# Week 8 — Local Tool Execution Harness

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** Week 7's pinned single-tool agent
**Lanes touched:** custom eval lane (primary), platform & CI lane (harness enters CI)
**Prerequisites:** Week 7 exit gate closed — 100 normalized traces, adapter tested, errata window closed.

[← Week 7](week-07-specimen.md) · [Week index](README.md) · [Next: Week 9 →](week-09-human-labeling.md)

---

## Objective

An automated local harness built on Strands Evals that maps the repo dataset into versioned experiments, separates metered trace generation from offline gate execution, and reports tool-selection accuracy, execution success rates, error-handling compliance, and timeout behavior in cloud-free PR CI.

## Why this week exists

This is the clipboard the rest of the plan writes on. Every later claim — "the judge agrees with humans", "the PR regressed tool selection", "the multi-tool agent sequences correctly" — is a harness report. Deterministic gates come first because they are cheap, explainable, and never hallucinate.

The division of labor being established: **gates check mechanical contract compliance; judges (Week 10) assess quality; humans (Week 9) define truth.** Gates can verify the agent called `weather.get_current_weather` twice with cities from the allowed set and didn't touch search — they cannot verify the response *compared the cities well*. Keeping that boundary explicit (the report footer literally says it) is what makes the harness's numbers trustworthy: nothing in this week's output is an opinion.

## Concepts

### `strands-agents-evals` primitives, and where your code plugs in

Verified against current docs (2026-07-13; PyPI snapshot `1.0.1`): the SDK's shape is **`Case`** (input, expected values, metadata) → **`Experiment`** (cases × evaluators) → `run_evaluations(task_function)` / `run_evaluations_async(...)` → **`EvaluationReport`**. Built-in deterministic evaluators (`Equals`, `Contains`, `StartsWith`, `ToolCalled`, `StateEquals`) are reusable reference implementations. Repo gates that need the full Week 6 `expected` contract subclass **`Evaluator`** and implement `evaluate(EvaluationData) -> list[EvaluationOutput]`; they do not pretend that subclassing `Contains` creates an argument-fidelity gate.

Each custom gate returns an explicit `EvaluationOutput`: `score` (`1.0` pass / `0.0` fail), `test_pass`, a stable evidence-bearing `reason`, and a machine label where it helps diagnosis. A malformed trace or broken adapter is an **instrument error**, not an ordinary `0.0` agent verdict. Preserve that distinction in exceptions and reports.

The SDK formats are adapters, not truth. `scripts/validate_dataset.py` still owns row/schema/binding/distribution/safety validation; `execution-trace.schema.json` remains the gate input contract; Strands Evals owns orchestration and reporting. Likewise, `strands-evals validate` proves that a serialized Experiment and its registered evaluators can be loaded — it does not validate the repo corpus.

### Map dataset rows into Cases without weakening the contract

`evals/adapters/cases.py` is the narrow join:

```text
Week 6 row + dataset manifest
        ↓ validate, then map
Case(name=exampleId, input=prompt,
     metadata={expected, tags, exact manifest/contract versions})
```

`Case.name` is the unique `exampleId`: the result store requires unique, non-null case names. The complete `expected` block and readable exact-version joins remain in metadata; the adapter validates the source row first and refuses unknown tags or malformed bindings. A serialized Experiment under `evals/experiments/` is derived and reproducible. If its JSON is reviewable, commit it; if not, commit the deterministic builder plus checksum and validation receipt instead.

The plan's sketch, mapping Week 6's `expected` block onto custom gates:

```python
from strands_evals import Case, Experiment
from evals.evaluators.gates import ExpectedToolsGate, ArgConstraintGate, FailureBehaviorGate, NoToolGate

cases = load_cases("datasets/synthetic/tool-calling-100.jsonl")
evaluators = [ExpectedToolsGate(), ArgConstraintGate(), FailureBehaviorGate(), NoToolGate()]
experiment = Experiment(cases=cases, evaluators=evaluators)
report = await experiment.run_evaluations_async(run_specimen)   # replays via mock registry
report.run_display()
```

Your four gates implement the row's `expected` block: right tools, right call counts, arg constraints satisfied, forbidden tools untouched, failure-injection rows produce the taxonomy-required behavior, no-tool rows stay tool-free. `run_specimen` is the task function — it runs Week 7's pinned specimen (mock registry behind it) and returns/emits what evaluators need.

### Use result caching to make the stage boundary real

