# Week 8 — Local Tool Execution Harness

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** Week 7's pinned single-tool agent
**Lanes touched:** custom eval lane (primary), platform & CI lane (harness enters CI)
**Prerequisites:** Week 7 exit gate closed — 100 normalized traces, adapter tested, errata window closed.

[← Week 7](week-07-specimen.md) · [Week index](README.md) · [Next: Week 9 →](week-09-human-labeling.md)

---

## Objective

An automated local harness that replays the dataset through the specimen and reports tool-selection accuracy, execution success rates, error-handling compliance, and timeout behavior — deterministically, in CI, without cloud calls.

## Why this week exists

This is the clipboard the rest of the plan writes on. Every later claim — "the judge agrees with humans", "the PR regressed tool selection", "the multi-tool agent sequences correctly" — is a harness report. Deterministic gates come first because they are cheap, explainable, and never hallucinate.

The division of labor being established: **gates check mechanical contract compliance; judges (Week 10) assess quality; humans (Week 9) define truth.** Gates can verify the agent called `weather.get_current_weather` twice with cities from the allowed set and didn't touch search — they cannot verify the response *compared the cities well*. Keeping that boundary explicit (the report footer literally says it) is what makes the harness's numbers trustworthy: nothing in this week's output is an opinion.

## Concepts

### `strands-agents-evals` primitives, and where your code plugs in

Verified against current docs (2026-07-07): the SDK's shape is **`Case`** (input, expected output, session metadata) → **`Experiment`** (cases × evaluators) → `run_evaluations(task_function)` → **report** (with `run_display()` and structured results). Its deterministic evaluator family — `Equals`, `Contains`, `ToolCalled`, `StateEquals` — is exactly the extension seam for your gates. The SDK also does trace-based evaluation with telemetry capture (the in-memory exporter pattern from the quickstart) — which is how evaluators see *what the agent did*, not just what it said.

The plan's sketch, mapping Week 6's `expected` block onto custom gates:

```python
from strands_evals import Case, Experiment
from strands_evals.evaluators import ToolCalled, Contains
from evals.evaluators.gates import ExpectedToolsGate, ArgConstraintGate, FailureBehaviorGate, NoToolGate

cases = load_cases("datasets/synthetic/tool-calling-100.jsonl")
evaluators = [ExpectedToolsGate(), ArgConstraintGate(), FailureBehaviorGate(), NoToolGate()]
experiment = Experiment(cases=cases, evaluators=evaluators)
report = await experiment.run_evaluations_async(run_specimen)   # replays via mock registry
report.run_display()
```

Your four gates implement the row's `expected` block: right tools, right call counts, arg constraints satisfied, forbidden tools untouched, failure-injection rows produce the taxonomy-required behavior, no-tool rows stay tool-free. `run_specimen` is the task function — it runs Week 7's pinned specimen (mock registry behind it) and returns/emits what evaluators need.

### Gate design: one claim, binary verdict, evidence attached

Rules that keep gates trustworthy:

- **One gate, one claim.** `ExpectedToolsGate` answers only "were the selected tools ⊆/⊇ what the row demands, within call bounds?" Argument fidelity is a different gate. Compound gates produce compound failures nobody can read.
- **Verdict + evidence, not verdict alone.** A failing gate emits *which* constraint failed, expected vs observed (`expected minCalls=2, observed 1 call to weather.get_current_weather`). Week 9's labelers and your own debugging live on these payloads.
- **Gates read normalized traces, not SDK internals.** The `execution-trace.schema.json` shape is the harness's input contract — that's what makes gates stable across SDK upgrades and lets Week 13 re-run them over traces from a *deployed* agent unchanged.
- **Gate error ≠ gate fail.** A gate that throws (malformed trace, unknown tag) must surface as an *error*, loudly distinct from a fail verdict. Errors mean the instrument broke; fails mean the agent misbehaved. Conflate them and neither number means anything.
- **Gates are code; buggy gates are worse than no gates.** Each gate gets unit tests against synthetic traces engineered per verdict — including at least one test that would catch an always-pass implementation (the most common real-world gate bug, and invisible in green CI by construction).

### The "without cloud calls" design decision you must make explicitly

The objective says CI runs *deterministically, without cloud calls* — but the specimen's mocked lane still calls the real model (Bedrock) to decide tool use. Both can't be literally true in one process, so decide the harness's architecture deliberately. Two clean resolutions exist:

1. **Two-stage harness.** Stage A (*generate*): run the specimen (model + mocks) to produce normalized traces — needs Bedrock, runs locally or nightly. Stage B (*gate*): evaluate traces against rows — a pure function, milliseconds, no network. PR CI runs stage B over committed regression traces plus dataset/schema validation; full regeneration happens on your machine or a scheduled lane.
2. **Record–replay at the model boundary.** Cassette the model I/O per (manifest, row) and replay in CI, making stage A itself offline-repeatable — more moving parts, but CI can then exercise the whole loop.

The plan's Week 13 shape (PR lane = fixtures + mocks, fast and free; merge/nightly lane = live invocations) strongly suggests resolution 1 as the backbone; record–replay can arrive later if it earns its complexity. Whichever you choose, write it down in the harness README — "what exactly runs on a PR" is the first question anyone asks of a CI gate, including you in Week 13. This is a design decision that's yours (per [AGENTS.md](../../AGENTS.md)) — make it on purpose, not by drift.

### Report design: per-tag or it hides the story

