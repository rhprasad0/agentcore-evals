# Strands Evals Curriculum Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Strengthen the 16-week learning plan’s use of Strands Evals as the custom-evaluation execution framework without replacing the repository’s versioned datasets, canonical traces, human ground truth, or AgentCore managed-evaluation lane.

**Architecture:** Keep the current curriculum sequence and four evidence boundaries: repository contracts/datasets define truth claims; the canonical trace adapter remains the stable internal interface; Strands Evals provides Cases, Experiments, custom Evaluators, task execution/caching, reports, and CI ergonomics; AgentCore Evaluations remains the separately calibrated managed lane. Deepen Strands Evals in Weeks 7–8, preserve calibrated `TrajectoryEvaluator` use in Week 11, and reuse its CLI/reporting surface in the offline Week 13 lane. Do not add a new week or a fourth LLM-judge lane.

**Tech Stack:** Markdown curriculum; Python 3.10+; `strands-agents-evals==1.0.1` (current PyPI release verified 2026-07-13, to be rechecked when Week 8 starts); Strands OpenTelemetry capture and session mappers; repository JSON Schema validators; GitHub Actions.

---

## Research Verdict

**Recommendation: integrate more deeply, but narrowly.** The plan already names Strands Evals as the custom-lane engine and uses its `Case`/`Experiment` model in Week 8 plus `TrajectoryEvaluator` in Week 11. The gap is not curriculum coverage; it is an under-specified integration boundary.

The SDK is valuable here because it now supplies:

- stable orchestration primitives (`Case`, `Experiment`, task functions, `EvaluationReport`);
- deterministic evaluators (`Equals`, `Contains`, `StartsWith`, `ToolCalled`, `StateEquals`);
- a documented custom `Evaluator` extension point returning `EvaluationOutput` records;
- `@eval_task(TracedHandler())` for Strands-native telemetry capture and session mapping;
- `LocalFileTaskResultStore` for separating expensive/stochastic task execution from evaluator iteration;
- JSON experiment/report serialization and a CI-oriented CLI with validation, reports, exit policies, custom evaluator registration, and cached execution;
- remote CloudWatch trace retrieval and session mappers for a later comparison with the repository-owned adapter;
- LLM trajectory evaluation that already fits Week 11’s calibrated judged-complement role.

The SDK should **not** become a second source of truth:

- `strands-evals validate` validates serialized Strands experiments; it does not replace `scripts/validate_dataset.py` or the repository’s JSON Schemas.
- `TracedHandler` and Strands session mappers do not replace the canonical execution-trace adapter. They are source adapters/compatibility tools whose output may drift with SDK versions.
- `LocalFileTaskResultStore` can contain complete inputs, outputs, and trajectories. Its cache must stay private/git-ignored and pass the same public-safety boundary as raw traces.
- SDK LLM evaluators remain judges. Do not add local `ToolSelectionAccuracyEvaluator` and `ToolParameterAccuracyEvaluator` as an uncalibrated fourth judge lane merely because they exist. The curriculum already has a self-built judge and managed AgentCore built-ins; extra lanes would add cost and muddy the learning claim.
- `ExperimentGenerator` may draft challenge cases, but the Week 6 hand-review/editorial protocol remains authoritative.

### Authoritative sources reviewed

- Strands Evals quickstart: <https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/>
- Evaluators overview: <https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/>
- Deterministic evaluators: <https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/deterministic_evaluators/>
- Task decorator and `TracedHandler`: <https://strandsagents.com/docs/user-guide/evals-sdk/how-to/eval_task/>
- Result caching: <https://strandsagents.com/docs/user-guide/evals-sdk/how-to/result_caching/>
- Remote trace providers: <https://strandsagents.com/docs/user-guide/evals-sdk/how-to/trace_providers/>
- CLI and CI behavior: <https://strandsagents.com/docs/user-guide/evals-sdk/cli/>
- PyPI release metadata: <https://pypi.org/project/strands-agents-evals/> (`1.0.1`, released 2026-06-25)
- Practical evaluation guide: <https://strandsagents.com/blog/evaluating-ai-agents-practical-guide-strands-evals/>

## Current Context and Assumptions