Strands Evals' `LocalFileTaskResultStore` caches full `EvaluationData` so evaluators can be rerun without reinvoking a slow or stochastic agent. Use it behind a thin repo wrapper that namespaces the store by the complete run-manifest identity — a case name is unique within one Experiment, not across model/prompt/tool revisions.

- **Stage A — generate:** model + deterministic mock tools produce canonical traces once; this is metered and may vary.
- **Stage B — evaluate:** custom gates rerun against cached or fixture-loaded results with no model/tool invocation.
- **PR lane:** loads committed, reviewed public-safe regression traces through a task function; it never depends on a developer-local cache.

The local store contains complete prompts, outputs, and trajectories. Keep it git-ignored under a private/raw cache path, never upload it as a CI artifact, and run the public-safety policy over any derived fixture before committing it.

### Gate design: one claim, binary verdict, evidence attached

Rules that keep gates trustworthy:

- **One gate, one claim.** `ExpectedToolsGate` answers only "were the selected tools ⊆/⊇ what the row demands, within call bounds?" Argument fidelity is a different gate. Compound gates produce compound failures nobody can read.
- **Verdict + evidence, not verdict alone.** A failing gate emits *which* constraint failed, expected vs observed (`expected minCalls=2, observed 1 call to weather.get_current_weather`). Week 9's labelers and your own debugging live on these payloads.
- **Gates read normalized traces, not SDK internals.** The `execution-trace.schema.json` shape is the harness's input contract — that's what makes gates stable across SDK upgrades and lets Week 13 re-run them over traces from a *deployed* agent unchanged.
- **Gate error ≠ gate fail.** A gate that throws (malformed trace, unknown tag) must surface as an *error*, loudly distinct from a fail verdict. Errors mean the instrument broke; fails mean the agent misbehaved. Conflate them and neither number means anything.
- **Gates are code; buggy gates are worse than no gates.** Each gate gets unit tests against synthetic traces engineered per verdict — including at least one test that would catch an always-pass implementation (the most common real-world gate bug, and invisible in green CI by construction).

### The cloud-free boundary is Stage B

The specimen's mocked lane still calls the real Bedrock model to decide tool use, so the whole harness cannot honestly be called offline. This curriculum adopts the **two-stage harness**: Stage A runs the model + deterministic mocks locally or on a scheduled lane and writes manifest-namespaced results; Stage B evaluates cached or committed traces as a pure function with no network. PR CI runs Stage B over reviewed regression traces plus dataset/schema validation. Record–replay at the model boundary is deferred unless a later requirement earns its extra machinery.

Write this boundary in the harness README. A green PR proves known canonical traces still satisfy mechanical gates; it does not prove the current model would regenerate those traces. Week 13's merge/nightly lane asks that separate, metered question.

### Report design: per-tag or it hides the story

One overall accuracy number is marketing. The report's unit of meaning is **per-tag and per-kind**: tool-selection accuracy *on ambiguous rows* is the number that matters; failure-behavior compliance *per failure kind* is what localizes a taxonomy violation. Three renderings of the same numbers — console text (you, iterating), JSON (machines: CI thresholds, trend tooling), Markdown (`docs/reports/`, public-safe) — generated by one `scripts/summarize_run.py` so they cannot disagree. Every report carries its run-manifest fields (the join key) and the honesty footer: *mechanical contract compliance only; response quality is out of scope until human labels exist (Week 9).*

### Baseline ×3, then the sensitivity check

Before trusting the harness, two experiments:

1. **Gate stability:** evaluate the same cached/canonical results three times — identical verdicts required. Any flicker is in the adapter, evaluator, or report path; Stage A model variation is not involved.
2. **Sensitivity:** generate a new run after flipping one system-prompt word (or one docstring word — Week 7 Exercise 3 already staged this), then compare gates and repeat enough model runs to separate a directional effect from one stochastic sample. A harness where nothing moves may be insensitive; one where everything moves may be measuring model noise. Record both the generated-run variation and the deterministic gate verdicts.

## Build steps

### 1. Build `evals/harness.py` on `strands-agents-evals` primitives

At implementation time, re-check PyPI and the current docs, then pin `strands-agents-evals` exactly in the root dev dependency group and lock it with `uv`; record that version in the run manifest. Build `evals/adapters/cases.py`, then load validated Cases from the Week 6 dataset. Implement the four custom `Evaluator` gates so the full `expected` block is enforced: expected tools within call bounds, arg constraints, forbidden tools untouched, failure-injection rows produce taxonomy-required behavior, no-tool rows stay tool-free. Wire `run_specimen` to the Week 7 pinned configuration over the mock registry and adapt the canonical trace into the task result consumed by the gates.

