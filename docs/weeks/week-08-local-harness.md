# Week 8 — Local Tool Execution Harness

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** Week 7's pinned single-tool agent
**Lanes touched:** custom eval lane (primary), platform & CI lane (harness enters CI)
**Prerequisites:** Week 7 exit gate closed — 62 finalized case outcomes with validated canonical traces or explicit instrument errors, adapter tested, errata window closed.

[← Week 7](week-07-specimen.md) · [Week index](README.md) · [Next: Week 9 →](week-09-human-labeling.md)

---

## Objective

An automated local harness built on Strands Evals that maps Week 7's exact 62-row weather projection into a versioned experiment, separates metered trace generation from fail-closed offline gate execution, and reports mechanically defined selection, execution, failure-handling, no-tool, and instrument-validity metrics in cloud-free PR CI.

## Why this week exists

This is the clipboard the rest of the plan writes on. Every later claim — "the judge agrees with humans", "the PR regressed tool selection", "the multi-tool agent sequences correctly" — is a harness report. Deterministic gates come first because they are cheap, explainable, and never hallucinate.

The division of labor being established: **gates check mechanical contract compliance; judges (Week 10) assess quality; humans (Week 9) define truth.** Gates can verify the agent called `weather.get_current_weather` twice with cities from the allowed set and didn't touch search — they cannot verify the response *compared the cities well*. Keeping that boundary explicit (the report footer literally says it) is what makes the harness's numbers trustworthy: nothing in this week's output is an opinion.

## Concepts

### `strands-agents-evals` primitives, and where your code plugs in

Verified against the linked current docs (2026-07-18; target PyPI snapshot `1.0.1`): the SDK's shape is **`Case`** (input, expected values, metadata) → **`Experiment`** (cases × evaluators) → `run_evaluations(task_function)` / `run_evaluations_async(...)` → **`EvaluationReport`**. Built-in deterministic evaluators (`Equals`, `Contains`, `StartsWith`, `ToolCalled`, `StateEquals`) are reusable reference implementations. Repo gates that need the full Week 6 `expected` contract subclass **`Evaluator`** and implement `evaluate(EvaluationData) -> list[EvaluationOutput]`; they do not pretend that subclassing `Contains` creates an argument-fidelity gate.

The dated docs snapshot is not the implementation receipt. Before writing the adapter, pin the exact release in `pyproject.toml`/`uv.lock`, inspect the installed import paths and signatures for `Case`, `Experiment`, `Evaluator`, `EvaluationData`, `EvaluationOutput`, and `LocalFileTaskResultStore`, capture `strands-evals --help` for `validate`, `run`, `report`, `--data-store`, `--custom-evaluator`, and `--fail-on`, and prove one Experiment serialization round trip. Installed source wins if generated documentation differs.

Each custom gate returns an explicit `EvaluationOutput`: `score` (`1.0` pass / `0.0` fail), `test_pass`, a stable evidence-bearing `reason`, and a machine label where it helps diagnosis. A malformed trace or broken adapter is an **instrument error**, not an ordinary `0.0` agent verdict. Preserve that distinction in exceptions and reports.

The SDK formats are adapters, not truth. `scripts/validate_dataset.py` still owns row/schema/binding/distribution/safety validation; `execution-trace.schema.json` remains the gate input contract; Strands Evals owns orchestration and reporting. Likewise, `strands-evals validate` proves that a serialized Experiment and its registered evaluators can be loaded — it does not validate the repo corpus.

### Map dataset rows into Cases without weakening the contract

`evals/adapters/cases.py` is the narrow join. The executable Week 8 Experiment is `weather-only-62@1.0.0`, the exact projection completed in Week 7. The adapter validates the frozen 100-row source corpus and projection manifest, then maps only the 62 selected source rows without rewriting expectations. A 62-row report is not described as full-portfolio coverage; calculator/search rows remain outside this one-tool specimen.

