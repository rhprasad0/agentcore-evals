# Local Strands vs. AgentCore Runtime

This comparison uses the same small weather agent in two places: directly in a local Python process and as a CodeZip deployment on Amazon Bedrock AgentCore Runtime. The point was not to benchmark the internet. It was to learn what managed Runtime changes: latency boundaries, credentials, sessions, failure modes, cost, and debugging.

## What was deployed

The managed version used:

- AgentCore CLI with an AWS CDK and CloudFormation deployment
- CodeZip staged through Amazon S3
- Python 3.14, HTTP protocol, and public network mode
- a Strands agent backed by the global Claude Sonnet 4.5 inference profile
- the same typed `get_current_weather` tool used by the local agent

The Runtime reached `READY`, returned a tool-backed weather answer, and emitted CloudWatch logs and OpenTelemetry spans. The application artifact used S3-backed CodeZip packaging rather than a container image or ECR.

## Measurement design

The benchmark ran five paired trials in each environment:

- Local cold: construct a fresh Strands `Agent`, then invoke it.
- Local warm: invoke the same local `Agent` a second time.
- Managed cold: invoke AgentCore with a fresh Runtime session ID.
- Managed warm: make a second invocation in that same Runtime session.

Each first call requested fresh Seattle weather. Each second call requested fresh Boston weather. Both prompts explicitly required `get_current_weather`, so a remembered answer could not masquerade as a warm tool call.

"Cold" has different boundaries in the two lanes. Local cold means a fresh `Agent` object inside an already-running Python process. Managed cold means a fresh AgentCore session and whatever provisioning, routing, authentication, and client work that path requires. This is a learning benchmark, not a laboratory-grade service comparison.

The public-safe source measurements are in [`docs/assets/week-03-latency-measurements.json`](assets/week-03-latency-measurements.json).

## Latency results

| Lane | Samples | Median |
| --- | ---: | ---: |
| Local, fresh Agent | 5 | 3.853 s |
| Local, second call | 5 | 3.481 s |
| Managed CLI, fresh session | 5 | 12.106 s |
| Managed CLI, second call | 5 | 5.967 s |

The managed cold median was 3.14 times the local cold median. The managed warm median was 1.71 times the local warm median.

The CLI stopwatch is broader than the Runtime trace. It starts before AWS credential loading, request signing, network transit, routing, and session startup, and it stops after the response returns to the client. The Runtime root span begins after the request reaches the application boundary.

| Managed trace lane | Root span | Model spans | Weather tool span |
| --- | ---: | ---: | ---: |
| Fresh session, median | 3.627 s | 3.465 s | 0.047 s |
| Second call, median | 3.238 s | 3.188 s | 0.040 s |

The initial hypothesis was that OpenWeather would dominate because it sits outside AWS. The trace killed that theory quickly. Claude consumed roughly 96% to 99% of the traced Runtime duration. The weather tool consumed about 1%.

The fresh-session CLI median exceeded the corresponding Runtime root span by 8.479 seconds. The warm gap was 2.729 seconds. Subtracting those baselines gives about 5.75 seconds of incremental cold-path overhead, but that is not a pure microVM startup measurement. It also contains differences in AgentCore routing, session provisioning, client work, and network behavior that the application trace cannot separate.

## Credentials and identity

Local execution used two identities:

- local AWS credentials for Bedrock model invocation
- `OWM_API_KEY` loaded from an ignored local `.env` file

Managed execution also used two identities, but neither came from the deployment shell automatically:

- the Runtime execution role invoked Bedrock
- `OWM_API_KEY` was temporarily injected into the Runtime environment through `UpdateAgentRuntime`

The `.env` file was not packaged in CodeZip. That separation is useful: it proves that deployment credentials and Runtime credentials are different concerns. It also exposed a weak seam. A control-plane environment variable keeps the key out of the zip and tracked config, but the control plane is not a secret vault. A production version should use AgentCore Identity or another supported secret-backed credential flow.

## Sessions and conversation state

The application keeps one in-process Strands `Agent` per Runtime session ID in a bounded LRU cache. That gives best-effort conversation continuity while the process survives. It is not durable memory and resets after a cold start or cache eviction.

A three-call isolation probe used an inert random canary:

1. Session A stored the canary.
2. Session A recalled the exact value.
3. Session B returned `NO_CONTEXT` and did not return the canary.

The positive control matters. If Session A could not recall its own value, Session B's miss would prove nothing. The honest result is narrower than "AgentCore always isolates every conversation": the tested conversation context did not cross sessions in this run.

AgentCore's default idle Runtime session timeout is 900 seconds, and the default maximum instance lifetime is eight hours. The application cache does not override those platform lifecycle boundaries.

## Failure modes encountered

