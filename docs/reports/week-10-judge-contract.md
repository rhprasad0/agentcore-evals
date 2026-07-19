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
{"eligibleCaseIds":["slice-01","slice-02","slice-03","slice-04","slice-05","slice-06"],"excludedCaseIds":["slice-07","slice-08"],"providerTouched":false,"renderedCaseIds":["slice-01","slice-02","slice-03","slice-04","slice-05","slice-06"],"renderedRequestSha256":{"slice-01":"ef9f4a6fbfe8f2de00f1571fbb0564c0020072c779e4097e92b6fa69768ec2e1","slice-02":"c659bf168381615a099ba16743ebe9acd4eb27c38a8a006963a8ea8fe7cf1543","slice-03":"cd0da59260526b92d2d370365ef42904ef3553a576a9bc434d88d5b092535710","slice-04":"aaaa3bf9d05f4f1d78e54787511523913f39ae5ded3a9c7c1227a262c56c2772","slice-05":"a6439b4f57b53b7f1f31e8671dc6665f8e4ae0e743eb8f0c4d9e96bb36687432","slice-06":"ffba3da56d98246dbed49235364545d7eb6be2e73fb56f445a64e656e9527e76}}
```

## Calibration and held-out local evaluation

The calibration pack contains six disjoint synthetic evidence vectors: three reviewed pass labels and three reviewed fail labels. The intended held-out experiment is one local two-tool Strands run over exactly `slice-01` through `slice-06`, using the frozen custom evaluator plus `ToolSelectionAccuracyEvaluator` and `ToolParameterAccuracyEvaluator`.

The explicitly authorized live calibration command was attempted on 2026-07-19. It was blocked while obtaining AWS credentials: the configured AWS session was expired and the Python credential provider also reported the missing `botocore[crt]` login-provider dependency. The failure occurred while constructing the Bedrock client, before a Bedrock inference request; no calibration verdicts or held-out results exist.

**Required operator action:** refresh the local AWS session with `aws login` and make the login credential provider available to the locked environment, then rerun the calibration command once and save its sanitized JSON output as a receipt. The held-out command requires that receipt and rejects any missing, incomplete, mismatched-model, or mismatched-rubric calibration result.

## Claim boundary

This is local pre-deployment evidence, not AgentCore deployment evidence or a calibration/reliability claim. It does not test Runtime packaging, Gateway/Identity injection, Policy/Guardrail behavior, AgentCore Evaluations ingestion, or live weather access. Week 14 remains the only same-evidence deployed Runtime comparison.