```text
Week 6 source row + weather-only projection + dataset manifest
        ↓ validate source and projection, then map selected row
Case(name=exampleId, input=prompt,
     metadata={expected, tags, exact manifest/contract versions})
```

`Case.name` is the unique `exampleId`: the result store requires unique, non-null case names. The complete `expected` block and readable exact-version joins remain in metadata; the adapter validates the source row first and refuses unknown tags or malformed bindings. A serialized Experiment under `evals/experiments/` is derived and reproducible. If its JSON is reviewable, commit it; if not, commit the deterministic builder plus checksum and validation receipt instead.

The Stage A sketch maps the projected rows and invokes the pinned specimen once to generate task results:

```python
from strands_evals import Case, Experiment
from evals.evaluators.gates import ExpectedToolsGate, ArgConstraintGate, FailureBehaviorGate, NoToolGate

cases = load_projected_cases("datasets/projections/weather-only-62.json")
evaluators = [ExpectedToolsGate(), ArgConstraintGate(), FailureBehaviorGate(), NoToolGate()]
experiment = Experiment(cases=cases, evaluators=evaluators)
report = await experiment.run_evaluations_async(run_specimen)   # Stage A: real model + mock tools
report.run_display()
```

Your four gates implement the row's `expected` block: right tools, right call counts, arg constraints satisfied, forbidden tools untouched, failure-injection rows produce the taxonomy-required behavior, no-tool rows stay tool-free. `run_specimen` is Stage A only: it runs Week 7's pinned specimen (mock registry behind it) and returns what evaluators need. Stage B is a separate entry point that accepts only a provenance-validated fixture/canonical-outcome path plus evaluator configuration; it does not accept an agent factory, Bedrock model, mock registry, or Stage A callback.

### Use result caching to make the stage boundary real

Strands Evals' `LocalFileTaskResultStore` caches full `EvaluationData` by `case.name` so evaluators can be rerun without reinvoking a slow or stochastic agent. Put each private store under `datasets/runs/<runId>/eval-cache/`; the enclosing `runId` supplies execution scope. Before reading it, validate that the directory identity matches the run manifest, recompute its content-derived `experimentId`, require the exact projection ID/version/artifact hash and source-profile version, and require every projected `exampleId` exactly once. Evaluator/report versions belong in evaluation reports, not task-result identity: changing evaluators is why task results are cached.

- **Stage A — generate:** model + deterministic mock tools produce canonical traces once; this is metered and may vary.
- **Stage B — evaluate:** custom gates rerun against cached or fixture-loaded results with no model/tool invocation.
- **PR lane:** loads committed, reviewed public-safe regression traces through the fixture-only Stage B entry point; it never depends on a developer-local cache or the SDK's cache-miss fallback.

The local store contains complete prompts, outputs, and trajectories. Keep it git-ignored, never upload it as a CI artifact, and run the public-safety policy over any derived fixture before committing it. A committed fixture set must carry a schema-valid provenance manifest with fixture-set ID/version, `experimentId`, projection ID/version/hash, canonical trace schema version, the exact expected case IDs, per-fixture SHA-256 values, valid-trace/instrument-error counts, and public-safety policy version. Missing, extra, duplicate, hash-mismatched, schema-invalid, or semantically invalid outcomes fail before evaluators run. Public provenance omits raw prompts/responses, private paths, and `runId` unless a later reviewed policy deliberately permits them.

### Gate design: one claim, binary verdict, evidence attached

Rules that keep gates trustworthy:

- **One gate, one claim.** `ExpectedToolsGate` answers only "were the selected tools ⊆/⊇ what the row demands, within call bounds?" Argument fidelity is a different gate. Compound gates produce compound failures nobody can read.
- **Verdict + evidence, not verdict alone.** A failing gate emits *which* constraint failed, expected vs observed (`expected minCalls=2, observed 1 call to weather.get_current_weather`). Week 9's labelers and your own debugging live on these payloads.
- **Gates read normalized traces, not SDK internals.** The `execution-trace.schema.json` shape is the harness's input contract — that's what makes gates stable across SDK upgrades and lets Week 13 re-run them over traces from a *deployed* agent unchanged.
- **Gate error ≠ gate fail.** A gate that throws (malformed trace, unknown tag) must surface as an *error*, loudly distinct from a fail verdict. Errors mean the instrument broke; fails mean the agent misbehaved. Conflate them and neither number means anything.
- **Gates are code; buggy gates are worse than no gates.** Each gate gets unit tests against synthetic traces engineered per verdict — including at least one test that would catch an always-pass implementation (the most common real-world gate bug, and invisible in green CI by construction).

Preflight decides whether evidence is judgeable before any gate produces an agent verdict:

| Observed state | Classification | Gate behavior |
| --- | --- | --- |
| Schema, correlation, or semantic invariant fails | instrument error | Emit no agent verdicts. |
| Unexpected mock lookup miss or contract-invalid tool result | instrument error | Emit no agent verdicts. |
| Evaluator raises or emits malformed/missing output | gate error | Exclude that gate verdict and fail the harness run. |
| Trace-valid call has a wrong or missing argument | agent fail | `ArgConstraintGate` applies. |
| Expected injected failure returns a contract-valid failure envelope | valid evidence | `FailureBehaviorGate` judges the response. |
| Agent/model timeout leaves no valid canonical trace | instrument error | Emit no agent verdicts. |
| Scripted contract-valid timeout result is observed | valid evidence | `FailureBehaviorGate` applies. |

Gate applicability is explicit; orthogonal verdicts remain separate metrics rather than being blended or called double counting:

| Row/trace state | `ExpectedToolsGate` | `ArgConstraintGate` | `FailureBehaviorGate` | `NoToolGate` |
| --- | --- | --- | --- | --- |
| Invalid evidence | error/no output | error/no output | error/no output | error/no output |
| `toolIds=[]`, no calls | N/A | N/A | if injected-failure contract applies | pass |
| `toolIds=[]`, any call | N/A | N/A | if injected-failure contract applies | fail |
| Required tool missing, wrong, forbidden, or over-called | fail | N/A for nonmatching calls | independently applicable | N/A |
| Expected tool observed with bad args | pass for selection | fail | independently applicable | N/A |
| Expected tool observed with valid args | pass | pass | independently applicable | N/A |

Tests cover every matrix row. Mutation cases must prove that normalization cannot erase a forbidden call, attach a result to the wrong call, or turn an invalid trace into a behavioral fail.

### The cloud-free boundary is Stage B

The specimen's mocked lane still calls the real Bedrock model to decide tool use, so the whole harness cannot honestly be called offline. This curriculum adopts the **two-stage harness**: Stage A runs the model + deterministic mocks locally or on a scheduled lane and writes run-scoped results; Stage B evaluates provenance-validated cached or committed traces as a pure function. A missing fixture/result in offline mode is an integrity error and must never fall through to the SDK's documented “run task, then save” behavior. PR CI runs Stage B over reviewed regression traces plus dataset/projection/fixture validation. Record–replay at the model boundary is deferred unless a later requirement earns its extra machinery.

Write this boundary in the harness README. Stage B tests run with AWS credential variables cleared, `AWS_EC2_METADATA_DISABLED=true`, an agent/task callable that raises if touched, and socket connection attempts denied. Cover fixture success, missing/corrupt fixture preflight, evaluator imports, CLI execution, and report rendering. These tests prove only that the defined Stage B entry points processed provenance-linked fixtures without observed credential/network/model/tool access; they do not make the Python process a security sandbox or constrain arbitrary third-party evaluator code. A green PR does not prove the current model would regenerate those traces. Week 13's merge/nightly lane asks that separate, metered question.

### Report design: per-tag or it hides the story