- `LEARNING_PLAN.md:24`, `:97`, `:109`, and the Week 8 summary already identify Strands Evals.
- `docs/weeks/week-07-specimen.md:34-40` owns capture → canonical normalization → storage.
- `docs/weeks/week-08-local-harness.md:23-41` sketches `Case`/`Experiment`, but it does not yet define the dataset-to-Case adapter, custom evaluator return contract, result-store safety, or CLI role.
- `docs/weeks/week-08-local-harness.md:55-60` already identifies the stage-A/model-call versus stage-B/offline-gate split. `LocalFileTaskResultStore` is a useful implementation mechanism for local iteration, but committed public-safe regression traces remain the PR source.
- `docs/weeks/week-11-multi-tool-chains.md:59-61` correctly treats `TrajectoryEvaluator` as an LLM judge that requires calibration.
- `docs/weeks/week-13-ci-regression.md:23-35` already defines offline PR and managed nightly lanes; the Strands CLI can make the offline lane inspectable without changing those semantics.
- The current root `pyproject.toml` intentionally has only Week 5’s `jsonschema` dependency. Do not install or pin Strands Evals while editing curriculum docs; the dependency is added when Week 8 implementation begins and the API is reverified.
- Repository status was clean on `main` at inspection time. The plan file is the only artifact to create during plan mode.

## Proposed Curriculum Boundary

Add this explicit mapping to the plan and Week 8 guide:

| Layer | Owner | Stable artifact | What Strands Evals does |
| --- | --- | --- | --- |
| Correctness definition | Repository | Week 5 contracts/taxonomy + Week 6 dataset schemas | Receives mapped Cases; does not define truth |
| Source telemetry | Strands SDK / ADOT | Pinned source profile | Captures or maps source spans |
| Canonical trace | Repository adapter | `execution-trace.schema.json` | Custom evaluators consume the canonical projection through a task adapter |
| Mechanical evaluation | Repository custom Evaluators on Strands Evals | `EvaluationOutput` verdicts with evidence | Orchestrates Cases × evaluators and reports |
| Human ground truth | Repository labeling workflow | `human-labels-64.jsonl` | No authority; only later comparisons |
| Judged evaluation | Own judge / managed AgentCore lane | Versioned judge outputs | Strands `TrajectoryEvaluator` is used only where explicitly calibrated |
| CI | Repository + Strands CLI | Experiment/report JSON and committed safe fixtures | Validates serialized experiments, runs offline tasks, applies exit policy, renders reports |

## Task 1: Tighten the Plan-Wide Strands Evals Positioning

**Objective:** Make the source-of-truth and framework boundaries visible before readers reach Week 8.

**Files:**
- Modify: `LEARNING_PLAN.md:21-27`
- Modify: `LEARNING_PLAN.md:104-123`
- Modify: `LEARNING_PLAN.md:125-171`
- Modify: `LEARNING_PLAN.md:211-229`
- Modify: `LEARNING_PLAN.md:291-303`

**Step 1: Correct the stack snapshot**

Update the Strands bullet to state that the Evals package is a separately versioned, fast-moving dependency and that the curriculum will pin the exact version in the Week 8 run manifest. Use `1.0.1` only as the verified research snapshot, not as a timeless claim.

Suggested text:

```markdown
- **Strands Agents 1.x + Strands Evals** — the agent SDK and the separately versioned evaluation SDK. The custom lane uses Evals for Case/Experiment orchestration, task-result caching, custom evaluator execution, and reporting; the repository's schemas and canonical traces remain the evaluation contracts. Pin and record the exact Evals version when Week 8 begins (PyPI snapshot verified 2026-07-13: `1.0.1`).
```

**Step 2: Add a custom-lane boundary paragraph**

Immediately after the architecture lanes, add the ownership table from “Proposed Curriculum Boundary.” State explicitly that SDK serialization and validation supplement rather than replace repository schemas.

**Step 3: Refine the repository target shape**

Keep `evals/cases/`, `evals/evaluators/`, and `evals/harness.py`, but add:

```text
evals/
  adapters/                  # dataset/canonical-trace → Strands Case/EvaluationData
  experiments/               # serialized, versioned Strands Experiment definitions
  evaluators/                # custom deterministic Evaluator subclasses
```

Do not move `src/adapters/`; it still owns raw telemetry → canonical trace normalization. `evals/adapters/` owns canonical repository artifacts → Strands Evals types.

**Step 4: Clarify the Week 8 and Week 11 summaries**

Week 8 summary should name `Case`, `Experiment`, custom `Evaluator`, cached task results, and CLI/report output. Week 11 should continue to describe `TrajectoryEvaluator` as a calibrated judged complement, not a deterministic gate.

