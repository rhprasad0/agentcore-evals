# Telemetry compatibility profile

## Purpose and claim boundary

This document defines the tested translation seam between three different contracts:

1. **Producer profile:** Strands telemetry with inline span events, or Strands metadata spans plus ADOT-split event records.
2. **Repository canonical trace:** [`schemas/execution-trace.schema.json`](../schemas/execution-trace.schema.json), consumed by later local adapters, gates, labels, and reports.
3. **Managed input profile:** the documented Amazon Bedrock AgentCore `EvaluationInput.sessionSpans` request member.

The fixtures prove offline extraction, correlation, schema validation, and deterministic canonical projection for the exact synthetic profiles below. They do **not** prove live AgentCore Evaluations acceptance, CloudWatch resource association, ADOT transport behavior, production representativeness, or model determinism. The first live managed acceptance receipt remains a Week 10 task.

Verified against primary documentation on **2026-07-16**:

- [AgentCore Strands framework profile](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-strands.html)
- [Spans, event records, and telemetry signals](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html)
- [`EvaluationInput` API reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_EvaluationInput.html)
- [Strands trace documentation](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/)

## Pinned source profiles

The package versions are taken from `weatheragent/app/weather_agent/uv.lock`; the root validation project deliberately does not depend on the deployable agent package.

| Component | Pinned value | Role |
| --- | --- | --- |
| Strands Agents | `strands-agents==1.46.0` | Producer SDK and built-in instrumentation |
| Instrumentation scope | `strands.telemetry.tracer` | Required span/event-record scope name |
| Scope version | explicit `null` | The documented examples emit an empty or omitted scope version; no version is invented |
| Scope schema URL | explicit `null` | Not present in the documented Strands examples used by this profile |
| AWS Distro for OpenTelemetry | `aws-opentelemetry-distro==0.18.0` | Collector profile for split telemetry only |
| OpenTelemetry API/SDK | `1.42.1` | Locked transitive telemetry implementation |
| OpenTelemetry semantic conventions package | `0.63b1` | Locked transitive convention package; not treated as the Strands profile version |
| AgentCore SDK | `bedrock-agentcore==1.17.0` | Local managed-client package; not evidence of service acceptance |

`src.telemetry_normalization.normalize_strands_telemetry` rejects a producer-version, collector-version, or instrumentation-scope mismatch. A later SDK or ADOT upgrade must add or revise a named source profile and fixtures rather than silently flowing through this adapter.

## Span identification and correlation

AWS documents the following Strands classifiers:

| Canonical operation | Source classifier |
| --- | --- |
| `invoke_agent` | `attributes["gen_ai.operation.name"] == "invoke_agent"` |
| `execute_tool` | `attributes["gen_ai.operation.name"] == "execute_tool"` |
| `chat` | `attributes["gen_ai.operation.name"] == "chat"` |

For split telemetry, each event record is joined to exactly one span by the pair `(traceId, spanId)`. Missing, duplicate, and orphaned correlations fail loudly. The adapter does not fall back from a missing split record to inline attributes or events.

The adapter orders supported spans by `(startTimeUnixNano, endTimeUnixNano, spanId)` and assigns contiguous canonical `sequence` values. The source identifiers and timestamps remain available in the full canonical trace, while the deterministic projection keeps only `sequence`.

## Field mapping

