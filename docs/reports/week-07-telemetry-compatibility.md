# Week 7 Strands telemetry calibration

**Calibration date:** 2026-07-17
**Scope:** Two bounded Amazon Bedrock invocations; not the 62-row projection

## Exact behavior pins

- Model: `us.amazon.nova-micro-v1:0`
- Strands Agents: `1.46.0`
- Strands Agents Evals: `1.0.1`
- Source profile: `strands-inline@1.0.0`
- Canonicalizer: `1.0.0`

The successful run used one exported span set for both the repository adapter and `StrandsInMemorySessionMapper`. Raw spans, prompts, responses, identifiers, and run-local files remain ignored and are not reproduced here.

## Adapter findings

The live Strands trace contained the expected `invoke_agent`, `chat`, `execute_tool`, and `execute_event_loop_cycle` operations. Event-loop-cycle spans are explicit SDK scaffolding rather than canonical operations. The serializer therefore validates them, omits them from the source profile, and reparents supported descendants to the nearest retained ancestor. Unknown operations still fail loudly.

The installed tracer emitted instrumentation scope `strands.telemetry.tracer` with empty version and schema URL metadata. The source adapter preserves those values rather than inventing package metadata.

The successful canonical trace contained:

- one root agent invocation;
- two model chat spans;
- one exact `get_current_weather` tool execution;
- contract-valid arguments and output;
- contiguous sequence values and valid parent references; and
- non-null selection reasoning derived only from contiguous assistant text immediately before the correlated tool call.

Semantic validation resolved `weather.get_current_weather@2.0.0` through `agents.weather@4.0.0`, then independently validated the tool reference, arguments, output, parentage, ordering, and success/failure consistency.

## Native Strands Evals compatibility

The bounded `@eval_task(TracedHandler())` probe and repository adapter consumed the same finished spans. The native Session and canonical trace agreed on every planted fact:

| Fact | Result |
|---|---|
| Model-visible tool name | Match |
| Tool arguments | Match |
| Normalized tool result | Match |
| Span correlation identity | Match |

Mutation tests independently changed each fact and produced the corresponding field-specific mismatch. The compatibility comparator does not require byte-identical schemas.

Native-only representation details include typed span classes and `Session`/`Trace` containers. Timestamps and token usage exist in both representations but were not planted compatibility facts. Exact contract identity, block-local selection reasoning, bounded diagnostics, and repository semantic invariants remain canonical-trace responsibilities.

## Instrument-error calibration

The other bounded case produced an exact mock-fixture miss: Nova Micro supplied explicit `metric` units where the selected row had no matching row-scoped fixture key. The tool span consequently contained SDK exception text instead of a contract-shaped result. The adapter rejected it as an instrument error and did not create a canonical trace.

That finding is intentionally not repaired during calibration. It demonstrates the boundary required for the later 62-row run: model/specimen failures remain observable evidence and cannot be recast as valid agent verdicts or adapter output.

## Claim boundary

This calibration establishes compatibility for the pinned local Strands source profile and one public-safe successful case. It does **not** establish managed AgentCore ingestion compatibility, full-projection behavior, model determinism, or cross-version SDK compatibility.