**Step 5: Add one guardrail**

Append to Appendix C:

```markdown
- **Framework schemas are adapters, not truth.** Strands Evals Cases, Sessions, experiments, and reports are useful execution formats. Repository contracts, canonical traces, and human labels remain the stable evidence model; SDK upgrades cross a tested adapter boundary.
```

**Step 6: Review and verify**

Run:

```bash
git diff -- LEARNING_PLAN.md
git diff --check
```

Expected: only plan-positioning changes; no new implementation dependency or altered managed-evaluation claim.

**Step 7: Commit**

```bash
git add LEARNING_PLAN.md
git commit -m "docs: define Strands Evals curriculum boundary"
```

## Task 2: Add a Bounded Strands-Native Capture Exercise to Week 7

**Objective:** Teach the SDK’s `@eval_task(TracedHandler())` path without allowing it to bypass the repository’s canonical telemetry adapter.

**Files:**
- Modify: `docs/weeks/week-07-specimen.md:34-46`
- Modify: `docs/weeks/week-07-specimen.md:57-69`
- Modify: `docs/weeks/week-07-specimen.md:75-97`
- Modify: `docs/weeks/week-07-specimen.md:108-127`

**Step 1: Extend the instrumentation concept**

Add a short contrast between:

1. the explicit repository path: Strands/ADOT source telemetry → `src/adapters/` → canonical trace;
2. the convenience path: `@eval_task(TracedHandler())` → Strands `Session`.

State that the convenience path is a compatibility probe and Week 8 handoff, not the canonical storage format.

**Step 2: Add a capture cross-check exercise**

Add an exercise with this exact learning outcome:

- run one synthetic case through `@eval_task(TracedHandler())`;
- inspect the resulting `Session` and tool span;
- normalize the same synthetic source fixture through the repository adapter;
- compare tool name, arguments, result status, and correlation identifiers;
- record fields present in one representation but not the other;
- fail if the comparison silently drops a canonical required field.

Include a warning that `TracedHandler` clears and maps the in-memory exporter per case, while session IDs still need to remain unique and pinned.

**Step 3: Add version and safety requirements**

The Week 7 run manifest must record the Strands Evals package version and capture path. Any serialized SDK `Session` output is treated like a raw trace: git-ignored unless transformed into a reviewed public-safe fixture.

**Step 4: Extend deliverables and success criteria**

Add:

```markdown
- [ ] One public-safe synthetic compatibility test comparing the repository canonical adapter with Strands Evals' `TracedHandler`/Session mapping on the same declared source profile.
```

Success criterion: both paths agree on the required tool-call facts; differences are documented, and no claim of byte-identical schemas is made.

**Step 5: Update docs to consult**

Add the task decorator URL and current Evals quickstart. Update the verification date during implementation.

**Step 6: Review and verify**

Run:

```bash
git diff -- docs/weeks/week-07-specimen.md
git diff --check
```

Expected: Week 7 still produces the repository canonical trace and does not gain a cloud dependency.

**Step 7: Commit**

```bash
git add docs/weeks/week-07-specimen.md
git commit -m "docs: add Strands Evals capture cross-check"
```

## Task 3: Make Week 8 the Explicit Strands Evals Integration Week

**Objective:** Turn the existing sketch into an actionable integration contract that teaches the real SDK surface while preserving deterministic gate semantics.

**Files:**
- Modify: `docs/weeks/week-08-local-harness.md:11-41`
- Modify: `docs/weeks/week-08-local-harness.md:43-71`
- Modify: `docs/weeks/week-08-local-harness.md:73-90`
- Modify: `docs/weeks/week-08-local-harness.md:91-124`
- Modify: `docs/weeks/week-08-local-harness.md:126-146`
- Future implementation files named by the guide:
  - Modify: `pyproject.toml`
  - Modify: `uv.lock`
  - Create: `evals/adapters/cases.py`
  - Create: `evals/evaluators/gates.py`
  - Create: `evals/experiments/tool-calling-100.json`
  - Create: `evals/harness.py`
  - Create: `tests/test_evals_case_adapter.py`
  - Create: `tests/test_evals_gates.py`
  - Create: `tests/test_evals_experiment.py`

**Step 1: Replace “extends the family” with the actual extension contract**

