# Week 4 direct-weather versus Gateway-weather comparison

**Date:** 2026-07-12
**Region:** `us-east-1`
**Scope:** one direct Strands `@tool` and the same current-weather contract behind Lambda and AgentCore Gateway
**Model calls:** none

## Question

What changes when the same current-weather capability moves from an in-process Strands tool to a Lambda target exposed as MCP through AgentCore Gateway?

## Production-shaped deployment

A dedicated CloudFormation stack owns:

- one Python Lambda function;
- one Lambda execution role;
- one seven-day CloudWatch log group;
- one least-privilege `lambda:InvokeFunction` policy attached to the existing Gateway execution role;
- one `AWS::BedrockAgentCore::GatewayTarget` resource.

The existing Gateway and Web Search connector remain managed by the AgentCore CLI configuration. Account-specific Gateway identifiers and role names are discovered from ignored deployment state and the control plane at deploy time; they are not committed.

The OpenWeather key is passed as a CloudFormation `NoEcho` parameter and stored in the Lambda environment for this bounded Week 4 exercise. That is a transitional credential seam, not the final production credential design; managed identity and secret handling are deferred to Week 12.

The direct and Lambda transports use different HTTP clients, but they package the same pure contract core for argument normalization, status mapping, success shaping, and typed failures.

## Schema transformation

Authored MCP schema: [`schemas/weather-tool.json`](../../schemas/weather-tool.json)

Observed Strands-facing Gateway tool:

- name: `weather-lambda___get_current_weather`;
- description: exactly equal to the direct tool description;
- required input: `city` on both seams;
- properties: `city` and `units` on both seams.

Transformation notes:

1. The standalone MCP schema uses API-style lower camel case: `name`, `description`, `inputSchema`, `type`, `properties`, and `required`.
2. The CloudFormation resource provider requires PascalCase equivalents. The deploy helper converts only structural property casing before putting the schema in `InlinePayload`.
3. Gateway returns a normal MCP schema, and Strands wraps it under `inputSchema.json`.
4. The direct Strands schema exposes `units` with `default: "metric"`.
5. The Gateway-advertised schema does not expose that default because AgentCore Gateway's CloudFormation `SchemaDefinition` has no `Default` field. The Lambda still defaults omitted `units` to `metric` at runtime.

That missing model-visible default is real contract drift even though runtime behavior remains equal. Week 5 should decide whether to encode the default in prose, require `units`, or add a manifest-level default assertion.

## Controlled comparison

Harness: [`scripts/compare_week4_weather_seams.py`](../../scripts/compare_week4_weather_seams.py)

The harness invoked each seam directly without a model. It made three successful Oslo metric calls through each seam and one invalid-city call through each seam.

### Success path

| Measurement | Direct `@tool` | Gateway → Lambda |
| --- | ---: | ---: |
| Successful calls | 3/3 | 3/3 |
| Minimum | 81.4 ms | 192.4 ms |
| Median | 83.9 ms | 217.5 ms |
| Maximum | 94.3 ms | 972.8 ms |

Measured median Gateway overhead: **133.6 ms**.

The first Gateway sample was 972.8 ms, consistent with a cold-start-shaped outlier, but this three-sample run does not isolate Lambda cold start from Gateway, network, or upstream variance. These numbers are a bounded comparison, not a service benchmark.

### Invalid-city path

Both seams returned exactly:

```json
{
  "ok": false,
  "error": {
    "kind": "upstream_4xx",
    "message": "weather API returned status 404",
    "retryable": false
  }
}
```

Direct latency was 153.4 ms; Gateway latency was 204.6 ms.

Gateway preserved the typed domain-failure payload. MCP reported transport success with `status: "success"` and `isError: false` because Lambda completed normally and returned a handled failure envelope. This distinction matters for Week 5 contracts and Week 6 labels: domain failure and transport failure are separate axes.

## Findings

1. **Description integrity can survive Gateway.** The authored weather description arrived model-facing without text drift. This contrasts with the managed Web Search connector, whose raw description was empty and received a generic Strands fallback.
2. **Schema fidelity is not complete.** Required fields survived; the Python default did not.
3. **Typed domain failures survive.** Gateway did not erase or rewrite the weather envelope.
4. **MCP success does not imply tool-domain success.** Evaluators must inspect the payload, not only `isError`.
5. **The governed seam costs latency and infrastructure.** The measured median added 133.6 ms plus a cold-start-shaped outlier, in exchange for centralized IAM, sharing, target governance, and a future Policy attachment point.
6. **Discovery still does not grant capability.** The Gateway now advertises weather, Web Search, and its semantic-search helper. The fixed three-tool portfolio continues to register only direct weather, calculator, and exact-name Web Search. Gateway weather was invoked only by the controlled comparison harness.

## Verification receipts

- CloudFormation preview: five additions, no replacements.
- Initial deployment: all five resources reached `CREATE_COMPLETE`.
- Shared-core update: in-place update, no replacements, final stack `UPDATE_COMPLETE`.
- AgentCore control plane: weather Lambda target `READY`.
- Offline suite after implementation: 41 tests passed.
- No raw Gateway endpoint, ARN, account ID, request ID, authorization header, API key, or full provider trace is stored in this report.

## Honest limitations

- Three success samples are enough to expose seam overhead, not characterize a latency distribution.
- Only one success city and one invalid-city domain failure were measured.
- Lambda environment credential injection is transitional.
- The comparison bypassed model selection deliberately; it measures invocation seams, not agent routing accuracy.
