# Week 13 — Terraform-Owned Runtime Operations

**Prerequisite:** The governed Gateway path and weather reliability boundary pass locally, including all three focused production tests.

[← Week 12](week-12-reliability-gates.md) · [Week index](README.md) · [Next: Week 14 →](week-14-managed-evaluation-ci.md)

## Concept

Release operations are part of the system contract. Package one exact Python 3.13 artifact, let Terraform create an immutable Runtime version, test it through a named STAGING endpoint, and promote only an explicitly approved version to PROD. Observability and rollback attach to that identity.

The AgentCore CLI packages the CodeZip but owns no final resources. Terraform owns the artifact bucket, Runtime, endpoints, IAM, dashboard, alarms, and lifecycle. The public proxy will invoke PROD—never DEFAULT or computed latest.

## Build

### 1. Package one reviewed Python 3.13 CodeZip

Keep the Runtime package narrow:

- `weatheragent/app/weather_agent/main.py`
- `weather_contract.py`
- `gateway_weather.py`
- `weather_reliability.py`
- `pyproject.toml` only for genuine Runtime dependencies
- `weatheragent/agentcore/agentcore.json` as a package-only manifest

Run the existing Runtime tests under Python 3.13, then use `agentcore package --directory weatheragent --runtime weather_agent`. Do not invoke the CLI deployment path or generated CDK.

Before packaging, inspect the resolved `bedrock-agentcore` version. It must be at least `1.5.1` and must not be `1.4.8` or `1.5.0`, per CVE-2026-15737. Inspect the ZIP rather than trusting the source lock alone. If an affected deployment ever existed, review its `aws/spans` data before public traffic.

### 2. Deploy the artifact and STAGING endpoint through Terraform

Add `infra/terraform/production-demo/artifacts.tf` and `runtime.tf`. Upload the hashed ZIP to a private, versioned artifact bucket and configure `aws_bedrockagentcore_agent_runtime` with the exact S3 object version, entry point, and `PYTHON_3_13` CodeZip runtime.

Create named `STAGING` and `PROD` `aws_bedrockagentcore_agent_runtime_endpoint` resources. Apply the new Runtime version to STAGING first. Run one managed weather→calculator invocation and compare its sequence, intermediate value, typed result, and failure behavior with the local receipt.

The Runtime role gets only model invocation, the intended Gateway call, telemetry, artifact read, and breaker-table item access. It gets neither the OpenWeather key nor forecast permission.

### 3. Promote one immutable version to PROD

Store only the approved Runtime version and artifact digest in `infra/terraform/production-demo/release.tf`. Do not commit an ARN, account ID, endpoint URL, or secret.

Promotion is a second reviewed apply that changes PROD's explicit version after STAGING passes. The normal rollback restores the previous approved version in `release.tf`, reviews an endpoint-only plan, and applies it. Never make PROD follow computed latest.

### 4. Add the smallest useful operations view and finish migration

Create `observability.tf` with a compact dashboard for Runtime invocations/errors, end-to-end duration, weather/Gateway failures and provider duration, retry count, and breaker-open events. Verify live namespaces, dimensions, and metric names instead of copying guesses.

Create two low-traffic, absolute-count alarms with an externally supplied SNS destination:

1. any Runtime total/system error; and
2. any breaker-open event or equivalent actionable weather dependency failure.

Test-fire both paths. Keep evidence-rich sessions synthetic and on STAGING. Before Week 15, run a harmless PROD canary and inspect proxy logs plus `aws/spans`; block public launch if raw prompt/response bodies appear. Set short explicit retention for public-demo logs.

After Terraform's Runtime, endpoints, Gateway, and two-tool invocation pass, remove the old CLI/CDK stack through its original, ownership-ordered teardown. Verify the old Runtime, Gateway, connector, generated roles, and dedicated log groups are absent without touching the Terraform resources. Preserve old declarative artifacts as history only.

### 5. Draft the runbook before the incident

Create `docs/runbooks/production-demo.md` with backend/state boundaries, saved-plan review, alarm meanings, first queries, endpoint-version rollback, known-good HCL/artifact restore-and-apply, verification, recovery criteria, and ownership-ordered teardown.

State restoration from versioned S3 is break-glass for corrupted Terraform state. It is not the normal rollback for a bad Runtime version or valid-but-bad infrastructure change.

## Deliverable

One Runtime-operations artifact group:

- `artifacts.tf`, `runtime.tf`, `release.tf`, and `observability.tf`
- `docs/reports/week-13-runtime-operations.md`
- `docs/assets/week-13-two-tool-trace.png`
- draft `docs/runbooks/production-demo.md`

## Success check

Ryan can package one hashed Python 3.13 CodeZip, apply it through Terraform to STAGING, promote only its immutable version to PROD in a second endpoint-only plan, follow one two-tool invocation in CloudWatch, test-fire both alarm paths, prove the old CLI/CDK resources are absent, and identify the exact endpoint rollback and known-good Terraform recovery commands without improvising.

## Read

- [Terraform AgentCore Runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_agent_runtime)
- [Terraform Runtime endpoint](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_agent_runtime_endpoint)
- [AgentCore Runtime versioning](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html)
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [AWS security bulletin 2026-058](https://aws.amazon.com/security/security-bulletins/2026-058-aws/)