The current wording implies custom gates subclass `ToolCalled`/`Equals`/`Contains`. Correct it: the repository gates subclass `Evaluator` and implement `evaluate(EvaluationData) -> list[EvaluationOutput]`; built-in deterministic evaluators are reference implementations and reusable helpers where their semantics fit.

Require every custom gate output to set:

- `score`: `1.0` pass or `0.0` fail;
- `test_pass`: explicit boolean;
- `reason`: stable human-readable evidence;
- `label`: stable machine category when useful.

Instrument errors remain exceptions or explicit harness errors; they must not be encoded as a normal `0.0` agent failure.

**Step 2: Specify the dataset-to-Case adapter**

Add a design box:

```text
Week 6 row + dataset manifest
        ↓ evals/adapters/cases.py
Strands Case(name=exampleId, input=prompt, metadata={expected, tags, exact versions})
```

Requirements:

- `Case.name` is the unique `exampleId` because result caching requires unique non-null names;
- the full `expected` block and exact manifest/version joins stay in metadata;
- the adapter validates the repository row first and refuses unknown fields/tags;
- serialization to a Strands Experiment is a derived artifact; it cannot weaken repository validation.

**Step 3: Resolve stage A/B with the SDK’s result store**

Use `LocalFileTaskResultStore` for local evaluator iteration:

- Stage A invokes the model against deterministic mock tools once and caches `EvaluationData` by unique Case name.
- Stage B re-runs custom evaluators against cached results without invoking the model.
- Cache keys must include or be namespaced by the complete run-manifest identity; a Case name alone is not sufficient across manifests.
- The cache directory is raw/private, git-ignored, and excluded from public receipts because it stores complete outputs and trajectories.
- PR CI still evaluates committed, reviewed public-safe regression traces through a fixture-loading `--task`; it does not rely on a developer’s cache.

This preserves the current stage-A/stage-B decision while using the SDK feature built for it.

**Step 4: Add a CLI/API parity exercise**

Teach both paths:

```bash
strands-evals validate evals/experiments/tool-calling-100.json \
  --custom-evaluator evals.evaluators.gates:ExpectedToolsGate

strands-evals run evals/experiments/tool-calling-100.json \
  --task evals.harness:load_public_safe_fixture \
  --custom-evaluator evals.evaluators.gates:ExpectedToolsGate \
  --fail-on any \
  -o reports/tool-calling-100.json

strands-evals report reports/tool-calling-100.json --rich
```

Before implementation, verify exact CLI placement and repeatability of `--custom-evaluator` against the installed version. The guide should call these representative commands, not immutable API promises.

State what each command proves:

- repository validator: row, manifest, distribution, binding, safety correctness;
- `strands-evals validate`: SDK experiment deserialization and evaluator registration;
- `strands-evals run`: orchestration and gate execution;
- `strands-evals report`: rendering of the SDK report, not the repository’s only public summary.

**Step 5: Add a TDD implementation sequence to Week 8**

The guide should direct this future RED→GREEN order:

1. Write `tests/test_evals_case_adapter.py` proving one valid row maps to a uniquely named Case with exact expected metadata.
2. Run it and confirm failure because `evals/adapters/cases.py` does not exist.
3. Implement the minimal adapter.
4. Add invalid-row and duplicate-name failures.
5. Write one failing gate test using a trace that must fail.
6. Implement the minimal `Evaluator` subclass and `EvaluationOutput` evidence.
7. Add pass, fail, and malformed-trace error tests for every gate.
8. Serialize one Experiment, validate it through the CLI, load it back, and assert evaluator/case counts.
9. Run Stage A once into a manifest-namespaced local result store; rerun Stage B with the task disabled and prove no model/tool invocation occurred.
10. Generate JSON and Markdown summaries and compare their aggregate numbers.

**Step 6: Add exact dependency discipline**

At Week 8 implementation time:

```toml
[dependency-groups]
dev = [
    "jsonschema==4.26.0",
    "strands-agents-evals==<CURRENT_VERIFIED_VERSION>",
]
```

Use `uv add --dev --exact strands-agents-evals==<CURRENT_VERIFIED_VERSION>` rather than hand-editing the lock. Record the installed version in run manifests and update the docs verification date. Do not pin `1.0.1` blindly if a later release exists when Week 8 begins.

**Step 7: Make exclusions explicit**

Week 8 does not use:

- LLM evaluators;
- `ExperimentGenerator` as dataset authority;
- remote trace providers;
- diagnosis/detectors;
- AgentCore Evaluations.