One overall accuracy number is marketing. The report's unit of meaning is **per-tag and per-kind**: tool-selection accuracy *on ambiguous rows* is the number that matters; failure-behavior compliance *per failure kind* is what localizes a taxonomy violation. Three renderings of the same numbers — console text (you, iterating), JSON (machines: CI thresholds, trend tooling), Markdown (`docs/reports/`, public-safe) — generated by one `scripts/summarize_run.py` so they cannot disagree. Every report carries its run-manifest fields (the join key) and the honesty footer: *mechanical contract compliance only; response quality is out of scope until human labels exist (Week 9).*

### Baseline ×3, then the sensitivity check

Before trusting the harness, two experiments:

1. **Stability:** run three times under the same manifest — identical results required (your Week 6/7 canonical-field definition makes "identical" precise). Anything that flickers is either an unpinned input or a volatile field misclassified as canonical — find it now.
2. **Sensitivity:** flip one system-prompt word (or one docstring word — Week 7 Exercise 3 already staged this), rerun, and watch which gates move. A harness where nothing moves isn't measuring the agent; one where *everything* moves is measuring noise. This check is your first evidence the instrument points at the thing you built it to watch — screenshot it; the Week 8 report cites it.

## Build steps

### 1. Build `evals/harness.py` on `strands-agents-evals` primitives

Load Cases from the Week 6 dataset; implement the four custom gates (extending the SDK's `ToolCalled`/`Equals`/`Contains` family) so the full `expected` block is enforced: expected tools within call bounds, arg constraints, forbidden tools untouched, failure-injection rows produce taxonomy-required behavior, no-tool rows stay tool-free. Wire `run_specimen` to the Week 7 pinned configuration over the mock registry.

### 2. Report per-tag and per-kind, not just overall

A blended average hides the ambiguous-row number that matters. Emit text (console), JSON (machine), and Markdown (docs/reports) — same numbers, three renderings, via `scripts/summarize_run.py`.

### 3. Wire the harness into GitHub Actions on every PR

Mocked lane only — fast, free, deterministic (per your stage-A/stage-B decision above). Keep unlabeled-quality questions out of scope: the harness validates *mechanical* contract compliance; response *quality* waits for human labels (Week 9). Say so in the report footer.

### 4. Baseline and sensitivity-check

Run three times, confirm identical results; then flip one system-prompt word and watch which gates move. That sensitivity check is your first evidence the harness measures the agent, not the harness.

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

## Gotchas & drift watch

- **Async/sync API surface:** the plan's sketch uses `run_evaluations_async`; the SDK also documents synchronous `run_evaluations`. Check the installed version's signatures (and pin `strands-agents-evals` in the manifest) before copying either form.
- **Evaluator interface drift:** the evals SDK is younger than the core SDK; the deterministic evaluator family (`Equals`, `Contains`, `ToolCalled`, `StateEquals`) was verified 2026-07-07, but subclassing seams (what a custom evaluator receives — output only, or trace context?) should be read from the current evaluators docs, not assumed from this file.
- **Don't let the harness re-implement the adapter.** If evaluators need trace data, they read the Week 7 normalized shape. The moment a gate parses raw SDK objects directly, you have two normalization paths that will disagree silently.
- **The committed baseline is a fixture — treat changes as reviewed diffs.** A PR that changes baseline numbers should *show* it (the JSON diff in review), not overwrite it in a drive-by commit. This is Week 13's regression discipline arriving early in social form.
- **Latency/timeout gates on mocks measure the mocks.** Timeout *behavior* (agent-side handling) is testable with scripted-delay fixtures; timeout *rates* are not meaningful in the mocked lane. Keep the report from implying otherwise — a column that only means something in Week 12's real-API lane shouldn't appear in the mocked report.
- **Minutes, not hours.** The success criterion ("runs in minutes") is a design constraint: if stage A (model calls) is in your PR path, you've likely chosen wrong upstream. Fast gates get run; slow gates get skipped, then deleted. Speed is a correctness feature of CI.

## Deliverable checklist — Local Evaluation Harness

- [ ] `evals/harness.py` + custom gate evaluators with unit tests.
- [ ] Reports in text/JSON/Markdown with per-tag breakdowns; committed baseline report.
- [ ] CI workflow running dataset validation + harness on PRs.
- [ ] Sensitivity-check note (what moved when the prompt changed).

## Success criteria

- [ ] Harness runs the 100-row dataset locally in minutes, offline, deterministically.
- [ ] Baseline metrics recorded: overall + per-tag tool-selection accuracy, execution success rate, failure-behavior compliance, no-tool compliance.
- [ ] A deliberately broken tool description produces a visibly worse report (proven, screenshotted).

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07.

- [Strands Evals quickstart](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/) — Case/Experiment lifecycle, task functions, telemetry capture, credentials; the harness skeleton is this page.
- [Strands Evals deterministic evaluators](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/deterministic_evaluators/) — `Equals`, `Contains`, `ToolCalled`, `StateEquals` semantics and parameters; your gates extend this family and should match its conventions.
- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — re-reference for what trace context evaluators can see.
- Metrics definitions: every number your report emits is defined once in [Appendix B — Metrics Glossary](../../LEARNING_PLAN.md#appendix-b--metrics-glossary); link report columns to it rather than redefining.

## Self-check

1. State the gates-vs-judges division of labor in one sentence each, and name the report element that announces it.
2. Why must gate *error* be distinguishable from gate *fail*? Give the concrete scenario where conflating them corrupts a week-over-week comparison.
3. Describe your stage-A/stage-B architecture and justify what runs on a PR. What exactly would a PR-lane green checkmark *not* tell you?
4. Your overall selection accuracy is 96%, ambiguous-tag accuracy is 60%. What does the blended number conceal, and which report design choice prevents the concealment?
5. In the sensitivity check, nothing moved. List the three hypotheses in the order you'd test them.
6. Why do the harness gates read the normalized trace schema instead of Strands objects, and which two later weeks does that choice directly pay off?
