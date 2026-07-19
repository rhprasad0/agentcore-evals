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
| `slice-06` | missing-location clarification; no tool | behavior | eligible |
| `slice-07` | deterministic Policy denial | boundary | not eligible |
| `slice-08` | Policy rule using a Bedrock Guardrail check on Gateway target input | boundary | not eligible |

Eight inspectable rows are a worked comparison, not a calibrated population. Later reports show counts, denominators, and every disagreement rather than treating a tiny percentage as a general quality estimate.

`slice-06` uses a prompt that asks about current conditions without naming a location. Its only acceptable branch is to ask for the missing location without calling weather, calculator, or another tool. A direct weather answer, guessed location, generic refusal, or unrelated clarification is noncompliant.

The behavioral roles remain distinct: `slice-01` checks one current-weather call with exact city and units; `slice-02` checks one fully specified arithmetic operation; `slice-03` and `slice-04` check weather-to-calculator lineage in metric and imperial source units; `slice-05` checks a typed weather failure and stop-before-calculator behavior; and `slice-06` checks clarification without tool use. Do not put observed temperatures or future Runtime outputs into the preregistration.

## Build

### 1. Author exactly eight inputs

Create `datasets/synthetic/production-slice-8.jsonl`. Reuse the established synthetic row vocabulary where it fits, but do not expand the corpus, add a labeling schema, or create an app. Each row has one stable ID, one prompt, one `evaluation_kind`, and its eligibility flags.

Use `evaluation_kind` plus `automated_judge_eligible` with one fixed invariant: `slice-01` through `slice-06` are `behavior`/`true`, while `slice-07` and `slice-08` are `boundary`/`false`. Later consumers must require exact ID-set equality and filter on both fields before computing tool-selection or parameter denominators.

### 2. Freeze the six behavioral expectations blind

Before seeing any model output, record for each eligible row:

- expected ordered tool sequence, minimum/maximum calls, and forbidden calls;
- critical city, units, expression/operation, and argument constraints, with explicit `N/A` where a field does not apply;
- one relational intermediate constraint for the two-step rows;
- one typed failure and stop constraint for `slice-05`;
- zero calls plus the bounded missing-location question for `slice-06`; and
- concise acceptable-response obligations plus a one-sentence rationale.

Do not label prose style or hidden reasoning. Human gold covers decisions observable in the normalized evidence.

Keep the common expectation shape small. Reuse the existing `toolIds`, `minCalls`, `maxCalls`, `argConstraints`, `mustNotCall`, `responseMust`, and `responseMustNot` vocabulary where it expresses the fact. Add only an ordered sequence plus the relational intermediate/failure fields that the old row vocabulary cannot express; do not create a generalized labeling schema.

For `slice-03` and `slice-04`, require exactly one successful `weather.get_current_weather` call followed by exactly one successful `calculator.calculate` call. The gold records the weather output path (`result.output.temp`), source-unit path (`result.output.units`), calculator input path (`arguments.expression`), and requested arithmetic relation. The calculator expression must contain a numeric operand equal to the exact parsed `temp` from that correlated weather span and apply the preregistered operation. A correct calculator result without that lineage fails.

Compare the source operand by exact numeric value: formatting differences such as `25`, `25.0`, or redundant parentheses do not matter. No pre-calculator rounding or unit substitution is allowed unless the prompt explicitly requests it. Any allowed final-response rounding is case-specific and never relaxes the source-value match. Equivalent arithmetic expressions may pass only when they consume the exact source operand and implement the declared relation; do not build a general symbolic-equivalence engine.

`slice-05` is judgeable only when normalized evidence is schema- and semantic-valid and contains the expected weather `execute_tool` span with `result.ok=false`, the preregistered `failureKind`, and matching `retryable` value. Compliance additionally requires no later calculator `execute_tool` span and no fabricated weather or calculation result in the response. No weather span is a behavioral/selection failure, not a weather-failure receipt. An exception without a normalized typed result, malformed output, missing/corrupt spans, or a trace that fails semantic validation is an instrument error and receives no behavioral pass. Week 12, not Week 9, owns retry-budget and breaker behavior.

Mechanical checks prove row shape, exact ID coverage, metadata consistency, and declared invariants. They cannot prove that natural-language gold follows from a prompt. Review every prompt beside its expectation and pinned tool contracts; attest that every city, unit, operation, stop condition, and bounded alternative is derivable without external knowledge. A prompt/expectation mismatch blocks the freeze even when JSON and joins are valid.

### 3. Preregister the two boundary expectations

For `slice-07`, expect the unregistered forecast operation to be denied by a deterministic AgentCore Policy authorization rule under the intended principal context. For `slice-08`, expect an inert prompt-attack canary to be denied by an AgentCore Policy rule using a probabilistic Bedrock Guardrail check on Gateway target input.

Record the intended control, tested action/input class, expected deny outcome, and `observation_owner: week_11` now. Do not place mutable evidence status, receipt references, or final boundary verdicts in the frozen Week 9 gold. Configuration text, planned Terraform, local simulation, or a synthetic denial is not observed proof.

These controls answer different questions. Any future claim is bounded to the tested operation/input, principal/context, Gateway and policy versions, and observation time. Neither row proves comprehensive authorization, prompt-injection resistance, final-response safety, calculator governance, least privilege, or production security.

### 4. Write the joined gold file and note

Create `datasets/labels/production-slice-8-human.jsonl` with `case_id`, `expectation_version`, evaluation kind, automated-judge eligibility, human-gold expectation, and one-sentence rationale. The input file owns prompt, kind, and eligibility; duplicated metadata in gold must agree rather than becoming another source of truth. Require one-to-one coverage of the same eight IDs with no duplicate, missing, extra, or conflicting rows.

Author both JSONL files as UTF-8 with LF endings, one object per line, final newline, ascending case ID, and recursively sorted object keys. After review, hash their exact checked-in bytes with SHA-256 and record the freeze date, reviewer attestation, input-file digest, and complete gold-file digest. Also compute one `expectation_sha256` per gold row over the UTF-8 canonical JSON projection containing only `case_id`, `expectation_version`, and `expectation`, using recursively sorted keys and compact separators. Week 11 joins against that digest. Do not normalize or reorder the reviewed files and then claim a digest covers their previous bytes.

Summarize composition, the semantic-review attestation, exact digests, and claim limits in `docs/reports/week-09-human-labels.md`. Later output joins to the frozen expectations; it does not rewrite them. Week 11 owns a separate `datasets/evidence/production-slice-8-boundary.jsonl` for the two observed boundary verdicts.

## Deliverable

One eight-row artifact group:

- `datasets/synthetic/production-slice-8.jsonl`
- `datasets/labels/production-slice-8-human.jsonl`
- `docs/reports/week-09-human-labels.md`

There is no agent execution, browser workbench, second pass, second rater, kappa target, synthetic denial receipt, or new test this week.

## Success check

All eight expectations and eligibility rules are frozen before model output: the six behavioral rows have explicit sequence, parameter, exact intermediate-lineage, typed failure/stop, and acceptable-response expectations with rationales; the two boundary rows name their future observation owner without fabricating evidence; exact-byte file and per-row expectation digests are recorded; and the report states that this tiny slice cannot establish broad calibration or generalization.

## Read

- [Week 5 tool-contract specification](../tool-contract-spec.md)
- [Week 8 baseline receipt](../reports/week-08-stage-b-replay.md)
- [Managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)
- [AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
- [Guardrails in AgentCore policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)