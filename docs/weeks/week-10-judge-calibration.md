# Week 10 — One Frozen Custom-Judge Contract

**Prerequisite:** Week 9's eight human expectations are reviewed and frozen. No final Runtime evidence exists yet.

[← Week 9](week-09-human-labeling.md) · [Week index](README.md) · [Next: Week 11 →](week-11-gateway-weather.md)

## Concept

A judge is useful only when its question and rubric exist before the evidence it will score. This week defines one custom judge for the six behavioral rows, proves its input/output plumbing locally, and freezes it. The only model-backed custom-judge execution happens in Week 14 over the same six Runtime spans sent to AgentCore Evaluations.

The judge is a sanity-check lane, not a new source of truth. One run over six cases cannot establish stability, calibration, false-rate estimates, or generalization. Policy and Guardrail denials are infrastructure outcomes and remain explicitly ineligible.

## Build

### 1. Define one normalized input

Create `scripts/judge_weather_calculator.py`. It accepts one case ID plus the normalized evidence needed to judge tool selection and parameters: available model-visible tools, user request, observed tool sequence, normalized arguments, and the critical intermediate value when the case is two-step.

Do not expose infrastructure-denial evidence to the model judge. The script must reject duplicate, unknown, or ineligible case IDs before any model path is reachable.

### 2. Freeze one rubric and structured verdict

Keep the prompt in the script, readable in one screen. Ask only:

- did the observed tool sequence fit the request and human-gold constraints;
- were critical parameters and intermediate values faithful; and
- which compact evidence code explains a disagreement.

Return a structured verdict with `case_id`, `selection_verdict`, `parameter_verdict`, `evidence_codes`, and a bounded rationale. Version the prompt once in the report. Do not add a prompt registry, evaluator hierarchy, output-manifest system, or second execution-quality judge.

### 3. Build a model-free dry run

`--dry-run` loads the frozen human-gold file, accounts for all eight IDs, excludes the two boundary IDs, validates the six normalized inputs, and renders the exact model request without calling Bedrock or another provider. A canned structured response may exercise parsing; it is not a judge result.

The dry-run receipt must make the absence of a model call inspectable—for example, a provider callable that raises if touched plus captured command output.

### 4. Review, report, and freeze

Create `docs/reports/week-10-judge-contract.md` containing:

- the human-gold fields the judge may inspect;
- exact verdict fields and rubric;
- six eligible IDs and two ineligible boundary IDs;
- the dry-run receipt; and
- the sentence: “One future run over six cases is a same-evidence sanity check, not robust calibration.”

After review, record the script/prompt digest and do not tune it against Week 13 outputs. Week 14 may fix only a mechanical blocker, with the change disclosed before scoring.

## Deliverable

One frozen judge-contract artifact group:

- `scripts/judge_weather_calculator.py`
- `docs/reports/week-10-judge-contract.md`
- the reused `datasets/labels/production-slice-8-human.jsonl`

There is no Week 10 model call, repeat-run campaign, holdout split, trust-policy document, or new test.

## Success check

The dry run accounts for all six judge-eligible IDs, excludes the two boundary IDs, validates and renders the frozen rubric without a model call, records the prompt/script digest, and leaves exactly one metered custom-judge execution for Week 14.

## Read

- [Amazon Bedrock Converse tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-inference-call.html)
- [AgentCore built-in prompt templates](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/prompt-templates-builtin.html)
- [Week 9 human gold](week-09-human-labeling.md)
- [Managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)