# AgentCore trace anatomy

Captured 2026-07-11 from one successful, tool-backed weather invocation in Amazon Bedrock AgentCore Runtime. This is a public-safe schema summary, not a raw trace export.

The representative trace contained nine spans and 27 correlated log records. Identifiers, prompts, model responses, tool arguments, tool results, AWS resource metadata, and credential identifiers are intentionally omitted.

## What each trace surface returned

AgentCore exposed two related but different views of the invocation.

### `agentcore traces get`

The CLI downloaded correlated CloudWatch records as a top-level JSON list. Each outer row contained:

- `@timestamp`
- `@message`
- `@ptr`

`@message` was a structured OpenTelemetry log record with:

- `traceId`
- `spanId`
- `timeUnixNano`
- `observedTimeUnixNano`
- `severityNumber`
- `severityText`
- `flags`
- `eventName`
- `body`
- `attributes`
- `resource`
- `scope`

This output carried prompts, responses, tool calls, and tool results in event bodies. It did not contain the normalized span rows used for duration analysis.

The CLI defaults to a 12-hour lookup window. An older trace required an explicit window:

```text
agentcore traces get <TRACE_ID> --since 24h --output <PRIVATE_PATH>
```

### CloudWatch `aws/spans`

The normalized span source supplied the hierarchy and timing fields:

- `traceId`
- `spanId`
- `parentSpanId`
- `name`
- `kind`
- `startTimeUnixNano`
- `endTimeUnixNano`
- `durationNano`
- `status`
- `attributes`
- `resource`
- `scope`
- `flags`

The CloudWatch console waterfall is built from this span shape. The CLI records and normalized spans share trace/span identifiers, allowing private correlation without committing either raw source.

## Representative span tree

Durations are nested and must not be added together indiscriminately.

```text
POST /invocations                                      3,178.339 ms  SERVER    UNSET
└─ invoke_agent Strands Agents                         3,175.732 ms  INTERNAL  OK
   ├─ execute_event_loop_cycle                         1,836.205 ms  INTERNAL  OK
   │  ├─ chat                                          1,794.856 ms  INTERNAL  OK
   │  │  └─ chat global.anthropic.claude-sonnet-4-5…   1,793.754 ms  CLIENT    UNSET
   │  └─ execute_tool get_current_weather                 40.434 ms  INTERNAL  OK
   └─ execute_event_loop_cycle                         1,338.816 ms  INTERNAL  OK
      └─ chat                                          1,337.967 ms  INTERNAL  OK
         └─ chat global.anthropic.claude-sonnet-4-5…   1,336.383 ms  CLIENT    UNSET
```

The first model pass selected the weather tool. The tool executed. The second model pass turned the result into the final answer.

`UNSET` did not mean failure here. The server request and Bedrock client spans had successful HTTP status attributes while their OpenTelemetry status remained unset. Internal Strands spans explicitly reported `OK`.

## Model fields

The Strands agent and model spans exposed:

- `gen_ai.agent.name`
- `gen_ai.agent.tools`
- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.request.model`
- `gen_ai.response.finish_reasons`
- `gen_ai.system`
- `gen_ai.server.request.duration`
- `gen_ai.server.time_to_first_token`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.usage.total_tokens`
- `gen_ai.usage.prompt_tokens`
- `gen_ai.usage.completion_tokens`
- `gen_ai.usage.cache_read_input_tokens`
- `gen_ai.usage.cache_write_input_tokens`
- `aws.genai.token_count_total`
- `retry_attempts`
- `http.response.status_code`

Not every field appeared on every model-related span. The outer `invoke_agent` span carried aggregate usage, the internal `chat` spans carried request timing, and the Bedrock client spans carried provider response and retry metadata.

## Tool fields

The normalized tool span exposed:

