# Week 7 full-projection and repeatability report

**Calibration date:** 2026-07-17

## Scope

Two complete executions of `datasets.weather_only@1.0.0` used Amazon Nova Micro, unchanged specimen behavior pins, `strands-agents@1.46.0`, `strands-agents-evals@1.0.1`, and `strands-inline@1.0.0`. The executions shared one content-derived experiment identity and used distinct private run identities. Raw prompts, arguments, responses, span IDs, and run IDs remain under ignored run storage.

The frozen ten-row human-review sample and triage policy are recorded in [`../../datasets/reviews/week-07-ten-row-sample.json`](../../datasets/reviews/week-07-ten-row-sample.json). Review outcomes are recorded in [`../errata/week-07-dataset-errata.md`](../errata/week-07-dataset-errata.md).

## Pre-run instrumentation correction

The first attempted full execution exposed incomplete exact-key fixture coverage: 39 of 62 cases ended as instrument errors, all caused by `UnknownMockFixtureError`. That execution was excluded from repeatability evidence.

The corrected registry was generated solely from reviewed projection expectations and the contract's predeclared optional-unit space. Existing reviewed exact-key results were preserved. Omitted units and explicit default units receive separate exact keys, while unconstrained optional units cover all schema-valid enum values. The registry now contains 141 validated fixtures. This changed the fixture checksum and therefore produced a new experiment identity before the two compared executions.

No fixture was added for the arguments observed in rows expected to make no tool call. Those calls continue to fail closed rather than becoming post-hoc fixtures.

## Finalized outcomes

Both compared executions produced the same aggregate outcome:

| Scenario family | Cases | Canonical traces | Instrument errors | Canonical tool calls |
|---|---:|---:|---:|---:|
| straightforward | 15 | 15 | 0 | 15 |
| multi-call | 15 | 15 | 0 | 32 |
| no-tool | 13 | 13 | 0 | 0 |
| failure-injection | 12 | 12 | 0 | 16 |
| adversarial-ambiguous | 5 | 3 | 2 | 1 |
| dependency-stop | 2 | 2 | 0 | 2 |
| **Total** | **62** | **60** | **2** | **66** |

All 60 canonical traces in each execution passed the execution-trace JSON Schema and repository semantic validation. Both manifests and public-safe summaries passed their schemas.

The same two adversarial rows ended as instrument errors in both executions. Each row expected zero tool calls, but the agent attempted a weather call outside that row's exact fixture space. No canonical agent verdict was created for either row.

## Repeatability

The same-experiment comparator reported:

- 62 of 62 case statuses matched;
- 60 of 60 comparable exact tool-call sequences matched; and
- 60 of 60 comparable canonical projections matched.

This is exact agreement for these two executions at the declared comparison surfaces. It is not a general claim that the model or managed service is deterministic.

## Selection-reasoning coverage

Across each execution's 66 canonical tool calls:

- 49 had block-local pre-tool assistant text;
- 17 had `selectionReasoning: null`.

The null values occur primarily in multi-call assistant messages where one local text block precedes several tool calls. The adapter does not copy one rationale across sibling calls or infer causality.

## Frozen ten-row review

All ten preselected rows had canonical traces. Human review produced eight passes, one agent bug, and one contract ambiguity:

- one no-tool row refused instead of answering a stable acronym directly;
- one standard-unit row added an unrequested metric conversion without a calculator call, while the capability boundary did not state whether that conversion was permitted.

No sampled finding required a dataset expectation correction. The conversion ambiguity remains recorded for a future versioned contract decision. The specimen was not tuned after review.

## Claim limits

- The two instrument-error rows are not agent verdicts.
- The initial incomplete-fixture execution is calibration evidence, not part of repeatability measurement.
- Raw telemetry and model prose are not public artifacts.
- Exact agreement covers only the pinned specimen, projection, fixture registry, SDK versions, and two executions documented here.
