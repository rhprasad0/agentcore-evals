# Week 11 — Production Gateway Boundary Receipt

**Status:** deterministic Terraform-owned Gateway boundary deployed and verified; Guardrail-in-Policy evidence deferred by provider support.

## Deployed boundary

Terraform owns the AgentCore Identity API-key provider, Gateway execution role, MCP Gateway, fixed-host OpenAPI target, Policy engine, and two deterministic Policies. The Gateway is in `ENFORCE` mode and exposes only the permitted current-weather operation to normal MCP discovery.

The execution role is scoped to the Gateway workload identity, the Token Vault, this API-key provider, its Identity-managed secret, and the attached Policy engine. The key was injected as the target's `appid` query parameter; it is absent from the repository, Runtime tool contract, saved-plan inspection, and this receipt.

## Live verification

| Check | Result |
| --- | --- |
| Current weather through Gateway | allowed |
| Weather → calculator trace | allowed; observed intermediate `18.92`, calculator result `37.84` |
| Direct forecast MCP invocation | denied by AgentCore Policy before target execution |
| Gateway service readback | MCP protocol, `ENFORCE` Policy engine, one `READY` OpenAPI target, two active deterministic policies |
| Guardrail-in-Policy prompt/output checks | deferred — not a pass |

The forecast request returned AgentCore's policy-enforcement denial. It did not return a provider payload. This receipt records that as the `slice-07` joined boundary observation in `datasets/evidence/production-slice-8-boundary.jsonl`.

## Guardrail limitation

The installed Terraform AWS provider supports only the plain-Cedar `definition.cedar` branch for AgentCore Policies. AWS's `when guardrails { … }` syntax requires the separate API `definition.policy` branch, which has not reached a provider release. The provider-gap detail and upstream references are recorded in [Week 11](../weeks/week-11-gateway-weather.md#4-attach-deterministic-policy-authorization).

No Console-managed or `local-exec` Policy was created to bypass Terraform ownership. Consequently, `slice-08` remains unobserved and no claim is made for prompt-attack denial or output suppression.

## Claim boundary

This proves the deployed Gateway/Identity/Policy path, not the current AgentCore Runtime package path. The existing Runtime still registers its legacy direct-weather tool; moving it to `gateway_weather.py` remains Week 13 work. This receipt also does not claim retries, circuit breaking, Guardrail-in-Policy, public-edge Guardrails, or broad evaluation coverage.

## Verification commands

```bash
terraform -chdir=infra/terraform/production-demo fmt -check
terraform -chdir=infra/terraform/production-demo validate
terraform -chdir=infra/terraform/production-demo plan -input=false
uv run --project weatheragent/app/weather_agent python3 scripts/verify_gateway_weather_boundary.py <city> --multiplier 2
```
