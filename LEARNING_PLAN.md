# AgentCore & Strands: 16-Week Eval-First Agent Development Plan

## Purpose

This is a learning-by-doing sequel to [aws-ai-evals](https://github.com/rhprasad0/aws-ai-evals). The finished specimen stays deliberately small: a Strands agent with exactly two capabilities—current weather and calculator—deployed through Terraform-owned Amazon Bedrock AgentCore infrastructure.

The goal is not a feature catalog. It is one inspectable vertical slice that teaches contracts, deterministic gates, human expectations, judge comparison, outbound credentials, policy, reliability, observability, CI, public-edge controls, and recovery without hiding behind platform machinery.

The claim remains narrow: **measured behavior on named cases under a pinned configuration**. The hosted endpoint is a capped learning demo, not proof of production readiness, broad safety, or generalization.

## What Weeks 1–7 built and what Week 8 must close

Weeks 1–7 are frozen historical foundation:

| Week | Completed foundation |
| --- | --- |
| 1 | Local Strands/AgentCore toolchain, first agent loop, architecture notes, Terraform Budget. |
| 2 | Typed weather tool and agent with explicit failure envelopes. |
| 3 | Managed Runtime deployment, invocation, isolation/IAM observations, telemetry, and teardown. |
| 4 | Direct, MCP, and Gateway tool seams with explicit registration and measured comparison. |
| 5 | Versioned tool contracts, capability manifests, failure taxonomy, and Runtime IAM denials. |
| 6 | Reviewed 100-row corpus, deterministic mocks, canonical traces, validators, and safe fixtures. |
| 7 | Pinned weather-only specimen and two normalized 62-case executions with explicit instrument errors. |

Week 8 is in progress under a reduced closeout contract. Keep the existing harness, fixtures, adapters, gates, schemas, and reporting code. Close it only when one fixture-backed Stage B run:

1. accounts for all 62 projected cases;
2. keeps instrument and gate errors outside behavioral denominators;
3. renders one canonical JSON aggregate and one Markdown view from that aggregate;
4. passes the existing focused harness/reporting tests and local diff checks; and
5. records one provenance-linked baseline receipt.

Do not add the superseded three-baseline/three-changed sensitivity campaign, a second cache or fixture architecture, another PR workflow, or a broad mutation matrix.

## Ruthless-minimalism rules

- Follow the weeks in order. A later week may not smuggle work into the current one.
- Every remaining artifact must serve the same weather→calculator path.
- Prefer a direct call path and one readable file over reusable frameworks.
- Add only the schema, helper, dependency, service, or workflow required by the current boundary.
- Exactly three planned production tests remain: retry budget, shared breaker transitions, and stop-before-calculator behavior. Other tests are bug-triggered.
- One real receipt beats a checklist of implied capability.
- Current AWS, Terraform Registry, and Strands documentation wins over this paraphrase.

## Working assumptions

- Region examples use `us-east-1`; verify feature availability and account enablement before each managed step.
- Terraform `>= 1.11` and HashiCorp AWS provider `>= 6.53, < 7.0` own final durable infrastructure.
- The final CodeZip Runtime uses Python 3.13. The AgentCore CLI may package, validate, inspect, invoke, and run evaluations; it does not deploy the final resources.
- `infra/terraform/state-bootstrap/` owns the encrypted, versioned, lock-enabled S3 backend; `infra/terraform/production-demo/` owns the final system; `infra/terraform/budget/` retains the account Budget under a separate state key.
- Existing CLI/CDK/CloudFormation resources remain migration history until Terraform cutover, then are removed through their original owner. Never put one live resource under two owners.
- Managed calls cost money. Confirm scope before model-backed evaluation, deployment, a WAF-enabled public edge, or repeated live probes.
- Tracked examples use placeholders and synthetic evidence. Operational identifiers, credentials, raw anonymous traffic, and private state stay out of public artifacts.

## Final vertical-slice architecture

```text
Browser
  ↓
CloudFront + WAF rate rule
  ├─ private S3 UI via OAC
  └─ `/api/*` → IAM-protected Lambda Function URL via OAC/SigV4
       ├─ proxy Bedrock Guardrail: ApplyGuardrail(INPUT)
       ├─ DynamoDB enabled flag + atomic 10-Runtime-calls/day counter
       ├─ named PROD AgentCore Runtime endpoint
       │    └─ immutable Runtime version
       │         ├─ narrow weather wrapper
       │         │    ├─ total deadline + one retry + shared DynamoDB breaker
       │         │    └─ AgentCore Gateway
       │         │         ├─ Policy permits current weather and denies forecast
       │         │         ├─ native Policy guardrail checks on Gateway input/output
       │         │         └─ OpenWeather OpenAPI target
       │         │              └─ Identity injects `appid`; Runtime never sees it
       │         └─ direct calculator tool
       └─ proxy Bedrock Guardrail: ApplyGuardrail(OUTPUT)

CloudWatch traces/dashboard/alarms → SNS
Existing Terraform-managed AWS Budget → $10 monthly limit and direct email alerts
Synthetic STAGING spans → custom judge + AgentCore Evaluations
Committed replay + three focused tests → offline pull-request gate
Manual GitHub OIDC job → one metered same-evidence evaluation run
```

Ownership is intentionally split by responsibility:

- Identity stores and injects the OpenWeather key.
- Gateway invokes the provider target.
- AgentCore Policy deterministically authorizes Gateway actions and runs native probabilistic checks there.
- The Runtime wrapper owns model-visible naming, typed inputs, response normalization, deadline, retry, and breaker behavior.
- The direct calculator does not pass through Gateway Policy.
- The public proxy's separate Bedrock Guardrail covers browser input and final output; it is not the native Policy guardrail mechanism.
- Terraform owns durable resources and named endpoint promotion. The normal rollback is an HCL change, reviewed plan, and apply—not state surgery.

## Scope and non-goals

The broad deterministic baseline remains the 62-case weather projection. Weeks 9–16 add exactly eight reviewed cases:

1. weather only;
2. calculator only;
3. metric weather→calculator;
4. imperial weather→calculator;
5. weather failure stops before calculator;
6. no-tool or clarification behavior;
7. deterministic Policy denial; and
8. native Gateway guardrail denial.

Only the first six are eligible for human/custom/managed tool-accuracy comparison. The two denial rows receive boundary-specific verdicts and never enter tool-selection or parameter-accuracy denominators. This eight-row comparison is a worked example, not calibrated population evidence: report counts and every disagreement, not impressive percentages without denominators.

Explicitly absent: a five-tool chain, write action, generalized resilience package, labeling app, second rater, kappa target, repeated judge campaign, nightly managed lane, online-evaluation program, Memory exercise, Graph, Swarm, A2A, optimizer trial, Cognito, API Gateway, React, or organization-scale operations platform.

## Managed evaluation boundaries (read before Week 8)

- A judge score is a measurement, not truth. Freeze human expectations before output and freeze the custom rubric before final Runtime evidence.
- Collect the six eligible synthetic STAGING spans once from one immutable Runtime version. The custom judge and both managed built-ins evaluate those exact spans.
- Record case ID, Runtime version, trace/span identity, evaluator ID, run date, eligibility, and transport. If those joins are missing, the comparison is invalid.
- `Builtin.ToolSelectionAccuracy` and `Builtin.ToolParameterAccuracy` are moving managed dependencies; a local schema pass does not prove service acceptance.
- A single custom-judge run is a sanity check. It does not establish stability, calibration, or generalization.
- The manual OIDC job is the only metered comparison path. Pull-request CI remains fixture-backed and cloud-free.
- Anonymous PROD telemetry is for operations, not evaluator-rich evidence. Block public launch if a harmless canary shows raw prompts or responses in proxy logs or `aws/spans`.

## Source links

- [AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)
- [AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
- [AgentCore Evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [Terraform AgentCore Runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_agent_runtime)
- [Terraform AgentCore Gateway](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_gateway)
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Strands Agents](https://strandsagents.com/docs/user-guide/quickstart/python/)
- [Strands Evals](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/)

# The 16 Weeks

Each guide's success check is its exit gate. Completed guides may describe historical future ideas; this map supersedes them.

| Week | Status | Focus | Bounded outcome |
| --- | --- | --- | --- |
| [1](docs/weeks/week-01-fundamentals.md) | Closed | Fundamentals | Local toolchain, agent loop, architecture, and Budget. |
| [2](docs/weeks/week-02-first-agent.md) | Closed | First agent | Typed weather agent and explicit failures. |
| [3](docs/weeks/week-03-runtime-deployment.md) | Closed | Runtime | Managed invocation, isolation/IAM evidence, telemetry, teardown. |
| [4](docs/weeks/week-04-tool-integration.md) | Closed | Tool seams | Direct, MCP, Gateway, registration, and seam comparison. |
| [5](docs/weeks/week-05-tool-contracts.md) | Closed | Contracts | Schemas, manifests, taxonomy, and IAM denials. |
| [6](docs/weeks/week-06-dataset-validation.md) | Closed | Dataset | 100 reviewed rows, mocks, traces, validators. |
| [7](docs/weeks/week-07-specimen.md) | Closed | Specimen | Pinned 62-case weather projection and normalized traces. |
| [8](docs/weeks/week-08-local-harness.md) | In progress | Harness closeout | One provenance-accounted fixture-backed 62-case baseline. |
| [9](docs/weeks/week-09-human-labeling.md) | Planned | Human gold | Eight preregistered expectations: six behavior, two denials. |
| [10](docs/weeks/week-10-judge-calibration.md) | Planned | Judge contract | One frozen prompt/script and dry run; no model call. |
| [11](docs/weeks/week-11-gateway-weather.md) | Planned | Terraform + Gateway | Remote state, Identity/OpenAPI target, Policy, native guardrail checks, allow/deny receipts. |
| [12](docs/weeks/week-12-reliability-gates.md) | Planned | Reliability | Deadline, one retry, shared breaker, three tests, failure probes. |
| [13](docs/weeks/week-13-runtime-operations.md) | Planned | Runtime operations | Python 3.13 CodeZip, STAGING/PROD promotion, telemetry, two alarms, old-stack teardown. |
| [14](docs/weeks/week-14-managed-evaluation-ci.md) | Planned | Managed eval + CI | Same-evidence comparison, offline PR gate, manual OIDC run, red/green receipt. |
| [15](docs/weeks/week-15-hosted-demo.md) | Planned | Hosted demo | CloudFront UI, proxy Guardrail, daily cap, kill switch, WAF, $10 Budget. |
| [16](docs/weeks/week-16-capstone.md) | Planned | Incident drill | Alarm, kill, endpoint rollback, Terraform recovery, controlled keep-live closeout. |

# Appendix A — Week × Capability Map

| Weeks | Primary capability |
| --- | --- |
| 1–4 | Strands/Runtime/Gateway foundations and tool seams. |
| 5–8 | Contracts, corpus, canonical traces, deterministic local evaluation. |
| 9–10 | Human expectations and one frozen custom-judge contract. |
| 11–12 | Terraform state, Identity/IAM, Policy/guardrails, weather reliability. |
| 13–14 | Runtime versions/endpoints, CloudWatch/SNS, managed evaluation, OIDC CI. |
| 15–16 | CloudFront/WAF public boundary, Budget, operations and recovery. |

# Appendix B — Metrics Glossary

Every metric names its unit, eligible population, numerator, denominator, and excluded instrument/gate errors. Empty populations render `null`, never a flattering zero or hundred percent.

- **Tool selection accuracy:** eligible behavioral cases whose observed tool set and call bounds match the expectation.
- **Tool parameter accuracy:** eligible expected-tool calls whose normalized arguments satisfy the declared constraints.
- **Execution success rate:** contract-valid observed calls returning `ok: true`, reported separately from selection.
- **Failure-behavior compliance:** eligible failure cases that satisfy the declared stop/degradation contract.
- **No-tool compliance:** eligible no-tool cases with zero observed calls.
- **Instrument validity:** all projected outcomes with schema- and semantic-valid evidence; errors remain visible outside behavioral denominators.
- **Judge agreement:** counts of matching and disagreeing verdicts over the six eligible rows, with every disagreement listed.
- **Boundary verdict:** observed allow/deny/control evidence for Policy or Guardrail rows; never blended into judge metrics.

# Appendix C — Guardrails

The completed dataset/fixture publication machinery is historical foundation, not future curriculum scope. Tracked evidence still uses synthetic inputs, placeholders, explicit provenance, and scoped claims.

Live production controls are different: deterministic AgentCore Policy and native guardrail checks protect Gateway traffic, while a separate Bedrock Guardrail protects public proxy input/output. Neither covers the direct calculator as a Gateway tool boundary. WAF, the daily Runtime cap, kill switch, alarms, and Budget each control a different risk; no one control is a hard account-wide spend or safety guarantee.

Judges remain measurements. Deployment remains evidence. Terraform state restoration remains break-glass. The honest sentence is always available: **measured X on Y under Z**.