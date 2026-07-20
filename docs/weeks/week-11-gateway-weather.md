# Week 11 — Terraform, Identity, Gateway, and Policy

**Prerequisite:** The eight-case gold set and custom-judge contract are frozen. Final durable infrastructure has no owner yet.

[← Week 10](week-10-judge-calibration.md) · [Week index](README.md) · [Next: Week 12 →](week-12-reliability-gates.md)

## Concept

This week gives the final system one infrastructure owner and one governed external-tool boundary. Terraform owns the durable resources. AgentCore Identity owns the OpenWeather key, Gateway invokes the OpenAPI target, deterministic Policy authorizes operations, and a narrow Runtime wrapper is the only weather tool the model sees.

The direct calculator stays outside Gateway. Identity does not normalize responses or retry calls. Gateway Policy/Guardrail checks do not govern calculator arguments or the final model response. Week 15 adds a separate Bedrock Guardrail at the public proxy; it is not the Guardrail-in-Policy mechanism used at Gateway.

## Build

### 1. Establish remote Terraform state and migration boundaries

Create three flat roots with separate S3 state keys:

- `infra/terraform/state-bootstrap/`: one private, encrypted, versioned, Block-Public-Access state bucket;
- `infra/terraform/production-demo/`: the final system; and
- existing `infra/terraform/budget/`: the account Budget, migrated but not duplicated.

Require Terraform `>= 1.11`, AWS provider `>= 6.53, < 7.0`, and native S3 `use_lockfile = true`. Ignore partial `*.tfbackend` configuration while tracking provider lock files. Bootstrap locally once, move the bootstrap state into its own key, back up the existing Budget state, migrate it with `terraform init -migrate-state`, and require a no-surprise plan after each move.

Do not import resources still owned by the historical CLI/CDK CloudFormation stack. Create distinct Terraform names, cut over after real-path verification, and tear the old stack down through its original owner in Week 13. Never hide durable resources behind a provisioner or `local-exec`.

### 2. Build Identity, Gateway, and the OpenAPI target in Terraform

Create `schemas/openweather-gateway.openapi.yaml` with current weather plus an unregistered forecast operation used only for the denial probe. Manage the Gateway, execution IAM, API-key credential provider, OpenAPI target, Policy engine, and Policy with first-class `aws_bedrockagentcore_*` resources.

Supply the OpenWeather key through an `ephemeral = true`, `sensitive = true` variable to `api_key_wo`, with a non-secret `api_key_wo_version`. Attach the credential provider to the target as query parameter `appid`. The value must not appear in source, Runtime configuration, a saved plan, or state. The Runtime role may invoke only the intended Gateway and cannot retrieve the key.

### 3. Expose only the narrow wrapper and calculator to the model

Create `weatheragent/app/weather_agent/gateway_weather.py`. It accepts the existing city/units contract, calls only current weather, and normalizes the raw Gateway/provider response into the typed weather envelope. Reuse `src/tools/calculator.py` directly.

The raw current-weather and forecast operations are never model-visible. The forecast probe exists only to produce one deterministic denial receipt and is never called again afterward. Week 12 adds deadline, retry, and breaker behavior; Week 11 proves only happy-path normalization.

### 4. Attach deterministic Policy authorization

Run one Terraform-managed AgentCore Policy engine in `ENFORCE`. Author the smallest reviewed rules that permit current weather and deny forecast/unapproved actions. The reviewed unconditional operation rules require `IGNORE_ALL_FINDINGS`: AgentCore's analyzer identifies their intended all-scope allow/deny effect, while schema validation remains enabled.

**Provider gap:** AWS provider `6.55.0` exposes only `definition.cedar`, while AgentCore Guardrail statements require the API's separate `definition.policy` union member. The upstream provider work remains open ([#48648](https://github.com/hashicorp/terraform-provider-aws/issues/48648), [#48711](https://github.com/hashicorp/terraform-provider-aws/pull/48711)). Do not add `local-exec` or Console-owned policies to bypass Terraform ownership. Guardrail-in-Policy checks, `bedrock:InvokeGuardrailChecks`, and the prompt-attack/output-safeguard receipt are deferred until that support ships.

### 5. Apply, probe, and read back

Run `terraform fmt -check`, `terraform validate`, an inspectable saved plan, explicit apply, service readback, and a second no-drift plan. Capture:

1. allowed current-weather invocation;
2. denied unregistered forecast invocation under the intended principal context; and
3. record the unavailable prompt-attack Guardrail probe as a provider-gap limitation rather than a pass.

Use the forecast receipt to create the authorization observation in `datasets/evidence/production-slice-8-boundary.jsonl`; do not mutate the frozen Week 9 human-gold file. The deferred Guardrail row remains pending in the report rather than becoming a pass. Each observation joins `slice-07` or `slice-08` by `case_id`, `expectation_version`, and the matching frozen `expectation_sha256`, then records `observation_status`, boundary verdict, control, repository-relative receipt reference, tested scope, and observation time. Reject a row whose ID/version/digest does not match gold.

Keep the tracked evidence public-safe: no account IDs, ARNs, request IDs, live endpoints, raw prompts/responses, private paths, or principal identifiers. Both rows remain excluded from custom and managed tool-accuracy judges.

## Deliverable

One governed-boundary artifact group:

- `infra/terraform/state-bootstrap/`
- `infra/terraform/production-demo/` state/IAM/AgentCore files
- `schemas/openweather-gateway.openapi.yaml`
- `weatheragent/app/weather_agent/gateway_weather.py`
- `docs/reports/week-11-production-gateway-boundary.md`
- `datasets/evidence/production-slice-8-boundary.jsonl`

The AgentCore CLI may package, validate, inspect, invoke, or evaluate; do not use its deploy path for final resources.

## Success check

Terraform creates the deterministic Gateway boundary without CloudFormation co-ownership; one local weather→calculator trace succeeds through the wrapper with the exact intermediate value; Identity injects the key without exposing it in Runtime, plan, or state; the forecast probe is denied by Policy; the Guardrail receipt is explicitly deferred for the provider gap; and the repeat plan shows no unexpected change.

## Read

- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Terraform Gateway target](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_gateway_target)
- [Terraform API-key credential provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_api_key_credential_provider)
- [Add an OpenAPI Gateway target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html)
- [Guardrail checks in AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)