# Week 10 — Judge Contract and Pre-deployment Evaluation Receipt

**Status:** provider-free contract complete; live calibration and held-out Strands execution blocked before inference.

## Contract

- **Frozen behavioral rows:** `slice-01` through `slice-06`
- **Excluded boundary rows:** `slice-07`, `slice-08`
- **Judge model:** `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- **Rubric version:** `v1`
- **Judge script SHA-256:** `439a3126901f2149cb3a6796fb2cc7d16e63b1728df37a11ccb5cde10629d3e5`
- **Calibration-pack SHA-256:** `3d55f86fc7bfd4bdbe751834c00fbbcc2967f180e1f7cdfe11131c78f03e7b24`

The custom judge sees only a case ID, expectation, user request, ordered normalized calls, arguments, and normalized result/failure envelope. Its verdict is bounded to `case_id`, selection verdict, parameter verdict, compact evidence codes, and a 240-character rationale.

## Provider-free dry run

Command:

```bash
uv run --locked python -m scripts.judge_weather_calculator --dry-run
```

Receipt:

```json
{"eligibleCaseIds":["slice-01","slice-02","slice-03","slice-04","slice-05","slice-06"],"excludedCaseIds":["slice-07","slice-08"],"providerTouched":false}
```

## Calibration and held-out local evaluation

The calibration pack contains six disjoint synthetic evidence vectors: three reviewed pass labels and three reviewed fail labels. The intended held-out experiment is one local two-tool Strands run over exactly `slice-01` through `slice-06`, using the frozen custom evaluator plus `ToolSelectionAccuracyEvaluator` and `ToolParameterAccuracyEvaluator`.

The explicitly authorized live calibration command was attempted on 2026-07-19. It was blocked while obtaining AWS credentials: the configured AWS session was expired and the Python credential provider also reported the missing `botocore[crt]` login-provider dependency. The failure occurred while constructing the Bedrock client, before a Bedrock inference request; no calibration verdicts or held-out results exist.

**Required operator action:** refresh the local AWS session with `aws login` and make the login credential provider available to the locked environment, then rerun the calibration command once and save its sanitized JSON output as a receipt. The held-out command requires that receipt and rejects any missing, incomplete, mismatched-model, or mismatched-rubric calibration result.

## Claim boundary

This is local pre-deployment evidence, not AgentCore deployment evidence or a calibration/reliability claim. It does not test Runtime packaging, Gateway/Identity injection, Policy/Guardrail behavior, AgentCore Evaluations ingestion, or live weather access. Week 14 remains the only same-evidence deployed Runtime comparison.