### 2. Report per-tag and per-kind, not just overall

A blended average hides the ambiguous-row number that matters. Emit text (console), JSON (machine), and Markdown (docs/reports) — same numbers, three renderings, via `scripts/summarize_run.py`.

### 3. Wire the harness into GitHub Actions on every PR

Stage B only — fast, free, deterministic. Validate the repo dataset first, then validate the derived Strands Experiment, run custom gates over committed public-safe fixture traces, and upload only the flattened safe report. Keep unlabeled-quality questions out of scope: the harness validates *mechanical* contract compliance; response *quality* waits for human labels (Week 9). Say so in the report footer.

### 4. Baseline and sensitivity-check

Gate the same cached/canonical results three times and require identical verdicts. Then generate baseline and one-word-flip runs under distinct manifests, compare their repeated tool behavior, and watch which deterministic gates move. That two-part sensitivity check separates instrument stability from model variation.

## Exercises — guided discovery

**1. Spec the gate before coding it.** For `ExpectedToolsGate`, write the verdict table first: inputs (trace + `expected`), every combination of {tools called} × {bounds} × {mustNotCall}, and the verdict + evidence payload for each.
- *Hint 1:* What's the verdict when `toolIds` is empty and no tool was called — is that this gate's pass, or `NoToolGate`'s territory? Draw the boundary so no row is double-judged or unjudged.
- *Hint 2:* Over-calling (3 calls, max 2) and wrong-tool are different evidence payloads under the same fail verdict. Does your payload schema distinguish them for Week 9's disagreement analysis?

**2. The always-pass test.** For each gate, write the unit test that fails if the gate is accidentally a tautology.
- *Hint 1:* Construct a trace that *must* fail the gate; assert the verdict is fail. Trivial — and the single most valuable test in the file.
- *Hint 2:* Now the subtle sibling: a malformed trace (missing span field). Assert it produces *error*, not pass and not fail.

**3. Design the report's one-glance answer.** Sketch the Markdown report so "did tool selection get worse, and where?" is answerable in ten seconds.
- *Hint 1:* Rows = tags; columns = gate pass rates + n. What goes in the header so the report is self-identifying? (Manifest fields. Which ones?)
- *Hint 2:* n=10 per tag means one row flips ±10 points. Where does the report say "small n, expect quantization" — or does the JSON carry counts so tooling can, later?

**4. The failure-taxonomy compilation.** Take Week 5's required behaviors and sort every assertion into: deterministically gateable now / judge-territory (Week 10) / human-only (Week 9).
- *Hint 1:* "No fabricated weather values during an outage" — can a deterministic check approximate it (numeric-pattern scan of the response during injected failure)? What false positives would that scan produce, and are they acceptable for a *first* pass?
- *Hint 2:* `FailureBehaviorGate` implements only the first column. Its report section should name what it *didn't* check — that honesty is what the footer promises.

**5. Run the sensitivity experiment properly.** Three baselines → one-word flip → three runs again. Write the note: which gates moved, which didn't, and whether the movement pattern matches the word you flipped.
- *Hint 1:* Choose the word for a predicted effect ("never guess" → "avoid guessing" — what should move: no-tool compliance? selection on ambiguous rows?). A prediction beats a fishing trip.
- *Hint 2:* If a gate moved that shouldn't have, is that agent sensitivity or gate brittleness? What third run distinguishes them?

**6. Define the CI job.** Write the workflow: triggers, steps (dataset validation → safety scan → unit tests → gates), runtime budget, and what artifact it uploads.
- *Hint 1:* Which stage (A/B) runs on PR under your architecture decision? Where do the traces CI gates come from, and what pins them?
- *Hint 2:* The uploaded report JSON is the raw material for Week 13's thresholds — name it deterministically (manifest hash?) so runs are comparable across PRs.

**7. Build the adapter RED first.** Write `tests/test_evals_case_adapter.py`: one valid row must map to a uniquely named Case whose metadata preserves the full `expected` block and exact manifest/contract versions.
- *Hint 1:* First RED should be the missing adapter, then add invalid-row and duplicate-name cases. A mapper that accepts malformed source data has silently replaced the Week 6 validator.
- *Hint 2:* Round-trip the derived Experiment and compare case/evaluator counts. Which fields survive SDK serialization, and which remain repo-owned provenance outside it?

