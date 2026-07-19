# Week 10 — Calibrated Pre-deployment Strands Evaluation

**Prerequisite:** Week 9's eight human expectations are reviewed and frozen. No final Runtime evidence exists yet.

[← Week 9](week-09-human-labeling.md) · [Week index](README.md) · [Next: Week 11 →](week-11-gateway-weather.md)

## Concept

Week 10 is **evals first**: calibrate one local custom judge against a distinct human-reviewed synthetic pack, freeze the selected rubric/model, then run that same judge and Strands' tool-level evaluators over all six frozen behavioral rows before deployment.

The calibration pack is separate from `slice-01` through `slice-06`; those six remain held-out local evidence. Neither six-vector calibration nor six-case heldout evaluation establishes stability, false rates, or generalization. `slice-07` and `slice-08` are infrastructure outcomes and remain ineligible.

## Build

### 1. Keep the provider-free contract gate

`scripts/judge_weather_calculator.py --dry-run` accounts for all eight human-gold IDs, renders only the six eligible behavioral requests, and rejects the two boundary rows before any provider path. The receipt proves `providerTouched: false`.

### 2. Calibrate a bounded custom judge

`datasets/labels/week-10-judge-calibration.jsonl` contains six synthetic normalized-evidence vectors derived from non-heldout source scenarios: three known passes and three known failures. It never contains a Week 9 heldout row, raw model output, or credentials.

Run one pinned Haiku candidate against all six vectors. Record every expected-versus-actual label and the prompt/pack digest. A documented mechanical/rubric defect may receive one explicit revised candidate; do not retry until a preferred result appears. Freeze the selected digest before evaluating heldout rows.

### 3. Run all six heldout rows locally through Strands Evals

`scripts/run_week_10_predeployment_evals.py --confirm-live-bedrock --calibration-receipt <passed-receipt.json>` refuses to run until the receipt freezes the current model and rubric with all six calibration labels matched. It creates a fresh local two-tool agent per case: the custom judge evaluates exactly `slice-01` through `slice-06`; the two tool-level evaluators evaluate only rows whose expectation requires a tool call:

- the frozen `WeatherCalculatorJudgeEvaluator` adapter;
- `ToolSelectionAccuracyEvaluator`; and
- `ToolParameterAccuracyEvaluator`.

No Gateway, Identity, Runtime, Policy, Guardrail, live weather provider, search tool, or deployed span is involved. Tool-level output for `slice-06` is recorded as `not_applicable`, not a zero score.

### 4. Report claim boundaries

`docs/reports/week-10-judge-contract.md` records the dry-run receipt, calibration labels and selected digest, all six heldout case/evaluator results, model IDs, and every disagreement. It must say: “This is local pre-deployment evidence, not AgentCore deployment evidence or a calibration/reliability claim.”

## Deliverable

- `datasets/labels/week-10-judge-calibration.jsonl`
- `scripts/judge_weather_calculator.py`
- `evals/evaluators/weather_calculator_judge.py`
- `scripts/run_week_10_predeployment_evals.py`
- `docs/reports/week-10-judge-contract.md`

## Success check

The provider-free dry run accounts for all eight IDs; calibration uses only the disjoint six-vector pack and freezes one judge digest; local Strands execution evaluates all six heldout behavioral rows before deployment; and the report does not overclaim what six examples prove.

## Read

- [Strands Evals](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/)
- [Amazon Bedrock Converse tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-inference-call.html)
- [Week 9 human gold](week-09-human-labeling.md)
- [Managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)
