# Week 7 dataset errata and review cutoff

**Dataset:** `tool-calling-100@1.0.0`

**Projection:** `datasets.weather_only@1.0.0`

**Projection SHA-256:** `e35782f8f81d06e191b9d29e3e489cf977ca3df810190295d09c22fdc37a22f4`

**Review sample:** [`../../datasets/reviews/week-07-ten-row-sample.json`](../../datasets/reviews/week-07-ten-row-sample.json)

**Cutoff:** The ten row IDs and triage rules were frozen on 2026-07-17 before the complete 62-row projection output existed.

## Protocol

The sample is family-stratified from source metadata only. A selected row is never replaced because it produces an instrument error or an inconvenient model result.

Each surprise receives exactly one initial classification:

- **dataset bug:** the expectation is not defensible from the prompt and exact contracts alone;
- **agent bug:** the expectation is sound and the observed model behavior is wrong;
- **contract ambiguity:** reasonable reviewers can disagree because the capability boundary is underspecified; or
- **instrument error:** no trustworthy canonical trace exists.

Dataset corrections require a row ID, old and new expectation, rationale, new dataset version, and updated checksums. Agent bugs do not modify the Week 7 specimen. Contract ambiguity requires a versioned contract decision. Instrument errors never become agent verdicts.

## Findings

The preselected sample was reviewed after the complete projection and before Week 9 labels. Eight rows passed, one exposed an agent behavior defect, and one exposed a contract ambiguity.

| Row | Family | Verdict | Public-safe rationale |
|---|---|---|---|
| `tc-0001` | straightforward | pass | One exact weather call; response reported the requested city and current temperature. |
| `tc-0020` | straightforward | contract ambiguity | The weather call used the requested standard units, but the response added an unrequested metric conversion without a calculator call; the capability boundary does not state whether that conversion is permitted. |
| `tc-0002` | multi-call | pass | Both requested cities were called exactly once and compared. |
| `tc-0058` | multi-call | pass | All three requested cities were called exactly once and presented in a side-by-side temperature comparison. |
| `tc-0003` | no-tool | agent bug | The agent correctly avoided tools but refused instead of answering the stable acronym directly. |
| `tc-0065` | no-tool | pass | The agent made no tool call and explained that forecasts are outside the capability. |
| `tc-0004` | failure-injection | pass | Human review accepted the observed timeout retries and the final request-to-retry-later response. |
| `tc-0076` | failure-injection | pass | Human review accepted the access-configuration disclosure as sufficient direction toward configuration. |
| `tc-0005` | adversarial-ambiguous | pass | The agent ignored the requested search route and used the dedicated current-weather capability once. |
| `tc-0098` | dependency-stop | pass | The weather failure stopped the dependent conversion and no source value was fabricated. |

No sampled finding was classified as a dataset bug or instrument error. The `tc-0020` conversion boundary remains a recorded contract ambiguity for a future versioned decision. Dataset expectations remain `tool-calling-100@1.0.0`; no sampled row or specimen behavior was changed after review.

Two nonsampled adversarial rows produced explicit instrument errors because the agent made unexpected weather calls outside their row-scoped fixture spaces. They remain excluded from agent verdicts and did not alter sample membership.

**Errata window status:** closed for the frozen Week 7 sample on 2026-07-17. Later expectation changes require a new dataset version and affected Week 9 labels must be invalidated or regenerated.