**8. Prove Stage B cannot call the model.** Generate one manifest-namespaced local result store, then rerun the evaluators with a task function that raises if invoked.
- *Hint 1:* A green rerun proves the cache short-circuited task execution; a cache miss should fail loudly rather than spend money unexpectedly.
- *Hint 2:* Inspect the cache before deciding where it lives. Which fields make it raw/private even though the tools are mocked?

**9. Exercise CLI/API parity.** Validate the serialized Experiment, run it through a fixture-loading `--task`, and render the report through the CLI; compare case/evaluator counts and verdict aggregates with the Python API path.
- *Hint 1:* Representative shape: `strands-evals validate ... --custom-evaluator ...`, then `strands-evals run ... --task ... --fail-on any -o ...`, then `strands-evals report ... --rich`. Verify exact flag placement against the installed version's `--help` before scripting it.
- *Hint 2:* Write down what each command proves. Why does SDK validation not prove dataset distribution or public safety?

## Gotchas & drift watch

- **Async/sync API surface:** the plan's sketch uses `run_evaluations_async`; the SDK also documents synchronous `run_evaluations`. Check the installed version's signatures (and pin `strands-agents-evals` in the manifest) before copying either form.
- **Evaluator interface drift:** the evals SDK is separately versioned and moved quickly through `0.1.x` to `1.0.x`. Re-check the custom `Evaluator` signature and `EvaluationOutput` fields (`reason`, not an invented `reasoning`) before implementing, pin exactly, and make upgrades deliberate adapter changes.
- **Result caches are raw artifacts.** `LocalFileTaskResultStore` serializes complete evaluation data. Namespace by run manifest, git-ignore it, and never confuse a local cache hit with a committed public-safe regression fixture.
- **Don't let the harness re-implement the adapter.** If evaluators need trace data, they read the Week 7 normalized shape. The moment a gate parses raw SDK objects directly, you have two normalization paths that will disagree silently.
- **The CLI has a narrower validator.** `strands-evals validate` catches bad Experiment serialization or missing custom evaluator registration; only repo validators catch row schema, exact bindings, coverage, and safety defects. CI runs both.
- **The committed baseline is a fixture — treat changes as reviewed diffs.** A PR that changes baseline numbers should *show* it (the JSON diff in review), not overwrite it in a drive-by commit. This is Week 13's regression discipline arriving early in social form.
- **Latency/timeout gates on mocks measure the mocks.** Timeout *behavior* (agent-side handling) is testable with scripted-delay fixtures; timeout *rates* are not meaningful in the mocked lane. Keep the report from implying otherwise — a column that only means something in Week 12's real-API lane shouldn't appear in the mocked report.
- **Minutes, not hours.** The success criterion ("runs in minutes") is a design constraint: if stage A (model calls) is in your PR path, you've likely chosen wrong upstream. Fast gates get run; slow gates get skipped, then deleted. Speed is a correctness feature of CI.

## Deliverable checklist — Local Evaluation Harness

- [ ] `evals/harness.py` + custom gate evaluators with unit tests.
- [ ] Dataset-to-Case adapter + a versioned derived Experiment whose exact bindings survive mapping and round-trip validation.
- [ ] Manifest-namespaced, git-ignored result-store lane with a negative test proving Stage B does not invoke the model.
- [ ] Reports in text/JSON/Markdown with per-tag breakdowns; committed baseline report.
- [ ] CLI/API parity receipt: same case/evaluator counts and verdict aggregates; CI runs repo validation + Experiment validation + fixture-backed gates on PRs.
- [ ] Sensitivity-check note (what moved when the prompt changed).

## Success criteria

- [ ] Stage B gates the 100-row dataset locally in minutes, offline and deterministically; Stage A's model invocation is separately identified, pinned, and never implied to be offline.
- [ ] Baseline metrics recorded: overall + per-tag tool-selection accuracy, execution success rate, failure-behavior compliance, no-tool compliance.
- [ ] A deliberately broken tool description produces a visibly worse report (proven, screenshotted).
- [ ] Re-running evaluators from the manifest-namespaced store succeeds while a task function that would invoke the model is configured to fail.

## Docs to consult

Verified via the AWS docs MCP server and current Strands/PyPI sources, 2026-07-13.

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
