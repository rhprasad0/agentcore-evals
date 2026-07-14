# AgentCore Evals

**A 16-week, eval-first learning plan for building tool-calling agents with the Strands Agents SDK and Amazon Bedrock AgentCore — where tool selection accuracy and execution reliability are measured contracts, not vibes.**

This is the sequel to [aws-ai-evals](https://github.com/rhprasad0/aws-ai-evals), a 12-week project that built an evaluation harness around a deliberately boring chatbot: schemas, synthetic datasets, human labels, judge calibration, managed Bedrock eval jobs, and a CI gate that caught a real regression on camera. That project's guardrails explicitly deferred agent and tool-use evaluation to a future plan. This repo is that plan.

The curriculum lives in [`LEARNING_PLAN.md`](LEARNING_PLAN.md) (methodology, guardrails, and the week index), with one deep hands-on guide per week in [`docs/weeks/`](docs/weeks/README.md). This README is the map: what gets built, in what order, and how to follow along or fork it.

## The methodology in five bullets

1. **Define "correct tool use" before building more tools.** Tool contracts, capability manifests, and a failure taxonomy come before the fun parts.
2. **Deterministic gates before LLM judges.** Schema validators, tool-selection gates, and sequence checks are cheap, explainable, and never hallucinate.
3. **Humans are the only ground truth.** A blind-labeled 64-row fixture calibrates every judge — the self-built one *and* AWS's managed evaluators — before either is trusted.
4. **Deployment is evidence.** The agent ships so that CI regression gates, online evaluations, and dashboards have something real to measure. A preserved red-gate screenshot beats a green-badge collection.
5. **Optimizers face holdouts.** Proposed improvements (including AgentCore's managed recommendations) are adopted or rejected based on rows they never saw — and rejections get published too.

## Why AgentCore + Strands, and why now

Amazon Bedrock AgentCore went GA in October 2025 as composable infrastructure for agents built with any framework: **Runtime** (session-isolated serverless hosting), **Gateway** (APIs/Lambda/MCP servers as governed MCP tools), **Memory**, **Identity**, **Policy**, built-in tools (Code Interpreter, Browser, Web Search), and OpenTelemetry-based **Observability**. Through 2026 the evaluation story matured fast: **AgentCore Evaluations** (GA March 2026) ships built-in judges down to the tool level — `Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy` — plus online/on-demand/batch modes, custom evaluators, and an optimization loop (recommendations, batch validation, A/B testing, GA June 2026). The **AgentCore CLI** (`npm install -g @aws/agentcore`) scaffolds, runs, and deploys agents with CDK under the hood.

[Strands Agents](https://strandsagents.com/) is the open-source, model-driven SDK this plan builds on (Python, `strands-agents` 1.x), with first-class MCP support, multi-agent patterns (Graph, Swarm, workflow, A2A v1.0), OTEL-native tracing, and a dedicated evals SDK (`strands-agents-evals`).

That maturity is the point of the exercise: the managed services will happily score your agent. This repo builds the ground truth that says whether to believe them — and publishes the agreement numbers.

## What 16 weeks produces

- A deployed multi-tool Strands agent on AgentCore Runtime, every tool behind an explicit schema-validated contract — no magic tool discovery.
- A 100-row synthetic tool-calling dataset + deterministic local harness (tool selection, parameter fidelity, sequencing, failure behavior) that runs offline in CI.
- A 64-row blind human-labeled fixture and a **three-way judge calibration**: human labels vs a self-built blind judge vs AgentCore's managed evaluators, with published agreement, false-pass/false-fail rates, and a written trust policy.
- Resilience under real external APIs: retries, circuit breakers, honest degradation — evaluated with injected outages, not asserted.
- A two-lane CI regression pipeline (deterministic fixtures on PR, managed batch evaluation against the deployed agent on merge) with a preserved red-gate receipt.
- Production observability: scrubbed OTEL traces, online evaluation sampling, a CloudWatch dashboard, and alarms on selection-accuracy drift.
- Multi-agent orchestration (Graph/Swarm/A2A) with coordination accuracy measured, and safety boundaries (AgentCore Policy + Gateway-level guardrails) enforced outside agent code and probed with inert adversarial rows.
- A public demo, a metrics page fed by real eval artifacts, and a LinkedIn case study.

## Prerequisites

- An AWS account with Bedrock **model access granted** (Claude models for agent + judges) in `us-east-1`, and permissions for AgentCore, IAM, CloudWatch, Lambda, and CDK bootstrap.
- **Python 3.10+** (agent code), **Node.js 20+** (the AgentCore CLI is an npm package), Docker only if you choose container builds.
- Comfort with AWS fundamentals, Python, and basic ML concepts. **No prior AgentCore or Strands experience assumed** — Week 1 starts from install.
- A free OpenWeatherMap API key (Week 2) and a search API key (Week 11).
- **Budget awareness:** everything managed is consumption-billed (Runtime per-second, Evaluations per judged token, Gateway per call). The plan is structured so Weeks 5–10 run almost entirely local/mocked; deployed-lane weeks include teardown steps (`agentcore remove all` + `agentcore deploy`) and a Budgets alarm is a Week 1 deliverable. Expect low double-digit USD per month during cloud-heavy weeks if you tear down diligently.

## Repository structure

```text
agentcore-evals/
  README.md                  # you are here
  LEARNING_PLAN.md           # the 16-week curriculum (hub + week index)
  docs/                      # architecture notes, reports, receipts, screenshots
    weeks/                   # one deep guide per week (week-NN-*.md)
  schemas/                   # tool contracts, manifests, datasets, traces, labels, judge output
  datasets/                  # synthetic scenarios, human-label fixtures, CI regression fixtures
  src/                       # agents, tools (+ mocks), contracts, trace adapters, judges
  evals/                     # Strands Evals adapters, cases/experiments, deterministic gates, harness
  scripts/                   # dataset validator, safety scanner, label workbench, run summarizer
  infra/                     # dashboards & anything outside CLI-managed CDK
  .github/workflows/         # CI regression lanes
```

The tree grows week by week; nothing lands in `main` without its schema, validator, or fixture.

## The 16-week schedule

| Status | Week | Focus | Outcome | Deliverable |
|--------|------|-------|---------|-------------|
| ✅ Closed | **1** | **[AgentCore & Strands Fundamentals](docs/weeks/week-01-fundamentals.md)** | Understand AgentCore architecture (Runtime, Gateway, Memory, Identity, Observability), Strands SDK basics, MCP protocol, and A2A communication. Set up local development environment. | **Local Dev Environment + Architecture Notes** - Working Strands installation, AgentCore CLI setup, ["Hello World" agent](src/agents/hello.py) that calls one AWS service, [trace inspection note](docs/hello-agent-loop.md), [architecture notes](docs/architecture.md), and [Terraform-managed cost guardrails](docs/cost-guardrails.md). |
| ✅ Closed | **2** | **[Basic Agent Development with Strands](docs/weeks/week-02-first-agent.md)** | Build first Strands agent with single tool, understand agent loop (reasoning → tool selection → execution → response), deploy to local runtime, and explore model providers (Bedrock, Anthropic, OpenAI). | **First Functional Agent + Tool** - Weather agent using Strands that calls OpenWeatherMap API, returns typed failure envelopes, includes scrubbed conversation notes, and adds a second `@tool` schema-inspection exercise with temperature conversion. |
| ✅ Closed | **3** | **[AgentCore Runtime & Deployment](docs/weeks/week-03-runtime-deployment.md)** | Deploy Strands agent to AgentCore Runtime, understand serverless agent hosting, session isolation, execution identity, and trace-based observability. Compare local vs. managed behavior with measured evidence. | **AgentCore Deployment Proof** - CodeZip deployment through the CLI-generated CDK stack, [local-vs-managed comparison](docs/local-vs-agentcore.md), [public-safe latency measurements](docs/assets/week-03-latency-measurements.json), [trace anatomy](docs/trace-anatomy.md), [execution-role baseline](docs/execution-role-baseline.md), measured Runtime cost, and verified final teardown. |
| ✅ Closed | **4** | **[Tool Integration Patterns](docs/weeks/week-04-tool-integration.md)** | Explore MCP tool integration, custom tool creation with @tool decorator, AgentCore Gateway for API transformation, and tool discovery patterns. Build 2-3 simple tools. | **Multi-Tool Agent Portfolio** - Agent with 3 tools (weather, calculator, web search), MCP integration example, custom Gateway transformation, and tool discovery/registration code with clear boundaries. |
| ✅ Closed | **5** | **[Agent/Tool Contract Architecture](docs/weeks/week-05-tool-contracts.md)** | Formalize tool interface contracts, agent capability boundaries, execution context isolation, and explicit tool-failure handling patterns. No "magic tool discovery" - explicit tool registration and capability declaration. | **Tool Contract Specification** - Exact-version contracts, manifest enforcement, shared dataset/run binding identity, Runtime IAM/session-isolation evidence, and contract-validation CI are complete. |
| ⬜ Planned | **6** | **[Tool Execution Dataset & Validation Schema](docs/weeks/week-06-dataset-validation.md)** | A 100-row reviewed tool-calling corpus, canonical trace schema, synthetic Strands inline/ADOT-split compatibility fixtures, exact-version mocks, and CI validators. | **Synthetic Dataset + Validators** — Version-bound corpus, tested telemetry mapping, deterministic canonical projection, and public-safe validation fixtures. |
| ⬜ Planned | **7** | **[Minimal Tool-Calling Specimen](docs/weeks/week-07-specimen.md)** | Single-tool agent specimen with a pinned Strands telemetry profile, canonical normalized traces, and a bounded Strands Evals Session-mapping compatibility check. | **Instrumented Agent Specimen** — Single-tool agent with tested trace normalization, explicit null handling for absent pre-tool text, controlled mocks, and a public-safe native-mapper comparison. |
| ⬜ Planned | **8** | **[Local Tool Execution Harness](docs/weeks/week-08-local-harness.md)** | Map validated rows into a versioned Strands Experiment, run repo-owned deterministic evaluators, separate metered generation from cached/offline gating, and report through Python/CLI paths. | **Local Evaluation Harness** — Dataset-to-Case adapter, custom gates, private manifest-namespaced result store, public-safe reports, and cloud-free PR execution. |
| ⬜ Planned | **9** | **[Human Tool-Selection Labeling](docs/weeks/week-09-human-labeling.md)** | Browser workflow for labeling correct tool choices, execution quality assessment, multi-step reasoning validation, and 64-row fixture: tool selection accuracy, execution reliability, error recovery patterns. | **Human Labeling Workflow** - Browser-based labeling interface, 64-row human-labeled fixture (tool selection + execution quality), blind evaluation process, and inter-rater reliability metrics. |
| ⬜ Planned | **10** | **[Tool Selection Judge Calibration](docs/weeks/week-10-judge-calibration.md)** | Claude judge predicts tool selection correctness and execution quality against human labels. Separate reasoning evaluation from execution validation - judge can't see actual tool outputs. | **Automated Judge System** - Claude judge that predicts tool selection correctness, agreement metrics vs human labels, false positive/negative analysis, and separate reasoning evaluation pipeline. |
| ⬜ Planned | **11** | **[Multi-Tool Integration Complexity](docs/weeks/week-11-multi-tool-chains.md)** | Expand to 3-5 tools with dependency chains (e.g., search → summarize → email). Eval tool sequencing logic, intermediate state handling, and cascade failure patterns. | **Multi-Tool Chain Agent** - Agent with 5+ tools in dependency chains, tool sequencing logic, intermediate state handling, cascade failure recovery, and execution flow visualization. |
| ⬜ Planned | **12** | **[External Integration Reliability Gates](docs/weeks/week-12-reliability-gates.md)** | Real external APIs with rate limits, failures, and timeouts. Eval retry logic, graceful degradation, and user communication during tool failures. Circuit breaker patterns. | **Production Integration Gates** - Agent with real external APIs, rate limiting, timeout handling, retry logic, circuit breakers, and user communication during failures with live demo. |
| ⬜ Planned | **13** | **[Production Agent CI Regression](docs/weeks/week-13-ci-regression.md)** | Deployed tool-calling agent with live external integrations, committed regression fixtures for tool selection accuracy, execution reliability gates, and red-gate proof of catching tool-selection regressions. | **CI/CD Regression Pipeline** - Deployed agent with automated regression tests, committed fixtures, red-gate screenshot catching tool-selection regression, and GitHub Actions workflow. |
| ⬜ Planned | **14** | **[Agent Execution Trace Instrumentation](docs/weeks/week-14-observability.md)** | Normalized trace schema for tool selection reasoning, execution timing, error patterns, and user satisfaction signals. CloudWatch integration without logging sensitive API responses. | **Observability Dashboard** - CloudWatch dashboard showing tool selection patterns, execution timing, error rates, user satisfaction signals, and distributed tracing without sensitive data logging. |
| ⬜ Planned | **15** | **[Advanced Agent Patterns & Safety](docs/weeks/week-15-multi-agent-safety.md)** | Multi-agent orchestration (Graph, Swarm, Workflow patterns), agent-to-agent communication (A2A), safety guardrails, and capability limitation enforcement. Eval coordination accuracy and safety boundary violations. | **Multi-Agent Orchestration** - Graph/Swarm/Workflow pattern implementation, A2A communication demo, safety guardrails, coordination accuracy metrics, and agent handoff patterns. |
| ⬜ Planned | **16** | **[Production Agent Architecture Reference](docs/weeks/week-16-capstone.md)** | Complete agent deployment with tool portfolio, execution monitoring, safety guardrails, and eval-driven improvement pipeline. Public demo with documented tool selection accuracy and reliability metrics. | **Production Reference Architecture** - Complete deployed system with public demo, documented metrics (tool accuracy, reliability), eval-driven improvement pipeline, and LinkedIn-ready case study. |

**Week 5 closed — 2026-07-14.** The repo now has tool-contract and capability-manifest schemas, exact-version contract instances, fail-closed manifest enforcement over the registered direct/discovered portfolio, constructor-inventory checks, a contract-owned failure taxonomy, and a shared exact-version binding resolver for future dataset/run consumers. A separate scratch Runtime preserved the selected model, normalized weather adapter, logs, and traces while denying an adjacent model, configuration-bundle deletion, and CloudWatch log reads under its actual execution role; a same-session/different-session canary supplied the bounded isolation receipt. The canonical `uv run --locked python -m scripts.validate_contracts` command validates schemas, fixtures, checked-in contracts, manifests, exact identities, and grant resolution in [CI](.github/workflows/contract-validation.yml). Links: [`docs/tool-contract-spec.md`](docs/tool-contract-spec.md), [`docs/reports/week-05-runtime-iam-isolation.md`](docs/reports/week-05-runtime-iam-isolation.md), [`docs/assets/week-05-runtime-iam-isolation.json`](docs/assets/week-05-runtime-iam-isolation.json). The scratch role was an operational probe and was torn down rather than encoded as durable IaC; Weeks 6–7 still own their dataset and run manifests rather than being pulled forward.

Every deliverable is designed to be **demo-ready** (shows in an interview), **linkable** (LinkedIn/portfolio), **code-complete** (runs from a fresh clone), and **metrics-proven** (numbers with receipts).

## Progress log

One dated entry per closed week, linking the artifacts. Convention:

> **Week N closed — YYYY-MM-DD.** One-sentence outcome. Links: report, code, receipt. One honest sentence about what didn't work.

> **Week 1 closed — 2026-07-08.** Set up the local Strands/AgentCore toolchain, built a minimal AWS identity tool-calling agent, inspected the scrubbed message trace, wrote the AgentCore service map, and moved the budget alarm into Terraform at a $100/month guardrail. Links: [`src/agents/hello.py`](src/agents/hello.py), [`docs/hello-agent-loop.md`](docs/hello-agent-loop.md), [`docs/architecture.md`](docs/architecture.md), [`docs/cost-guardrails.md`](docs/cost-guardrails.md), [`infra/terraform/budget/`](infra/terraform/budget/). The first refusal probe showed a useful boundary miss: the agent avoided an irrelevant tool call, but still answered a non-AWS question it should have redirected or refused.

> **Week 2 closed — 2026-07-09.** Built the first real Strands specimen: a current-weather tool with typed failure envelopes, a local weather agent runner, offline tests for every failure kind, and a second temperature-conversion `@tool` that proved `Literal[...]` constraints can surface as model-visible schema enums. Links: [`src/agents/weather.py`](src/agents/weather.py), [`src/tools/weather.py`](src/tools/weather.py), [`src/tools/temperature.py`](src/tools/temperature.py), [`tests/test_weather_tool.py`](tests/test_weather_tool.py), [`tests/test_temperature_tool.py`](tests/test_temperature_tool.py), [`docs/reports/week-02-conversations.md`](docs/reports/week-02-conversations.md). The honest boundary finding: docstrings and schemas shape tool use, but they do not enforce product policy; the model still needs deterministic checks, guardrails, and later eval gates.

> **Week 3 closed — 2026-07-11.** Deployed the weather agent to AgentCore Runtime through the CLI-generated CodeZip/CDK path, verified tool-backed execution and scoped session separation, benchmarked five cold/warm managed sessions against comparable local calls, and used Runtime traces to show that model calls occupied roughly 96–99% of traced time while the weather tool took only 40–47 ms. CloudWatch and Cost Explorer measured $0.025821 in Runtime compute across 14 invocations and eight sessions. Links: [`weatheragent/`](weatheragent/), [`docs/local-vs-agentcore.md`](docs/local-vs-agentcore.md), [`docs/assets/week-03-latency-measurements.json`](docs/assets/week-03-latency-measurements.json), [`docs/trace-anatomy.md`](docs/trace-anatomy.md), [`docs/execution-role-baseline.md`](docs/execution-role-baseline.md). The honest boundary: the measured cold-path overhead did not isolate microVM startup, and the standalone screenshot, A→A→B receipt, and redeploy runbook were dropped rather than manufacturing extra proof. Final teardown left zero matching Runtimes, application stacks, generated execution roles, or Runtime log groups; shared CDK bootstrap infrastructure remains intentionally.

> **Week 4 closed — 2026-07-12.** Built an explicitly registered three-tool portfolio, verified calculator/weather/Web Search controls and one exact-state multi-tool chain, retained two genuine ambiguity failures, audited an external MCP server's prompt-bearing descriptions, and deployed the same typed weather contract behind a Lambda-backed AgentCore Gateway target. The no-model seam comparison measured 83.9 ms direct versus 217.5 ms Gateway median latency; Gateway preserved the description and typed invalid-city envelope but omitted the direct schema's model-visible `units` default. Links: [`src/agents/weather.py`](src/agents/weather.py), [`docs/reports/week-04-live-three-tool-runs.md`](docs/reports/week-04-live-three-tool-runs.md), [`docs/reports/week-04-ambiguity-battery.md`](docs/reports/week-04-ambiguity-battery.md), [`docs/reports/week-04-external-mcp-trust-audit.md`](docs/reports/week-04-external-mcp-trust-audit.md), [`docs/reports/week-04-weather-seam-comparison.md`](docs/reports/week-04-weather-seam-comparison.md), [`docs/decisions/0001-explicit-tool-registration.md`](docs/decisions/0001-explicit-tool-registration.md). The honest boundaries: the managed Web Search description remained empty, two ambiguity rows failed, the latency sample was small, and Lambda credential injection remains transitional until later reliability/identity work.

## Following along / forking

1. Fork the repo, read [`LEARNING_PLAN.md`](LEARNING_PLAN.md) front matter (especially **Working assumptions**, **Managed evaluation boundaries**, and **Appendix C — Guardrails**) before Week 1.
2. Work one week at a time; each week's **Success criteria** are the exit gate — don't start Week N+1 with Week N's checkboxes open.
3. Keep the placeholder discipline: no account IDs, ARNs, real bucket names, raw traces, or secrets in commits. The safety scanner (Week 6) enforces this, but the habit starts Week 1.
4. Expect drift: AWS ships fast. When this repo's paraphrase and the [current docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) disagree, **the docs win** — and a PR fixing the paraphrase is welcome.

## Guardrails (the short version)

- Judges — mine and AWS's — are measurements, not truth; humans calibrate both.
- Deployment is evidence, not polish; the public claim is scoped regression discipline, never production-readiness or safety certification.
- Optimizer suggestions face holdout rows or they don't ship.
- Write-action tools stay stubbed until reliability gates exist.
- Adversarial test rows use inert canaries; this repo is not an attack cookbook.
- Raw traces and payloads stay out of git; public artifacts carry provenance, not data.

The full version, with rationale, is [Appendix C of the learning plan](LEARNING_PLAN.md).

---

*Built in public as a learning journey. Corrections and issues welcome — especially of the "the docs changed, your Week N command is stale" variety.*
