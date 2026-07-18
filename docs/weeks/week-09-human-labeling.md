# Week 9 — Human Gold for the Final Production Slice

**Prerequisite:** Week 8 closed with one verified 62-case deterministic baseline. Do not run the final agent before this week's expectations are frozen.

[← Week 8](week-08-local-harness.md) · [Week index](README.md) · [Next: Week 10 →](week-10-judge-calibration.md)

## Concept

Human gold is a preregistered expectation, not a reaction to model output. This week defines the only eight new cases used by the final vertical slice. The first six describe agent behavior and may later be compared across human, custom-judge, and managed-evaluator lanes. The last two describe infrastructure enforcement and receive boundary verdicts only.

| ID | Case | Evaluation kind | Automated-judge eligibility |
| --- | --- | --- | --- |
| `slice-01` | weather only | behavior | eligible |
| `slice-02` | calculator only | behavior | eligible |
| `slice-03` | metric weather→calculator | behavior | eligible |
| `slice-04` | imperial weather→calculator | behavior | eligible |
| `slice-05` | weather failure stops before calculator | behavior | eligible |
| `slice-06` | no-tool or clarification | behavior | eligible |
| `slice-07` | deterministic Policy denial | boundary | not eligible |
| `slice-08` | native Gateway guardrail denial | boundary | not eligible |

Eight inspectable rows are a worked comparison, not a calibrated population. Later reports show counts, denominators, and every disagreement rather than treating a tiny percentage as a general quality estimate.

## Build

### 1. Author exactly eight inputs

Create `datasets/synthetic/production-slice-8.jsonl`. Reuse the established synthetic row vocabulary where it fits, but do not expand the corpus, add a labeling schema, or create an app. Each row has one stable ID, one prompt, one `evaluation_kind`, and its eligibility flags.

The two-step rows must make the intermediate value observable: weather returns a temperature in the requested source unit, and calculator receives that exact value for the requested transformation. The failure row requires the calculator not to run after weather fails.

### 2. Freeze the six behavioral expectations blind

Before seeing any model output, record for each eligible row:

- expected tool sequence and call bounds;
- critical city, units, expression, and intermediate-value constraints;
- the stop condition, when applicable; and
- a concise range of acceptable final behavior.

Do not label prose style or hidden reasoning. Human gold covers decisions observable in the normalized evidence.

### 3. Preregister the two boundary expectations

For `slice-07`, expect the unregistered forecast operation to be denied by deterministic AgentCore Policy. For `slice-08`, expect an inert prompt-attack canary to be blocked by the native Gateway guardrail policy.

Record both expectations now, but mark observed evidence and final boundary verdict `pending_week_11`. Do not fabricate a trace or infer a pass from configuration text.

### 4. Write the joined gold file and note

Create `datasets/labels/production-slice-8-human.jsonl` with case ID, evaluation kind, eligibility, human-gold expectation, evidence status, and one-sentence rationale. Summarize composition and claim limits in `docs/reports/week-09-human-labels.md`.

Hash both inputs after review. Later output may be compared with them; it may not silently rewrite them.

## Deliverable

One eight-row artifact group:

- `datasets/synthetic/production-slice-8.jsonl`
- `datasets/labels/production-slice-8-human.jsonl`
- `docs/reports/week-09-human-labels.md`

There is no agent execution, browser workbench, second pass, second rater, kappa target, synthetic denial receipt, or new test this week.

## Success check

All eight expectations and eligibility rules are frozen before model output: the six behavioral rows have explicit sequence, parameter/intermediate-value, stop, and acceptable-response expectations with rationales; the two denial rows remain visibly pending rather than fabricated; and the report states that this tiny slice cannot establish broad calibration or generalization.

## Read

- [Week 5 tool-contract specification](../tool-contract-spec.md)
- [Week 8 baseline receipt](../reports/week-08-stage-b-replay.md)
- [Managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)
- [AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)