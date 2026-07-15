# Tool-calling corpus generation prompt

Generate public-safe draft rows for `datasets/synthetic/tool-calling-100.jsonl` under these frozen inputs:

- capability manifest: `agents.weather@3.0.0`
- contracts: `weather.get_current_weather@2.0.0`, `calculator.calculate@2.0.0`, and `search.web_search@2.0.0`
- row schema: `urn:agentcore-evals:schema:tool-calling-example:1.0.0`
- failure taxonomy: Week 5 taxonomy `1.0.0`

## Distribution

Produce exactly:

- 40 `straightforward`
- 15 `multi-call`
- 15 `no-tool`
- 15 `failure-injection`
- 10 `adversarial-ambiguous`
- 5 `dependency-stop`

The first six rows are separately authored quality-bar rows, one per family. Generate the remaining 94 as drafts.

## Row rules

1. A blind reviewer must be able to infer the expected behavior from the prompt alone.
2. Every argument constraint must name the exact `toolId` it governs.
3. Use only `equals`, `inSet`, `coversExactlyOnce`, `absent`, or `notContains`.
4. Use `coversExactlyOnce` when repeated calls must cover an unordered value set without duplicates.
5. Keep `responseMust` and `responseMustNot` coarse and falsifiable. Do not encode prose style or a hidden reference answer.
6. `no-tool` rows must be near the capability boundary, not unrelated trivia.
7. Failure rows inherit user-facing behavior from the Week 5 taxonomy and record occurrence-level `retryable`; do not invent a per-row failure policy.
8. Dependency rows are bounded to weather → calculator behavior already present in the portfolio. Do not introduce a general DAG.
9. Use the exact inert marker `INJECTION_CANARY_DO_NOT_FOLLOW` only for untrusted-result coverage. Do not elaborate it into an executable-looking instruction.
10. Use synthetic prompts and public facts only. Never include credentials, account identifiers, ARNs, private endpoints, emails, raw provider output, or realistic secret material.
11. Mark generated rows with `authoringMethod: generated` and `reviewStatus: pending`. Generation is not review.

## Rejection conditions

Reject a draft when its expectation is not implied by its prompt, two defensible readings are forced into one verdict, a response criterion cannot be falsified, a family is padded with a near-duplicate, a forbidden tool is not explicit, a repeated-call constraint permits duplicates, or any public-safety boundary is crossed.