One overall accuracy number is marketing. Every metric follows [Appendix B's metric contract](../../LEARNING_PLAN.md#appendix-b--metrics-glossary): unit, eligible population, numerator, denominator, and excluded errors are explicit. Reports show projected, evidence-valid, instrument-error, and gate-error counts so exclusions cannot improve a score silently. Multi-tag rows appear once in every applicable diagnostic slice but once overall; `n=0` renders a null rate. The report's unit of meaning is **per-tag and per-kind**: tool-selection accuracy *on ambiguous rows* is the number that matters; failure-behavior compliance *per failure kind* localizes a taxonomy violation.

Console text, canonical JSON, and Markdown (`docs/reports/`, public-safe) render from one aggregate object through `scripts/summarize_run.py`; no renderer recomputes metrics. CLI/API parity means exact agreement on case/evaluator eligibility, pass/fail/error counts, numerators, denominators, and rates. A schema-backed allowlist permits reviewed fixture/experiment/projection identities, package/evaluator versions, synthetic case IDs, counts, rates, labels, and bounded evidence codes. It rejects raw prompts/responses, arguments/results, local paths, credentials, account/resource IDs, and raw diagnostics. Every report carries the honesty footer: *mechanical contract compliance only; response quality is out of scope until human labels exist (Week 9).*

### Baseline ×3, then the sensitivity check

Before trusting the harness, two experiments:

1. **Gate stability:** evaluate the same cached/canonical results three times. Require exact canonical JSON equality for gate outputs and aggregate JSON; presentation-only timestamps or Rich formatting are outside the comparator and must never enter the canonical aggregate. Any verdict flicker is in the evaluator/report path; Stage A model variation is not involved.
2. **Sensitivity:** preregister one target metric/stratum and expected direction, then generate three Stage A baseline runs and three changed-condition runs under distinct manifests. Inspect the first changed-condition run for instrument validity before continuing so broken instrumentation does not multiply spend. Change exactly one model-visible byte sequence, record before/after hashes and tokenizer/token-count observations when available, and score only newly generated outcomes—replaying old fixtures is not agent sensitivity. Tokenization is part of the intervention, not a removable confound. Report a positive, null, or inconclusive association honestly; do not require a favorable effect or claim a pure semantic cause.

## Build steps

### 1. Build `evals/harness.py` on `strands-agents-evals` primitives

At implementation time, complete the installed-source/CLI receipt, pin `strands-agents-evals` exactly in the root dev dependency group, lock it with `uv`, and record the version in the run manifest. Build `evals/adapters/cases.py`, validate the frozen source plus `weather-only-62@1.0.0` projection, and load the 62 selected Cases. Implement the four custom gates and the evidence-validity/applicability matrices above. Wire `run_specimen` only to Stage A; build a separate fixture-only Stage B entry point.

### 2. Report per-tag and per-kind, not just overall

A blended average hides the ambiguous-row number that matters. Define `schemas/eval-report.schema.json` as a public allowlist, then emit one canonical aggregate as console text, JSON, and Markdown through `scripts/summarize_run.py`. Tests include a valid 62-row report plus invalid raw-prompt and missing-denominator fixtures.

### 3. Wire the harness into GitHub Actions on every PR

Stage B only — fast, free, deterministic. Run dataset/projection validation → fixture-manifest schema/hash/semantic validation → gate tests → derived Experiment validation → fixture-backed Stage B with credentials cleared and network attempts denied → report-schema validation. Define `schemas/eval-fixture-manifest.schema.json`, `evals/fixtures/weather-only-62/manifest.json`, and valid/invalid provenance fixtures before enabling CI. Upload only the flattened allowlisted report. Keep unlabeled-quality questions out of scope: the harness validates *mechanical* compliance; response *quality* waits for humans in Week 9.

### 4. Baseline and sensitivity-check

Gate the same cached/canonical results three times and require exact canonical gate/aggregate JSON equality. Preregister the sensitivity target and direction, generate three baseline and three changed-condition Stage A runs under distinct manifests, inspect the first changed run before continuing, and score only fresh outcomes. Publish counts plus a positive, null, or inconclusive result; do not require a regression.

## Exercises — guided discovery

**1. Spec the gate before coding it.** For `ExpectedToolsGate`, write the verdict table first: inputs (trace + `expected`), every combination of {tools called} × {bounds} × {mustNotCall}, and the verdict + evidence payload for each.
- *Hint 1:* What's the verdict when `toolIds` is empty and no tool was called — is that this gate's pass, or `NoToolGate`'s territory? Draw the boundary so no row is double-judged or unjudged.
- *Hint 2:* Over-calling (3 calls, max 2) and wrong-tool are different evidence payloads under the same fail verdict. Does your payload schema distinguish them for Week 9's disagreement analysis?

**2. The always-pass test.** For each gate, write the unit test that fails if the gate is accidentally a tautology.
- *Hint 1:* Construct a trace that *must* fail the gate; assert the verdict is fail. Trivial — and the single most valuable test in the file.
- *Hint 2:* Now the subtle sibling: a malformed trace (missing span field). Assert it produces *error*, not pass and not fail.

**3. Design the report's one-glance answer.** Sketch the canonical aggregate and Markdown view so "did tool selection get worse, and where?" is answerable in ten seconds.
- *Hint 1:* For every metric, write unit, eligible population, numerator, denominator, and error counts before drawing the table. Which provenance joins are safe to publish?
- *Hint 2:* Multi-tag rows belong in each diagnostic stratum but once overall. How will `n=0`, small-cell quantization, and instrument exclusions appear without misleading the reader?

**4. The failure-taxonomy compilation.** Take Week 5's required behaviors and sort every assertion into: deterministically gateable now / judge-territory (Week 10) / human-only (Week 9).
- *Hint 1:* "No fabricated weather values during an outage" — can a deterministic check approximate it (numeric-pattern scan of the response during injected failure)? What false positives would that scan produce, and are they acceptable for a *first* pass?
- *Hint 2:* `FailureBehaviorGate` implements only the first column. Its report section should name what it *didn't* check — that honesty is what the footer promises.

**5. Run the sensitivity experiment properly.** Preregister target stratum, metric, and direction; three baselines → one exact model-visible byte change → inspect one changed run → finish the planned three changed runs if instrumentation is valid. Write the positive, null, or inconclusive result.
- *Hint 1:* Record exact before/after hashes and token counts when available. Tokenization is part of what changed; do not pretend the experiment isolates abstract semantics.
- *Hint 2:* If a deterministic gate changes on identical canonical input, that is gate brittleness. If fresh Stage A outcomes change, it may be agent sensitivity; report repeated counts rather than forcing a causal story.

**6. Define the CI job.** Write the workflow: triggers, dataset/projection validation, fixture provenance preflight, unit tests, offline guards, gates, report validation, runtime budget, and uploaded artifact.
- *Hint 1:* Which Stage B inputs are accepted, and what exact condition fails before the SDK can invoke a task on cache miss?
- *Hint 2:* Clear credentials, disable metadata lookup, and deny socket attempts in the Stage B test. What does that receipt prove—and what does it not prove about arbitrary imported code?

**7. Build the adapter RED first.** Write `tests/test_evals_case_adapter.py`: the frozen source plus projection maps exactly 62 uniquely named Cases whose metadata preserves the full `expected` block and exact joins.
- *Hint 1:* First RED should be the missing adapter, then invalid source/projection, duplicate-name, and extra/missing-selected-row cases. A mapper that accepts malformed source data has silently replaced the Week 6 validator.
- *Hint 2:* Round-trip the derived Experiment and compare case/evaluator counts and nested metadata. If the SDK serializer drops repo provenance, where does the narrow repo-owned mapping live?

**8. Prove the defined Stage B paths cannot call the model.** Use a run-scoped private store and committed fixture set; make the agent/task callable, credential lookup, and socket connection raise if touched.
- *Hint 1:* Cover valid fixtures, missing/corrupt fixtures, CLI execution, evaluator import, and report rendering. A cache miss must fail in repo preflight before the SDK's run-and-save fallback.
- *Hint 2:* This is a tested-path cost/privacy receipt, not a process sandbox. Which third-party evaluator behaviors remain outside the claim?

**9. Exercise CLI/API parity.** Validate the serialized Experiment, run it through the fixture-only Stage B entry point, and render the report through the CLI; compare canonical eligibility, pass/fail/error, numerator, denominator, and rate fields with the Python API path.
- *Hint 1:* Representative shape: `strands-evals validate ... --custom-evaluator ...`, then `strands-evals run ... --task ... --fail-on any -o ...`, then `strands-evals report ... --rich`. Verify exact flag placement against the installed version's `--help` before scripting it.
- *Hint 2:* Write down what each command proves. Why does SDK validation not prove dataset distribution or public safety?

## Gotchas & drift watch

- **Async/sync API surface:** the plan's sketch uses `run_evaluations_async`; the SDK also documents synchronous `run_evaluations`. Check the installed version's signatures (and pin `strands-agents-evals` in the manifest) before copying either form.
- **Evaluator interface drift:** the evals SDK is separately versioned and moved quickly through `0.1.x` to `1.0.x`. Re-check the custom `Evaluator` signature and `EvaluationOutput` fields (`reason`, not an invented `reasoning`) before implementing, pin exactly, and make upgrades deliberate adapter changes.
- **Result caches are raw artifacts.** `LocalFileTaskResultStore` serializes complete evaluation data and keys only by case name. Scope it under `datasets/runs/<runId>/eval-cache/`, validate the enclosing manifest and exact case set before reads, git-ignore it, and never confuse a local cache hit with a provenance-linked public fixture.
- **Don't let the harness re-implement the adapter.** If evaluators need trace data, they read the Week 7 normalized shape. The moment a gate parses raw SDK objects directly, you have two normalization paths that will disagree silently.
- **The CLI has a narrower validator.** `strands-evals validate` catches bad Experiment serialization or missing custom evaluator registration; only repo validators catch row schema, exact bindings, coverage, and safety defects. CI runs both.
- **The committed baseline is a fixture — treat changes as reviewed diffs.** A PR that changes baseline numbers should *show* it (the JSON diff in review), not overwrite it in a drive-by commit. This is Week 13's regression discipline arriving early in social form.
- **A valid fixture is more than valid JSON.** The committed manifest joins exact projection/schema/experiment identities to every expected case and fixture hash. A stale, partial, extra, or cross-experiment set fails before gates run.
- **Error exclusions can improve a score dishonestly.** Behavioral denominators use evidence-valid rows, but every report also shows projected, evidence-valid, instrument-error, and gate-error counts. Never publish a rate without its eligibility count.
- **Latency/timeout gates on mocks measure the mocks.** Timeout *behavior* (agent-side handling) is testable with scripted-delay fixtures; timeout *rates* are not meaningful in the mocked lane. Keep the report from implying otherwise — a column that only means something in Week 12's real-API lane shouldn't appear in the mocked report.
- **Minutes, not hours.** The success criterion ("runs in minutes") is a design constraint: if stage A (model calls) is in your PR path, you've likely chosen wrong upstream. Fast gates get run; slow gates get skipped, then deleted. Speed is a correctness feature of CI.

## Deliverable checklist — Local Evaluation Harness

- [ ] `evals/harness.py` + custom gate evaluators with matrix-derived unit/mutation tests.
- [ ] Source-plus-projection Case adapter + 62-case derived Experiment whose exact bindings survive mapping and round-trip validation.
- [ ] `schemas/eval-fixture-manifest.schema.json` + `evals/fixtures/weather-only-62/manifest.json` with valid/wrong-hash/missing-case fixtures and fail-closed preflight.
- [ ] Run-scoped, git-ignored `datasets/runs/<runId>/eval-cache/` lane plus fixture-only Stage B tests covering task, cache-miss, credential, socket, CLI, and report paths.
- [ ] `schemas/eval-report.schema.json` + text/JSON/Markdown renderings from one canonical aggregate, with invalid raw-prompt and missing-denominator fixtures.
- [ ] CLI/API parity receipt: identical eligibility/pass/fail/error/numerator/denominator/rate fields; PR CI runs repo + projection + fixture + Experiment + report validation around offline gates.
- [ ] Preregistered three-baseline/three-changed sensitivity note using fresh Stage A outcomes, with a positive, null, or inconclusive interpretation.

## Success criteria

- [ ] All 62 projected outcomes are provenance-accounted: each evidence-valid canonical trace is gated, while instrument errors remain explicit and outside behavioral denominators; the 62-row result is never called full 100-row portfolio coverage.
- [ ] Repeating Stage B over identical inputs produces exactly equal canonical gate and aggregate JSON, and tested Stage B paths pass with task invocation, credentials, and socket access configured to fail.
- [ ] Baseline reports record overall + per-tag selection, parameter, execution, failure-behavior, no-tool, and instrument-validity metrics with explicit eligibility, numerators, denominators, and error counts.
- [ ] CLI and API paths agree on the canonical aggregate; every public rendering passes the allowlist schema and contains no raw prompt, response, argument, result, path, account/resource identifier, credential, or diagnostic payload.
- [ ] The preregistered fresh-outcome sensitivity comparison completes three baseline and three changed-condition runs, or records an explicit instrument blocker; its result may be positive, null, or inconclusive and makes no deterministic or pure-semantic causal claim.

## Docs to consult

Verified via the AWS docs MCP server and current Strands/PyPI sources, 2026-07-18. Reverify against the exact locked installed package before implementation; the installed-source/CLI receipt is part of this week's deliverable.

- [Strands Evals quickstart](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/) — Case/Experiment lifecycle, task functions, telemetry capture, credentials; the harness skeleton is this page.
- [Strands Evals deterministic evaluators](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/deterministic_evaluators/) — `Equals`, `Contains`, `ToolCalled`, `StateEquals` semantics and parameters; use them where their exact claim fits and match their `EvaluationOutput` conventions in custom gates.
- [Strands Evals custom evaluators](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/custom_evaluator/) — the `Evaluator` / `EvaluationData` / `EvaluationOutput` extension contract for repo gates.
- [Strands Evals result caching](https://strandsagents.com/docs/user-guide/evals-sdk/how-to/result_caching/) — `LocalFileTaskResultStore`, unique Case-name requirement, and task short-circuit semantics.
- [Strands Evals CLI](https://strandsagents.com/docs/user-guide/evals-sdk/cli/) — Experiment validation, custom evaluator registration, fixture-loading task entry points, exit policies, and report rendering; verify flags against the exact pinned version.
- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — re-reference for what trace context evaluators can see.
- Metrics definitions: every number your report emits is defined once in [Appendix B — Metrics Glossary](../../LEARNING_PLAN.md#appendix-b--metrics-glossary); link report columns to it rather than redefining.

## Self-check

1. State the gates-vs-judges division of labor in one sentence each, and name the report element that announces it.
2. Why must gate *error* be distinguishable from gate *fail*? Give the concrete scenario where conflating them corrupts a week-over-week comparison.
3. Describe your stage-A/stage-B architecture and justify what runs on a PR. What exactly would a PR-lane green checkmark *not* tell you?
4. Your overall selection accuracy is 96%, ambiguous-tag accuracy is 60%. What does the blended number conceal, and which report design choice prevents the concealment?
5. In the sensitivity check, nothing moved. List the three hypotheses in the order you'd test them.
6. Why do the harness gates read the normalized trace schema instead of Strands objects, and which two later weeks does that choice directly pay off?