- `gen_ai.tool.call.id`
- `gen_ai.tool.name`
- `gen_ai.tool.description`
- `gen_ai.tool.json_schema`
- `gen_ai.tool.status`
- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.system`
- `gen_ai.event.start_time`
- `gen_ai.event.end_time`
- `session.id`

The normalized span did **not** carry the selected arguments or returned weather data directly. Those lived in correlated log-event bodies.

The assistant-message event represented the tool call using fields including:

- `body.tool_calls[].id`
- `body.tool_calls[].type`
- `body.tool_calls[].function.name`
- `body.tool_calls[].function.arguments`

A provider-shaped copy also appeared under:

- `body.content[].toolUse.toolUseId`
- `body.content[].toolUse.name`
- `body.content[].toolUse.input`

Tool output appeared in `gen_ai.tool.message` records under `body.content[].text`, correlated by `body.id`. Another provider-shaped result appeared under `body.content[].toolResult` in a `gen_ai.user.message` event.

These bodies are useful for private debugging and evaluation ingestion. They are also the reason raw trace exports do not belong in Git.

## Correlation and runtime fields

Useful correlation fields included:

- `session.id`
- `event_loop.cycle_id`
- `event_loop.parent_cycle_id`
- `traceId`
- `spanId`
- `parentSpanId`
- `aws.request_id`
- `service.name`
- `deployment.environment.name`
- `cloud.provider`
- `cloud.platform`
- `cloud.region`
- `cloud.resource_id`
- `telemetry.sdk.name`
- `telemetry.sdk.language`
- `telemetry.sdk.version`
- `scope.name`
- `scope.version` or `scope.schemaUrl`, depending on signal type

Several are operational identifiers rather than evaluation features. Public evidence should replace or hash session, trace, request, and resource identifiers rather than publishing them verbatim.

One Bedrock client-span attribute was named `aws.auth.account.access_key`. Even though an access-key identifier is not the secret key itself, its presence is another reason to treat raw telemetry as sensitive.

## Week 6 execution-trace schema

A useful evaluation record should preserve enough structure to answer what happened without copying the entire vendor payload.

| Category | Proposed fields |
| --- | --- |
| Case | `case_id`, `dataset_version`, `prompt_version`, `expected_tool`, `expected_outcome` |
| Correlation | internal `trace_id`, `session_id`, `invocation_id`; public-safe hashes for exported evidence |
| Span | `span_id`, `parent_span_id`, `name`, `kind`, `started_at`, `duration_ms`, `status` |
| Model | provider, model/inference profile, operation, input/output/cache tokens, time to first token, finish reason, retries |
| Tool | call ID, tool name, sanitized arguments, status, sanitized result summary, duration |
| Runtime | service, Region, deployment version, cold/warm lane, CLI end-to-end duration |
| Evaluation | validator name/version, pass/fail, score, reason, failure category |
| Privacy | redaction version, fields removed, whether raw telemetry remains private |

The schema should preserve the two model passes around the tool call. Flattening the invocation into one model duration would hide the agent loop that actually matters.

## What the trace did not tell us

The trace was detailed, but it did not answer everything:

- **Why the model chose the tool.** It recorded the tool call, not a reliable model rationale. Fabricating one after the fact would be worse than leaving it unknown.
- **OpenWeather network anatomy.** The tool had one 40 ms wrapper span, with no child HTTP span separating DNS, TLS, network transit, server time, and Python overhead.
- **MicroVM startup duration.** No span isolated provisioning or cold boot before `POST /invocations` began.
- **Exact billing usage.** CPU and memory consumption are separate CloudWatch usage metrics, not trace fields.
- **Eval expectations.** The trace knew what happened, not whether the selected tool, arguments, or answer were correct for a test case.
- **Prompt and deployment fingerprints.** The telemetry did not provide the repository revision, prompt-template version, or evaluation dataset version needed for reproducibility.
- **Cross-session guarantees.** A `session.id` correlates one trace; it does not prove that other sessions could not access its state.

Those gaps define part of the Week 6 harness rather than defects to paper over with prose.

## Claim limits

- This summary describes one successful weather trace and checks its shape against the benchmark traces; it is not a universal AgentCore schema guarantee.
- Span attributes depend on the AgentCore, OpenTelemetry, Strands, and AWS SDK versions in the deployed artifact.
- The 40 ms tool duration measures the Python tool wrapper observed by Strands, not OpenWeather server time alone.
- `status: UNSET` was interpreted alongside HTTP status and successful parent behavior, not treated as automatic failure.
- Raw telemetry remains private and was not added to the repository.

## Sources

- [Local-versus-AgentCore comparison](local-vs-agentcore.md)
- [Public-safe latency measurements](assets/week-03-latency-measurements.json)
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [OpenTelemetry generative AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
