# Weekly Guides

The curriculum converges on one Terraform-owned weather→calculator AgentCore system. Completed Weeks 1–7 remain historical foundation; Week 8 closes the existing harness; Weeks 9–16 each add one bounded production boundary or operating outcome.

Read [`LEARNING_PLAN.md`](../../LEARNING_PLAN.md) first. Each guide has one integrated success check; do not start the next week while it is open. Current AWS, Strands, and Terraform documentation wins when a guide drifts.

## Phase 1 — Foundation and harness closeout (Weeks 1–8)

| Week | Guide | Outcome |
| --- | --- | --- |
| 1 | [AgentCore & Strands Fundamentals](week-01-fundamentals.md) | Local toolchain, agent loop, architecture, Budget |
| 2 | [Basic Agent Development with Strands](week-02-first-agent.md) | Typed weather tool and explicit failures |
| 3 | [AgentCore Runtime & Deployment](week-03-runtime-deployment.md) | Managed execution, IAM/isolation evidence, teardown |
| 4 | [Tool Integration Patterns](week-04-tool-integration.md) | Direct/MCP/Gateway seams and registration |
| 5 | [Agent/Tool Contract Architecture](week-05-tool-contracts.md) | Contracts, manifests, taxonomy, IAM denials |
| 6 | [Tool Execution Dataset & Validation](week-06-dataset-validation.md) | 100 rows, mocks, traces, validators |
| 7 | [Minimal Tool-Calling Specimen](week-07-specimen.md) | Pinned 62-case weather projection |
| 8 | [Local Harness Closeout](week-08-local-harness.md) | One fixture-backed 62-case baseline receipt |

## Phase 2 — Tiny gold set and judge contract (Weeks 9–10)

| Week | Guide | Outcome |
| --- | --- | --- |
| 9 | [Human Gold for the Final Slice](week-09-human-labeling.md) | Eight frozen expectations: six behavior, two denials |
| 10 | [One Custom Judge Contract](week-10-judge-calibration.md) | Frozen rubric, provider-free dry run, six-vector calibration, and six-case local evaluation |

## Phase 3 — Governed weather path (Weeks 11–12)

| Week | Guide | Outcome |
| --- | --- | --- |
| 11 | [Terraform, Identity, Gateway, and Policy](week-11-gateway-weather.md) | Remote state, OpenAPI target, Policy/guardrails, allow/deny receipts |
| 12 | [Weather Reliability Boundary](week-12-reliability-gates.md) | Deadline, one retry, shared breaker, three focused tests |

## Phase 4 — Runtime, evaluation, and CI (Weeks 13–14)

| Week | Guide | Outcome |
| --- | --- | --- |
| 13 | [Runtime Operations](week-13-runtime-operations.md) | Python 3.13 CodeZip, STAGING/PROD promotion, telemetry, alarms |
| 14 | [Same-Evidence Evaluation and CI](week-14-managed-evaluation-ci.md) | Custom/managed comparison, offline PR gate, manual OIDC run |

## Phase 5 — Hosted demo and incident drill (Weeks 15–16)

| Week | Guide | Outcome |
| --- | --- | --- |
| 15 | [Capped Hosted Demo](week-15-hosted-demo.md) | CloudFront edge, proxy Guardrail, cap, kill switch, WAF, $10 Budget |
| 16 | [Capstone Incident Drill](week-16-capstone.md) | Alarm, kill, rollback, Terraform recovery, controlled closeout |

The final system is a hosted learning demo. Passing its checks is scoped evidence about named cases and controls, not a production-readiness or safety certificate.