These are deferred because deterministic gates are the learning objective.

**Step 8: Update deliverables and success criteria**

Add:

- a versioned serialized Experiment derived from the repository dataset;
- tests proving adapter preservation of exact version joins;
- a manifest-namespaced, git-ignored result-store lane;
- CLI/API parity receipt with identical case/evaluator counts and verdict aggregates;
- a negative test proving Stage B does not invoke the model.

Keep existing report and sensitivity-check requirements.

**Step 9: Review and verify**

Run:

```bash
git diff -- docs/weeks/week-08-local-harness.md
git diff --check
```

Expected: no claim that all 100 model runs are offline; Stage B and PR fixtures are offline, while Stage A is explicitly metered/stochastic.

**Step 10: Commit**

```bash
git add docs/weeks/week-08-local-harness.md
git commit -m "docs: specify the Strands Evals harness integration"
```

## Task 4: Preserve Judge Discipline in Weeks 10–11

**Objective:** Demonstrate Strands Evals judged capabilities without adding an uncalibrated or redundant judge lane.

**Files:**
- Modify: `docs/weeks/week-10-judge-calibration.md:56-76`
- Modify: `docs/weeks/week-10-judge-calibration.md:122-129`
- Modify: `docs/weeks/week-11-multi-tool-chains.md:59-61`
- Modify: `docs/weeks/week-11-multi-tool-chains.md:77-80`
- Modify: `docs/weeks/week-11-multi-tool-chains.md:103-105`
- Modify: `docs/weeks/week-11-multi-tool-chains.md:134-140`

**Step 1: Add an explicit non-goal to Week 10**

Explain that Strands Evals also offers local `ToolSelectionAccuracyEvaluator` and `ToolParameterAccuracyEvaluator`, but the week does not automatically add them as a fourth lane. The curriculum’s calibrated comparison remains human labels vs self-built blind judge vs AgentCore managed built-ins. A local SDK evaluator may enter only through a preregistered question and the same calibration protocol.

**Step 2: Strengthen Week 11’s `TrajectoryEvaluator` protocol**

Require:

- exact Evals package version and judge model recorded;
- rubric versioned in repo;
- tool descriptions supplied from the same pinned contracts shown to the specimen;
- deterministic exact/in-order/any-order scorer chosen from row semantics rather than by convenience;
- calibration subset containing only rows with deterministic DAG verdicts;
- open-row use licensed only after agreement and flip-rate evidence is reported.

**Step 3: Add output-shape tests to the Week 11 plan**

The future implementation must assert that `EvaluationOutput` uses `reason` (not an invented `reasoning` field), score/pass semantics are mapped into the common verdict frame, and each report row identifies the evaluator.

**Step 4: Review and verify**

Run:

```bash
git diff -- docs/weeks/week-10-judge-calibration.md docs/weeks/week-11-multi-tool-chains.md
git diff --check
```

Expected: judge count does not silently grow; Strands `TrajectoryEvaluator` remains a calibrated complement.

**Step 5: Commit**

```bash
git add docs/weeks/week-10-judge-calibration.md docs/weeks/week-11-multi-tool-chains.md
git commit -m "docs: bound Strands Evals judge usage"
```

## Task 5: Reuse Strands Evals CLI and Trace Providers in Later Lanes

**Objective:** Carry the Week 8 framework skills into CI and observability without collapsing the custom and managed lanes.

**Files:**
- Modify: `docs/weeks/week-13-ci-regression.md:23-35`
- Modify: `docs/weeks/week-13-ci-regression.md:74-90`
- Modify: `docs/weeks/week-13-ci-regression.md:118-147`
- Modify: `docs/weeks/week-14-observability.md` at the custom/offline trace-analysis and docs sections after re-reading exact line locations during implementation

**Step 1: Make the Week 13 PR lane use the Week 8 interface**

Document the offline job as:

1. run repository dataset/contract/safety validators;
2. run unit tests;
3. validate the derived serialized Experiment;
4. run it with a fixture-loading `--task` and custom Evaluator registration;
5. use `--fail-on any` for 100% regression fixtures;
6. always upload the flattened JSON report and render the Markdown/job summary from it.

Do not use `--agent` in the PR lane because it would invoke the model. Do not use a developer-local task-result cache in CI.

**Step 2: Keep managed lane mechanics unchanged**

