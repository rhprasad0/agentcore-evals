# Week 12 — Weather Reliability Boundary

**Prerequisite:** Terraform owns the Gateway path; current weather succeeds through the narrow wrapper; the deterministic Policy authorization receipt is complete; and Guardrail-in-Policy evidence is explicitly deferred under Week 11's provider gap.

[← Week 11](week-11-gateway-weather.md) · [Week index](README.md) · [Next: Week 13 →](week-13-runtime-operations.md)

## Concept

Reliability belongs at the one real external-tool boundary, not in a general framework or prompt. The wrapper owns a total deadline and one bounded retry. A dedicated DynamoDB item shares breaker state across Runtime workers. The agent must stop before calculator whenever weather fails.

Only seam-normalized timeout, network, 429, and upstream 5xx outcomes are retryable. Bad input, authentication/Identity failures, Policy denials, Guardrail blocks, other upstream 4xx outcomes, and expired deadlines fail immediately. Identity still owns only credential injection.

## Build

### 1. Put one total deadline around the Gateway call

Modify `weatheragent/app/weather_agent/gateway_weather.py` and create `weatheragent/app/weather_agent/weather_reliability.py`. Measure the happy path, choose one explicit demo deadline and backoff range, and record the latency/cost tradeoff before changing them.

Permit no more than two total provider attempts. Backoff and jitter consume the same total deadline; a retry may not start if its remaining budget cannot complete. Normalize raw Gateway/provider outcomes before the retry decision so transport details do not leak into agent behavior.

Do not create a reusable retry package or per-tool policy registry.

### 2. Add shared breaker state in DynamoDB

Extend `infra/terraform/production-demo/reliability.tf` with one on-demand breaker table and `iam.tf` with only the item operations the Runtime needs. Keep this table separate from Week 15's public quota/kill-switch table.

Use one weather-provider item with explicit states:

- `CLOSED`: count consecutive eligible provider failures;
- `OPEN`: fail fast until `open_until`;
- `HALF_OPEN`: one conditional probe lease tests recovery;
- successful probe: reset to `CLOSED`; and
- failed probe: return to `OPEN` with a new expiry.

Use conditional writes so concurrent workers cannot all become the half-open probe. Emit stable attempt-count and breaker-state events for Week 13 operations.

### 3. Add exactly three focused tests

Create only `tests/test_production_reliability.py` with:

1. **retry budget:** at most two attempts and no retry after the deadline or a non-retryable result;
2. **breaker transition:** eligible failures open it, only one half-open probe is admitted, and success closes it; and
3. **stop before calculator:** a weather failure prevents the dependent calculator call.

Inject clock, randomness, provider result, and DynamoDB access only where required to make these tests deterministic. Existing tests remain; do not add adjacent coverage for its own sake.

### 4. Run bounded failure probes

Exercise timeout, 429/5xx exhaustion, open-breaker fast failure, and successful half-open recovery through a deterministic fake for the raw Gateway operation or a fault seam that cannot be enabled accidentally in PROD.

Reuse the Week 5 failure taxonomy and the eight-case slice. Record attempt count, deadline consumption, breaker transitions, final agent response, and whether calculator ran. Do not create an outage corpus or multi-provider matrix.

## Deliverable

One weather-reliability artifact group:

- `weatheragent/app/weather_agent/weather_reliability.py`
- updated wrapper and Terraform reliability/IAM files
- exactly `tests/test_production_reliability.py`
- `docs/reports/week-12-reliability.md`

There is no write action, idempotency system, load test, or reusable resilience library.

## Success check

The same injected outage produces at most two provider attempts, opens the shared breaker, prevents calculator execution, fails fast on the next request, and closes only after one successful half-open probe; all three named tests pass.

## Read

- [Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [DynamoDB condition expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html)
- [DynamoDB update expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html)
- [Week 5 failure taxonomy](../tool-contract-spec.md)
- [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)