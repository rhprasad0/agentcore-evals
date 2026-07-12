# AgentCore Gateway `enableSemanticSearch: false` deployment failure

## Summary

AgentCore CLI accepts a Gateway configured with `enableSemanticSearch: false`, but the generated CDK construct synthesizes `SearchType: NONE`. CloudFormation rejects that value because `SearchType` is optional and `SEMANTIC` is its only documented allowed value.

Removing `enableSemanticSearch` allows the CLI schema default (`true`) to apply. In the verified workaround, synthesis emitted `SearchType: SEMANTIC`, CloudFormation deployed successfully, the Gateway and Web Search target reached `READY`, and IAM-authenticated MCP listing and invocation succeeded.

This workaround does **not** disable semantic search. Clients that require a deterministic tool set must still filter the discovered MCP surface explicitly.

## Environment

- AgentCore CLI: `0.24.0`
- Generated construct: `@aws/agentcore-cdk` `0.1.0-alpha.45`
- Management path: AgentCore CLI → generated CDK project → CloudFormation
- Gateway protocol: MCP
- Inbound authorization: AWS IAM
- Target: built-in Web Search connector

No account identifiers, ARNs, endpoints, stack identifiers, or raw service responses are included in this report.

## Expected behavior

A documented configuration value of `enableSemanticSearch: false` should produce a service-valid disabled Gateway configuration. If the current service or construct cannot represent that state, the CLI should reject `false` locally with an actionable error. It should never synthesize the unsupported `SearchType: NONE` value.

CloudFormation reference: [AWS::BedrockAgentCore::Gateway MCPGatewayConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrockagentcore-gateway-mcpgatewayconfiguration.html)

## Actual behavior

The following relevant fragment from a Gateway entry passes local validation as part of the complete project configuration:

```json
{
  "name": "example-gateway",
  "protocolType": "MCP",
  "authorizerType": "AWS_IAM",
  "enableSemanticSearch": false,
  "exceptionLevel": "NONE"
}
```

The deployment path then synthesizes:

```yaml
ProtocolConfiguration:
  Mcp:
    SearchType: NONE
```

`agentcore validate` succeeds, but CloudFormation rejects the generated Gateway because `NONE` is not an allowed `SearchType` value. The valid `exceptionLevel: NONE` setting is unrelated; the failure concerns `ProtocolConfiguration.Mcp.SearchType`.

## Reproduction sequence

```bash
agentcore validate
agentcore deploy --dry-run --target default --yes
agentcore deploy --target default --yes
```

Observed layers:

1. AgentCore local schema validation accepted `enableSemanticSearch: false`.
2. CDK synthesis converted the false value to `SearchType: NONE`.
3. CloudFormation rejected the generated enum value.

A passing `agentcore validate` therefore does not catch this cross-layer contract mismatch.

## Verified workaround

Remove the property rather than setting it to `false` while retaining the rest of the Gateway entry:

```json
{
  "name": "example-gateway",
  "protocolType": "MCP",
  "authorizerType": "AWS_IAM",
  "exceptionLevel": "NONE"
}
```

With AgentCore CLI 0.24.0, omission applies the schema default of `true`. The verified result was:

1. `agentcore validate` passed.
2. `agentcore deploy --dry-run` completed successfully.
3. Manual inspection of the synthesized template found `SearchType: SEMANTIC` and no Gateway `SearchType: NONE`.
4. The reviewed template contained one Runtime, one Gateway, one Gateway target, two IAM roles, and two IAM policies.
5. CloudFormation deployment completed successfully.
6. The Gateway and Web Search target both reached `READY`.
7. An IAM/SigV4-authenticated MCP `tools/list` request returned HTTP 200.
8. A controlled Web Search invocation returned HTTP 200 with no JSON-RPC or tool-level error.

The raw search response was not retained.

## MCP surface after the workaround

Because omission enables semantic search, `tools/list` advertised two tools:

- `x_amz_bedrock_agentcore_search` — Gateway semantic tool discovery
- `web-search___WebSearch` — the configured Web Search connector

The Web Search connector required `query` and optionally accepted `maxResults`. Its advertised description was empty in this deployment, which is a separate model-facing contract concern for the Week 4 trust/schema audit.

An eval-oriented client must register only `web-search___WebSearch` and fail closed if that approved tool is absent or duplicated. Passing the entire discovered list to the agent would add the semantic-search helper to the candidate set and undermine deterministic tool-selection measurement.

AWS documents IAM-authenticated Strands connectivity using `aws_iam_streamablehttp_client` from `mcp-proxy-for-aws`, signed with service name `bedrock-agentcore`. The verification for this report used the equivalent SigV4-signed MCP JSON-RPC request without storing credentials or endpoint details.

## Behavioral limitation

This workaround changes behavior:

- **What it fixes:** the generated CloudFormation becomes service-valid and deploys.
- **What it does not preserve:** semantic search is no longer disabled at the Gateway.
- **What remains deterministic:** the client can still use an explicit allowlist and decline to register the semantic-search helper.
- **What cannot be claimed:** that semantic discovery is disabled end to end.

The AgentCore Evals architecture decision remains explicit client registration for evaluability. Semantic search is enabled here only because the current false-value deployment path is defective.

## Regression assessment

The current behavior is a **technically confirmed defect**: documented input deterministically produced invalid CloudFormation.

It is also a **likely regression**, because review discussion on [`aws/agentcore-cli` PR #855](https://github.com/aws/agentcore-cli/pull/855) described an earlier `enableSemanticSearch: false` path that omitted `ProtocolConfiguration`. Current behavior instead emits `SearchType: NONE`.

It is not yet a **confirmed regression** because the same minimal fixture has not established a pinned last-good/first-bad release boundary. The related PR is historical evidence, not an exact duplicate report or upstream acknowledgment.

## Upstream issue

The public bug report is [aws/agentcore-cli #1744](https://github.com/aws/agentcore-cli/issues/1744).

## Suggested fix

The CLI/CDK path should map `false` to the service's valid disabled representation, or reject `false` locally if no disabled representation is currently supported. Tests should cover all contract layers:

1. the false-value path never generates an unsupported enum value;
2. synthesis with `false` does not emit `SearchType: NONE`;
3. the synthesized template conforms to CloudFormation's allowed values;
4. `agentcore validate` rejects or warns about any configuration that would synthesize an unsupported enum value;
5. an end-to-end Gateway deployment test covers both semantic-search-enabled and disabled configurations.

Once the disabled state is supported upstream, this project should restore an explicit disabled setting and verify the synthesized template before claiming that semantic discovery is off.
