# Week 10 — Judge Contract and Pre-deployment Evaluation Receipt

**Status:** provider-free contract, calibration freeze, and held-out local Strands execution complete.

## Contract

- **Frozen behavioral rows:** `slice-01` through `slice-06`
- **Excluded boundary rows:** `slice-07`, `slice-08`
- **Judge model:** `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- **Rubric version:** `v1`
- **Judge script SHA-256:** `1f57057e095961742bbfdc4e8c9a5c62f14819b90f7b3ee9e315ff7f74e86149`
- **Calibration-pack SHA-256:** `3d55f86fc7bfd4bdbe751834c00fbbcc2967f180e1f7cdfe11131c78f03e7b24`

The custom judge sees only a case ID, expectation, user request, ordered normalized calls, arguments, and normalized result/failure envelope. Its verdict is bounded to `case_id`, selection verdict, parameter verdict, compact evidence codes, and a 240-character rationale.

## Provider-free dry run

Command:

```bash
uv run --locked python -m scripts.judge_weather_calculator --dry-run
```

Receipt:

```json
{"eligibleCaseIds":["slice-01","slice-02","slice-03","slice-04","slice-05","slice-06"],"excludedCaseIds":["slice-07","slice-08"],"providerTouched":false,"renderedCaseIds":["slice-01","slice-02","slice-03","slice-04","slice-05","slice-06"],"renderedRequestSha256":{"slice-01":"015250c12ac9a30cd3386b04c2ff38db99a9d7f00ef03047f9aec6ecd2745a2f","slice-02":"9947e27feabb9555cbee53d023f9691f0739fff132e094f2a4f397768ecc6306","slice-03":"95eca390faf029357d4e8cced26744ef8df20b4c114c2f737b650db9f4d6d1dc","slice-04":"9e7c35b7220d67eb390b7190e53a94a70ed6ae97389e232c05cf06dd6a3ea9a0","slice-05":"e2a45ee2cc3f1aec71acda61b2fb7dbe730b681281f5d1f4bc6c28a3f1719bf5","slice-06":"06821ea69a1ada171c12bcb314d62ccd6e0ed465c7b415cd0f75b27df686f6a6"}}
```

## Calibration and held-out local evaluation

The calibration pack contains six disjoint synthetic evidence vectors: three reviewed pass labels and three reviewed fail labels. The intended held-out experiment is one local two-tool Strands run over exactly `slice-01` through `slice-06`, using the frozen custom evaluator plus `ToolSelectionAccuracyEvaluator` and `ToolParameterAccuracyEvaluator`.

Candidate `v1` stopped on its first provider response because the prompt requested compact evidence codes without enumerating the parser's finite code set. No calibration label was accepted and no held-out case ran. Candidate `v2` was the single permitted mechanical revision: it names that existing finite code set in the prompt.

After refreshing the local AWS session, candidate `v2` ran the six-vector pack once. All six labels matched the human labels; the frozen receipt is [`docs/receipts/week-10-calibration.json`](../receipts/week-10-calibration.json).

The held-out command requires this receipt and rejects any missing, incomplete, mismatched-model, or mismatched-rubric calibration result.

## Held-out local results

The first held-out receipt is retained as [`invalid evidence-shape output`](../receipts/week-10-heldout.json): the custom adapter supplied `result.content` where the frozen conversion expectations require `result.output.*`. The normalized retry is also retained as [`invalid fixture-coverage output`](../receipts/week-10-heldout-normalized.json): `tc-0006` and `tc-0097` lacked their exact row-scoped weather success fixtures. After restoring those fixtures, the separately labeled [`fixture-covered receipt`](../receipts/week-10-heldout-fixture-covered.json) records a custom-judge match on all six behavioral rows. `slice-06` remains `not_applicable` for the two built-in tool lanes. The built-in evaluators still expose a separate reporting discrepancy on the conversion rows: their labels are `Yes`, but one or both lane scores are `0.5` with `testPass: false`. Treat that as evaluator-semantics evidence, not an agent failure or a reason to retune the frozen judge.

## Claim boundary

This is local pre-deployment evidence, not AgentCore deployment evidence or a calibration/reliability claim. It does not test Runtime packaging, Gateway/Identity injection, Policy/Guardrail behavior, AgentCore Evaluations ingestion, or live weather access. Week 14 remains the only same-evidence deployed Runtime comparison.