AgentCore batch evaluation remains the merge/nightly managed lane. Strands CLI output must not be called an AgentCore managed score.

**Step 3: Add a Week 14 comparison exercise for `CloudWatchProvider`**

For a small set of billboard-safe synthetic/test sessions:

- retrieve the same AgentCore Runtime session through the repository CloudWatch adapter and Strands Evals `CloudWatchProvider`;
- compare session/tool facts;
- record query/log-group requirements and mapping differences;
- retain the repository canonical adapter as the stable production evidence boundary;
- never commit raw provider output.

This teaches remote providers without changing Week 10/13 managed ingestion paths.

**Step 4: Add CI safety notes**

- `--data-store` is disabled or points only to ephemeral CI storage.
- Report artifacts are public-safe aggregates; raw cached `EvaluationData` is not uploaded.
- CLI exit code `1` means evaluation failure, `2` means bad experiment/config, and `3` means runtime error; the runbook should preserve that distinction.

**Step 5: Review and verify**

Run:

```bash
git diff -- docs/weeks/week-13-ci-regression.md docs/weeks/week-14-observability.md
git diff --check
```

Expected: lane 1 is offline and framework-backed; lane 2 remains managed and metered; CloudWatch provider comparison is a mapper audit, not a replacement.

**Step 6: Commit**

```bash
git add docs/weeks/week-13-ci-regression.md docs/weeks/week-14-observability.md
git commit -m "docs: carry Strands Evals into CI and trace audits"
```

## Task 6: Align the Week Index and Run a Curriculum Consistency Audit

**Objective:** Ensure summaries, prerequisites, and claims tell one consistent story after the detailed edits.

**Files:**
- Modify: `docs/weeks/README.md:18-39`
- Inspect: `README.md`
- Inspect: `LEARNING_PLAN.md`
- Inspect: `docs/weeks/week-06-dataset-validation.md`
- Inspect: `docs/weeks/week-07-specimen.md`
- Inspect: `docs/weeks/week-08-local-harness.md`
- Inspect: `docs/weeks/week-09-human-labeling.md`
- Inspect: `docs/weeks/week-10-judge-calibration.md`
- Inspect: `docs/weeks/week-11-multi-tool-chains.md`
- Inspect: `docs/weeks/week-13-ci-regression.md`
- Inspect: `docs/weeks/week-14-observability.md`

**Step 1: Update the Week 7–8 index summaries**

Week 7 should mention canonical trace plus Strands-native mapping compatibility. Week 8 should mention the versioned Strands Experiment, custom deterministic evaluators, cached local iteration, and offline CI report.

**Step 2: Audit terminology**

Search and correct these distinctions:

- Strands `Session` vs repository canonical trace;
- Strands Evals local evaluator vs AgentCore `Builtin.*` evaluator;
- repository dataset validation vs `strands-evals validate`;
- cached task result vs committed regression trace;
- deterministic evaluator vs LLM evaluator;
- SDK report vs public-safe summary.

Run:

```bash
rg -n "Strands Evals|strands-evals|Case|Experiment|TrajectoryEvaluator|ToolSelectionAccuracyEvaluator|Builtin\.ToolSelectionAccuracy|result store|data-store" LEARNING_PLAN.md README.md docs/weeks
```

**Step 3: Audit sequencing**

Confirm:

- Week 6 does not depend on Strands Evals runtime types;
- Week 7 introduces only a bounded capture compatibility exercise;
- Week 8 is the first required SDK dependency and full integration;
- Week 9 still treats humans as ground truth;
- Week 10 still has three calibrated lanes, not four by accident;
- Week 11 uses the trajectory judge only after calibration;
- Week 13 PR lane stays cloud-free;
- Week 14 remote-provider exercise does not upload or commit raw traces.

**Step 4: Run documentation verification**

Run:

```bash
git diff --check
python3 - <<'PY'
from pathlib import Path
for path in [Path("LEARNING_PLAN.md"), *sorted(Path("docs/weeks").glob("*.md"))]:
    text = path.read_text(encoding="utf-8")
    assert "strands-agents-evals==1.0.1" not in text or "verified 2026-07-13" in text
print("documentation consistency smoke passed")
PY
```

Expected: no whitespace errors; any snapshot version is dated and implementation instructions require re-verification.

**Step 5: Run public-safety checks**

Run Gitleaks once across the changed documentation set, following `AGENTS.md`. Confirm no account IDs, ARNs, raw traces, session IDs, or model outputs were introduced.

