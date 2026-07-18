# Weekly Guides

The 16-week curriculum, one deep guide per week. The plan's front matter — North Star, specimen strategy, working assumptions, managed-evaluation boundaries, and appendices — lives in [`LEARNING_PLAN.md`](../../LEARNING_PLAN.md); read it before Week 1.

Every guide follows the same template: **Objective · Why this week exists · Concepts · Build steps · Exercises (guided discovery) · Gotchas & drift watch · Deliverable checklist · Success criteria · Docs to consult · Self-check.** Each week's success criteria are the exit gate — don't start Week N+1 with Week N's checkboxes open. Doc references were verified against live AWS/Strands docs via the AWS documentation MCP server on the date noted in each file; when a guide and the current docs disagree, **the docs win**.

## Phase 1 — Foundations (Weeks 1–4)

Learn the SDK, runtime, and tool integration seams before formalizing anything.

| Week | Guide | Deliverable |
| --- | --- | --- |
| 1 | [AgentCore & Strands Fundamentals](week-01-fundamentals.md) | Local dev environment + architecture notes |
| 2 | [Basic Agent Development with Strands](week-02-first-agent.md) | First functional agent + tool (typed failure envelope) |
| 3 | [AgentCore Runtime & Deployment](week-03-runtime-deployment.md) | AgentCore deployment proof |
| 4 | [Tool Integration Patterns](week-04-tool-integration.md) | Multi-tool agent portfolio (`@tool` / MCP / Gateway) |

## Phase 2 — Eval contract (Weeks 5–10)

One tool keeps tool-selection labels unambiguous. The eval contract is the work.

| Week | Guide | Deliverable |
| --- | --- | --- |
| 5 | [Agent/Tool Contract Architecture](week-05-tool-contracts.md) | Tool contract specification + capability manifests |
| 6 | [Tool Execution Dataset & Validation Schema](week-06-dataset-validation.md) | 100-row synthetic dataset + validators + mocks |
| 7 | [Minimal Tool-Calling Specimen](week-07-specimen.md) | Canonical trace specimen + Strands-native mapping compatibility check |
| 8 | [Local Tool Execution Harness](week-08-local-harness.md) | 62-row Strands Experiment + deterministic gates + provenance-linked offline CI report |
| 9 | [Human Tool-Selection Labeling](week-09-human-labeling.md) | Blind-labeled 64-row human fixture |
| 10 | [Tool Selection Judge Calibration](week-10-judge-calibration.md) | Three-way judge calibration + trust policy |

## Phase 3 — Complexity under contract (Weeks 11–13)

Every new tool arrives with dataset rows, gates, and regression fixtures.

| Week | Guide | Deliverable |
| --- | --- | --- |
| 11 | [Multi-Tool Integration Complexity](week-11-multi-tool-chains.md) | 5-tool chain agent + sequencing/state/cascade gates |
| 12 | [External Integration Reliability Gates](week-12-reliability-gates.md) | Real APIs, retries, breakers, honest degradation |
| 13 | [Production Agent CI Regression](week-13-ci-regression.md) | Two-lane CI pipeline + red-gate receipt |

## Phase 4 — Production & orchestration (Weeks 14–16)

Deployment as evidence: live traces, online evals, red gates, documented metrics.

| Week | Guide | Deliverable |
| --- | --- | --- |
| 14 | [Agent Execution Trace Instrumentation](week-14-observability.md) | Observability dashboard + online evaluations |
| 15 | [Advanced Agent Patterns & Safety](week-15-multi-agent-safety.md) | Multi-agent orchestration + Policy/guardrail boundaries |
| 16 | [Production Agent Architecture Reference](week-16-capstone.md) | Reference architecture, public demo, case study |