| Failure or surprise | Local behavior | Managed behavior |
| --- | --- | --- |
| Missing OpenWeather key | Fails immediately in the local process | Deploys successfully, then the tool fails at invocation unless the Runtime receives the key separately |
| Bedrock permissions | Uses the developer's AWS identity | Uses the Runtime execution role |
| Deployment prerequisites | None beyond local dependencies | CDK bootstrap, S3 asset staging, CloudFormation, and IAM are part of the path |
| CLI drift | Local Python runner remains stable | Installed AgentCore CLI used `deploy --dry-run`; an older `--plan` instruction was stale |
| Trace availability | Local debugging is immediate | Transaction Search activation and span indexing can lag; the first OTLP export returned HTTP 400 while setup was still activating |
| Console discovery | Local logs are direct | The generic Agents View was initially empty even though `agentcore traces list` already found traces |
| Deployment state | No cloud identifiers | AgentCore CLI can write account IDs and ARNs into local state files, so tracked public-safe versions must be restored before committing |

## Debuggability

Local development is faster for tool contracts, argument validation, deterministic failure injection, and normal Python stack traces. It is also easier to inspect the complete Strands message history without waiting for telemetry.

AgentCore is better for distributed-system questions that local execution cannot answer:

- Which IAM principal invoked Bedrock?
- Did a fresh session take a different path from a warm one?
- Which model and tool spans dominated latency?
- Did conversation state cross session IDs?
- Did deployment, networking, or the execution role fail before application code ran?

The useful managed receipt was the span tree: `POST /invocations`, `invoke_agent Strands Agents`, two model calls, and `execute_tool get_current_weather`. In AgentCore CLI 0.22, `agentcore traces get` downloaded correlated Runtime records but not the normalized span table. Precise span durations came from CloudWatch Logs Insights over the special `aws/spans` source.

Raw traces are not committed. They may contain prompts, responses, session IDs, resource identifiers, and account metadata.

## Runtime cost model

AgentCore Runtime currently charges:

- $0.0895 per vCPU-hour
- $0.00945 per GB-hour

That normalizes to about $0.00002486 per vCPU-second and $0.000002625 per GB-second. Runtime cost is:

```text
(vCPU-hours used × $0.0895) + (GB-hours used × $0.00945)
```

Wall-clock latency is not a billing meter. AWS bills actual CPU consumption and peak memory consumed per second across the session lifetime. CPU can fall to zero during model or tool I/O, while memory remains a separate usage dimension. The service also counts system overhead.

After the documented telemetry delay, CloudWatch reported the following usage for the measured workload window:

| Runtime usage | Quantity | Rate | Cost |
| --- | ---: | ---: | ---: |
| CPU | 0.036823 vCPU-hours | $0.0895/vCPU-hour | $0.003296 |
| Memory | 2.383629 GB-hours | $0.00945/GB-hour | $0.022525 |
| **Total Runtime compute** | | | **$0.025821** |

AWS Cost Explorer independently reported $0.0258209862 for Amazon Bedrock AgentCore on the workload date, matching the metric calculation before rounding. That Cost Explorer period was still marked estimated.

The same usage was emitted at two CloudWatch dimension granularities: `Name/Resource/Service` and `Resource/Service`. Their values were identical, so the calculation used one series rather than double-counting both.

The window contained 14 traced invocations across eight sessions. Allocating the Runtime total evenly gives $0.001844 per invocation or $0.003228 per session. Those are workload averages, not isolated request prices: idle session lifetime, fresh-session frequency, and shared overhead all affect the allocation. Memory represented 87.24% of this Runtime compute cost.

Bedrock model inference, CloudWatch telemetry, S3 CodeZip storage, and network transfer are separate charges. The daily Bedrock service total was not attributed to this workload because other account activity could share the same service and date.

The default 15-minute idle timeout also matters when pricing a full session. Runtime billing spans boot through termination, so invocation cost and session cost are not interchangeable. The dominant cost knob cannot be inferred from response latency alone.

## Practical split

Use local execution to develop the agent and prove deterministic tool behavior. Use AgentCore when the question involves deployment identity, session lifecycle, managed networking, or trace evidence.

For this specimen, managed hosting did not make the weather tool faster or smarter. It made the operational boundaries visible. The latency tax was real, especially for fresh sessions, but the trace showed where the application spent its time instead of leaving the architecture to vibes.

## Claim limits

- N=5 per lane is too small for a performance guarantee.
- Measurements came from one Region, model, tool, prompt pair, account, and time window.
- Local cold did not include Python process or machine startup.
- The CLI-minus-root-span gap is unattributed overhead, not measured microVM startup.
- The session probe covered conversational context once; it did not test filesystem isolation or prove universal platform behavior.
- No managed tool timeout was injected; the failure comparison covers observed deployment, credential, and telemetry failures.
- Runtime cost is measured at the workload/day level; the per-invocation and per-session figures are allocations, not isolated AWS line items.

## Sources

- [Public-safe benchmark measurements](assets/week-03-latency-measurements.json)
- [Runtime execution-role baseline](execution-role-baseline.md)
- [AgentCore trace anatomy](trace-anatomy.md)
- [Amazon Bedrock AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [AgentCore Runtime lifecycle settings](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html)
- [AgentCore Runtime observability data](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-runtime-metrics.html)
