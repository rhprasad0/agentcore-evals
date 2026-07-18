# Week 8 — Local Harness Closeout

**Phase:** Foundation closeout · **Specimen:** Week 7's exact 62-case weather projection
**Prerequisite:** Week 7 closed with 60 valid canonical traces and two explicit instrument-error receipts.

[← Week 7](week-07-specimen.md) · [Week index](README.md) · [Next: Week 9 →](week-09-human-labeling.md)

## Objective

Close the existing Strands Evals integration with one provenance-accounted, fixture-backed Stage B run. Produce a canonical aggregate and readable receipt without calling a model, tool, network endpoint, or developer-local cache.

This week is not a new harness design. The implementation already has the Case adapter, four deterministic gates, exact fixture publication/preflight, Stage B replay, report schema/renderer, and focused tests. The job now is to run the path, inspect the output, record the baseline, and stop.

## Existing implementation

- `evals/adapters/cases.py` maps the frozen `weather-only-62@1.0.0` projection without rewriting expectations.
- `evals/evaluators/gates.py` implements expected-tools, argument-constraint, failure-behavior, and no-tool gates.
- `evals/fixtures/weather-only-62/` contains 60 canonical traces, two instrument-error receipts, and a hash/provenance manifest.
- `evals/harness.py` rejects stale, partial, malformed, or cross-experiment evidence before constructing a Strands Experiment.
- `evals/reporting.py` and `scripts/summarize_run.py` render one aggregate under `schemas/eval-report.schema.json`.
- Focused coverage lives in `tests/test_week_08_cases.py`, `tests/test_week_08_gates.py`, `tests/test_week_08_harness.py`, `tests/test_week_08_reporting.py`, and `tests/test_week_08_strands_evals_sdk_contract.py`.

The two instrument-error receipts are not agent failures and never enter behavioral denominators. The remaining 60 cases are the evidence-valid population. This is weather-only coverage, not the full 100-row portfolio.

## Build steps

### 1. Re-run the focused path

Use the locked environment. Run the five Week 8 test modules and the fixture-backed Stage B/report command documented by `scripts/summarize_run.py`. Keep AWS credentials unavailable and metadata lookup disabled for the offline path.

Do not add another fixture format, cache, adapter, evaluator family, mutation matrix, or workflow. If the existing path fails, fix the narrow defect that blocks this closeout.

### 2. Inspect the canonical aggregate

Confirm it names:

- 62 projected outcomes;
- 60 evidence-valid traces;
- two instrument errors;
- zero silent case loss;
- gate pass/fail/error counts and explicit denominators; and
- overall plus existing per-tag/per-kind mechanics metrics.

The Markdown view must be derived from the same aggregate and retain the honesty boundary: **mechanical contract compliance only; response quality has not yet been judged by humans.**

### 3. Preserve one receipt

Keep the canonical JSON and Markdown at:

- `docs/reports/week-08-stage-b-replay.json`
- `docs/reports/week-08-stage-b-replay.md`

Verify both pass the report allowlist and do not expose raw prompts, responses, tool values, private paths, credentials, account/resource identifiers, or raw diagnostics.

### 4. Close the week and stop

Record the exact command, locked SDK version, fixture manifest identity/hash, counts, and result. Then move to the eight-row human expectation sheet. Do not run the removed three-baseline/three-changed sensitivity campaign.

## Deliverable checklist

- [x] Exact 62-case projection-to-Case adapter and four deterministic gates.
- [x] Provenance-linked fixture set with 60 traces and two explicit error receipts.
- [x] Fixture-only Stage B preflight and replay with tested live-dependency denials.
- [x] Schema-backed canonical JSON and Markdown renderers.
- [ ] One freshly verified baseline receipt with exact command/version/hash/counts recorded.

## Integrated success check

From the locked environment, one bounded command sequence proves all of the following:

1. the five focused Week 8 test modules pass;
2. Stage B accounts for all 62 outcomes without model, tool, credential, cache-miss, or network fallback;
3. repeated rendering of identical evidence produces the same canonical aggregate; and
4. the two committed report files validate and contain only allowlisted fields.

If any item fails, Week 8 remains open. A broad refactor is not an acceptable substitute for fixing the failing path.

## Docs to consult

- [Strands Evals quickstart](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/)
- [Custom evaluators](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/custom_evaluator/)
- [Result caching](https://strandsagents.com/docs/user-guide/evals-sdk/how-to/result_caching/)
- [Metrics glossary](../../LEARNING_PLAN.md#appendix-b--metrics-glossary)

## Self-check

1. Why are the two instrument errors excluded from behavioral denominators but still visible in the report?
2. What exact preflight behavior prevents an offline fixture miss from turning into a model call?
3. What does this 62-case baseline prove, and what response-quality claim remains unavailable until Week 9?