**Step 6: Inspect final scope**

Run:

```bash
git status --short
git diff --stat
git diff --check
```

Expected changed public artifacts:

- `LEARNING_PLAN.md`
- `docs/weeks/README.md`
- `docs/weeks/week-07-specimen.md`
- `docs/weeks/week-08-local-harness.md`
- `docs/weeks/week-10-judge-calibration.md`
- `docs/weeks/week-11-multi-tool-chains.md`
- `docs/weeks/week-13-ci-regression.md`
- `docs/weeks/week-14-observability.md`

No code, lockfile, dependency, deployment, AWS resource, or raw evaluation artifact should change during this documentation integration.

**Step 7: Commit the consistency pass**

```bash
git add docs/weeks/README.md
git commit -m "docs: align Strands Evals curriculum sequencing"
```

## Tests and Validation

Documentation integration is complete when:

- every Strands Evals capability in the curriculum points to a current authoritative doc;
- the package snapshot is dated and future implementation requires an exact reverified pin;
- the custom evaluator extension point is described accurately (`Evaluator`, `EvaluationData`, `list[EvaluationOutput]`);
- result caching is manifest-namespaced, private, and never confused with committed regression traces;
- Stage A (model invocation) and Stage B (offline evaluation) are mechanically distinct;
- repository validation and SDK experiment validation have separate commands and claims;
- Week 10 retains the existing human/self-built/managed calibration design;
- Week 11’s `TrajectoryEvaluator` remains explicitly LLM-based and calibration-gated;
- Week 13 PR CI uses an offline `--task` path rather than `--agent`;
- all changed docs pass `git diff --check` and Gitleaks;
- `git status --short` shows only the intended curriculum files and this local plan if plans are not ignored.

## Risks and Tradeoffs

- **SDK churn:** Strands Evals moved from `0.1.x` to `1.0.x` recently. Mitigation: exact implementation-time pin, run-manifest recording, docs re-verification, and adapter tests.
- **Framework capture bypassing canonical traces:** `TracedHandler` is convenient enough to become the accidental data model. Mitigation: frame it as a compatibility path; gates consume canonical traces through an adapter.
- **Cache leakage:** `LocalFileTaskResultStore` serializes complete evaluation data. Mitigation: manifest-namespaced git-ignored directories, no artifact upload, same treatment as raw traces.
- **Duplicate validation confusion:** repository schemas and SDK experiment serialization overlap superficially. Mitigation: list separate commands and claims in Week 8 and CI.
- **Judge proliferation:** the SDK includes many LLM evaluators. Mitigation: no fourth judge lane without preregistration and human calibration; use deterministic framework features first.
- **Curriculum bloat:** touching too many weeks can turn a useful integration into framework tourism. Mitigation: no new week, no detector/red-team/simulator requirements, and no implementation before Week 8.
- **CLI assumptions:** `--task`, `--custom-evaluator`, and exit behavior can drift. Mitigation: representative commands plus implementation-time `--help` and API verification.

## Deferred Capabilities

Do not add these to the required 16-week path now:

- automated failure diagnosis/detectors;
- red-team attack generators;
- LLM-powered tool simulation as a replacement for deterministic mocks;
- ActorSimulator-driven multi-turn testing before a real multi-turn requirement exists;
- ExperimentGenerator-authored ground truth;
- Langfuse/OpenSearch providers;
- multimodal evaluators;
- an additional local LLM judge lane.

They can appear in a post-capstone “further experiments” note if later evidence creates a real need.

## Open Questions for the Implementation Review

1. Should Week 8 serialize the full 100-row Experiment in git, or generate it deterministically from the repository dataset and commit only a checksum/validation receipt? Recommendation: generate deterministically and commit the derived Experiment only if its diff is genuinely reviewable.
2. Should local Stage A caching use the SDK store directly or a repository wrapper that enforces run-manifest namespacing and safety policy? Recommendation: a thin wrapper, because Case names are unique only within an experiment and are insufficient across manifests.
3. Should Week 14’s `CloudWatchProvider` comparison become a required deliverable or a guided exercise? Recommendation: guided exercise unless it reveals a mapper difference worth preserving as a regression fixture.
4. Should Strands’ local tool-selection evaluator be calibrated in Week 10? Recommendation: no by default; add it only if Ryan wants an explicit open-source-vs-managed judge comparison and accepts the extra cost and analysis lane.