| Canonical field | Inline Strands source | ADOT-split source | Required/null rule | Projection class | Redaction and managed-lane note |
| --- | --- | --- | --- | --- | --- |
| `sourceProfile` | Fixture-declared pinned profile | Fixture-declared pinned profile plus collector | Required | Volatile metadata; excluded | Package/scope metadata only; no host, account, or resource identifiers |
| `sessionId` | Invoke span `attributes["session.id"]` | Same | Required | Provider identity; excluded | Runtime injects this in managed deployments; synthetic fixture uses a fictional value |
| `traceId` | Invoke span `traceId` | Same | Required | Provider identity; excluded | Must be a 32-character lowercase hexadecimal ID; synthetic only |
| `spans[].spanId` / `parentSpanId` | Span fields | Span fields | Span ID required; parent nullable | Provider identity; excluded | Synthetic only; used for inspection and split correlation |
| `spans[].operationName` | `gen_ai.operation.name` | Same metadata span attribute | Required closed set | Canonical; included | Framework-specific classifier, not a generic OTEL fallback |
| `prompt` | Invoke event `gen_ai.user.message.attributes.content` | Correlated record `body.input.messages` user-role content | Required non-empty | Canonical; included | Public-safe synthetic prompt only |
| `response` | Invoke event `gen_ai.choice.attributes.message` | Correlated record `body.output.messages` assistant-role content/message | Required non-empty | Canonical; included | Public-safe synthetic response only |
| `spans[].observedToolName` | Execute span `gen_ai.tool.name` | Same metadata span attribute | String for tool spans; otherwise null | Canonical; included | Preserves the model-visible name separately from local identity |
| `spans[].tool` | Resolve observed name through exact `agents.weather@3.0.0` grants and contracts | Same | Exact `{toolId, contractVersion}` for tool spans; otherwise null | Canonical; included | Local extension; AWS telemetry does not emit repository contract identity |
| `spans[].arguments` | Execute event `gen_ai.tool.message.attributes.content` | Correlated record tool-role `body.input.messages[].content.content` | Decodes to an object for tool spans; otherwise null | Canonical; included | JSON representation is decoded without trimming, case-folding, default insertion, or numeric coercion |
| `spans[].result.output` | Execute event `gen_ai.choice.attributes.message` | Correlated assistant-role `body.output.messages[].content.message` | Normalized contract result object for tool spans; otherwise null | Canonical; included | Preserves the complete public-safe normalized result envelope |
| `result.ok` | Decoded output `ok` | Same | Required boolean | Canonical; included | Contract-owned meaning |
| `result.failureKind` / `retryable` | Decoded `error.kind` / `error.retryable` | Same | Null on success; typed values on failure | Canonical; included | Uses the Week 5 normalized failure taxonomy, not raw provider classes |
| `result.diagnostic` | Optional local attributes `agentcore_evals.failure.source` and `.code` | Same | Explicit null when absent; bounded source/code when present | Canonical; included | Local extension; code is capped at 64 characters and must contain no raw diagnostics |
| `selectionReasoning` | Optional local `agentcore_evals.selection_reasoning` | Same | Explicit null when no pre-tool assistant text was observed | Canonical; included | Never inferred or synthesized; this records observed text, not causal reasoning |
| `startTimeUnixNano` / `endTimeUnixNano` | Span fields | Span fields | Required non-negative integers | Volatile; excluded | Retained for inspection and ordering |
| `latencyMs` | Derived from source start/end | Same | Required non-negative number | Volatile; excluded | Measurement, not a deterministic gate input |
| `tokenUsage` | Invoke attributes `gen_ai.usage.input_tokens`, `.output_tokens`, `.total_tokens` | Same | All three integers or explicit null | Volatile; excluded | Provider-jittered counts are retained but excluded from reproducibility claims |

The synthetic source fixtures are:

- `tests/fixtures/telemetry/strands-inline/weather-success.json`
- `tests/fixtures/telemetry/strands-adot/weather-success.json`

Their full normalized reference is:

- `tests/fixtures/telemetry/canonical/weather-success.json`

## Canonical projection and reproducibility

`canonical_projection_bytes` serializes UTF-8 JSON with sorted object keys, compact separators, Unicode preserved, non-finite numbers rejected, and spans ordered by canonical `sequence`.

Included fields:

- schema and canonicalizer versions;
- exact capability-manifest identity;
- prompt and response;
- per-span sequence, operation, observed tool name, exact local tool reference, arguments, normalized result, and nullable observed selection text.

Excluded fields:

- source-profile/package metadata;
- session, trace, span, parent-span, and tool-call provider identifiers;
- timestamps and latency;
- token counts.

The passing equality test therefore means:

> Given the tested inline and ADOT-split source profiles with equivalent semantic content, normalization produces byte-identical canonical projections after deterministic ordering and explicit volatile-field exclusion.

It does not mean two stochastic model runs will choose the same tools, produce the same arguments, or return the same response.

## Managed `EvaluationInput.sessionSpans` fixture

`tests/fixtures/telemetry/agentcore-evaluation-input/session-spans.json` exercises the currently documented managed request boundary:

- `EvaluationInput` is treated as a union, so the fixture specifies only `sessionSpans`;
- `sessionSpans` contains JSON values;
- the array contains between 1 and 1000 items, inclusive;
- the values are span-shaped records from the pinned Strands profile.

The local validator checks the union-member exclusivity, JSON-value requirement, and 1–1000 bounds. The API reference does not document a direct `sessionSpans` packaging rule for separately correlated ADOT event records. Accordingly, this fixture is intentionally span-only and makes no split-record ingestion or live service-acceptance claim. Week 10 must test the exact live request path and record any adapter delta.

## Upgrade procedure

When Strands, ADOT, or the managed profile changes:

1. Re-read the four primary sources above.
2. Record the new exact package/scope metadata without borrowing unrelated OTEL release numbers.
3. Add a newly named source profile or deliberately revise this profile.
4. Capture only synthetic or scrubbed public-safe fixture shapes.
5. Run the inline, split-correlation, schema, failure-envelope, managed-boundary, and canonical-byte tests.
6. Keep any live acceptance claim scoped to the exact Region, service path, payload, and date actually exercised.
