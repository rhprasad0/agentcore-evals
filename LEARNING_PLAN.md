# AgentCore & Strands: 16-Week Eval-First Agent Development Plan

This is a learning-by-doing path for building **tool-calling agents whose behavior is measured before it is trusted**, using the Strands Agents SDK and Amazon Bedrock AgentCore. It is the direct sequel to the [12-week AWS AI Evals plan](https://github.com/rhprasad0/aws-ai-evals): that project built an evaluation harness around a deliberately boring chatbot and explicitly deferred agent/tool-use evaluation to a future plan. This is that plan.

The goal is not to demo an agent that looks smart in a happy-path video. The goal is a small but serious reference architecture where **tool selection accuracy, tool parameter fidelity, execution reliability, and failure behavior are contracts** — with schemas, synthetic datasets, human labels, calibrated judges, managed evaluation lanes, CI regression gates, and public-safe receipts to prove it.

The eval-first order of operations, carried over from the previous plan:

1. Define what "correct tool use" means before building more tools.
2. Build schemas, datasets, validators, deterministic gates, and a human-label workflow around a minimal specimen.
3. Calibrate LLM judges (your own **and** AWS's managed ones) against human labels before trusting either.
4. Only then scale up: more tools, dependency chains, real external APIs, multi-agent patterns.
5. Deployment and optimization are evidence-producing steps, not victory laps.

## Why this stack, and what changed in 2025–2026

Amazon Bedrock AgentCore went GA in October 2025 as a set of composable services for running agents built with any framework: **Runtime** (serverless, session-isolated microVM hosting), **Gateway** (turns APIs, Lambda functions, and MCP servers into governed MCP tools), **Memory** (short/long-term), **Identity** (OAuth inbound/outbound, token vault), **Policy** (deterministic control over agent–tool interactions), **Built-in tools** (Code Interpreter, Browser, Web Search), and **Observability** (OpenTelemetry traces into CloudWatch).

Since then the parts that matter most to this plan shipped:

- **AgentCore Evaluations (GA March 2026)** — managed LLM-as-judge evaluation over agent traces, with built-in evaluators at session, trace, and **tool level** — including `Builtin.ToolSelectionAccuracy` and `Builtin.ToolParameterAccuracy` — plus ground-truth modes, custom LLM/Lambda evaluators, and online (sampled live traffic), on-demand, and batch modes.
- **Agent performance loop (GA June 2026)** — recommendations, batch-evaluation validation, and A/B testing that propose and test prompt/tool-description changes from production traces.
- **AgentCore CLI (GA March 2026)** — `npm install -g @aws/agentcore`; scaffolds Strands/LangGraph/ADK/OpenAI-Agents projects, local dev with a browser Agent Inspector, CDK-backed deploys.
- **Strands Agents 1.x + Strands Evals** — the agent SDK and its separately versioned evaluation SDK. The custom lane uses Evals for `Case`/`Experiment` orchestration, task-result caching, custom evaluator execution, and reporting; the repo's schemas and canonical traces remain the evaluation contracts. Pin and record the exact Evals version when Week 8 begins (PyPI snapshot verified 2026-07-13: `1.0.1`).
- **Protocols** — MCP spec revision 2025-11-25; A2A protocol v1.0 under the Linux Foundation.

That maturity is exactly why the eval-first posture matters: the managed services will happily score your agent for you. This plan builds the ground truth that tells you whether to believe them.

## North Star

By the end of 16 weeks, there is a deployed **tool-calling agent reference architecture** that can:

- run a Strands agent portfolio locally and on AgentCore Runtime with identical behavior contracts;
- expose every tool through an explicit, schema-validated contract — no magic tool discovery;
- replay a versioned synthetic dataset of tool-calling scenarios through a local harness with deterministic gates for tool selection, argument fidelity, sequencing, and failure handling;
- maintain a human-labeled fixture (64+ rows) for tool-selection and execution quality, with a blind labeling workflow;
- run two calibrated judge lanes — a self-built blind judge and managed AgentCore Evaluations built-ins — with published agreement metrics against human labels;
- gate GitHub PRs and deploys on regression fixtures, with at least one preserved red-gate receipt of a caught tool-selection regression;
- emit normalized OpenTelemetry traces to CloudWatch with online evaluation sampling and a public-safe dashboard;
- enforce safety boundaries outside agent code (AgentCore Policy, Gateway-level guardrails, scoped IAM, capability manifests);
- demonstrate multi-agent coordination (Graph, Swarm, A2A) with coordination accuracy measured, not asserted;
- publish metrics a recruiter or reviewer can inspect: tool selection accuracy, parameter accuracy, execution success rate, judge agreement, and regression-gate history.

What it is **not**: a universal agent benchmark, a safety certificate, proof of production readiness, an autonomy showcase, or a claim that high eval scores generalize beyond the scenarios tested. Passing evals are scoped evidence. The harness and the honesty are the product; the agent stays boring on purpose.

## Specimen strategy: a deliberately boring tool portfolio

Reusing the previous plan's core lesson — the specimen must stay simpler than the evaluation machinery around it:

| Phase | Weeks | Specimen | Why |
| --- | --- | --- | --- |
| Foundations | 1–4 | "Hello world" agent → weather agent → 3-tool agent (weather, calculator, web search) | Learn the SDK, runtime, and tool integration seams before formalizing anything. |
| Eval contract | 5–10 | **Single-tool specimen** (weather) with stubbed/mocked integrations | One tool keeps tool-selection labels unambiguous. The eval contract is the work. |
| Complexity under contract | 11–13 | 5-tool dependency-chain agent (search → fetch → summarize → convert → notify) with real external APIs | Every new tool arrives with dataset rows, gates, and regression fixtures. |
| Production & orchestration | 14–16 | Deployed multi-agent system with observability, safety boundaries, and a public demo | Deployment as evidence: live traces, online evals, red gates, documented metrics. |

Rules that keep the specimen honest:

- **Write-action tools stay stubbed until Week 12's reliability gates exist.** The "notify/email" tool sends to a sink, never a real inbox, until circuit breakers and failure comms are evaluated.
- **Every tool has a failure mode catalog before it has a second feature.**
- **Tool count is a cost, not a feature.** More tools = larger selection surface = more ways to be wrong. Additions must pay for themselves through the harness.

## Working assumptions

Placeholders and synthetic data throughout — this is a public repo:

- AWS account: `<AWS_ACCOUNT_ID>`; Region: `us-east-1` (verify AgentCore feature availability there before each managed lane — availability is not uniform, and available is not enabled).
- Example bucket: `s3://example-agent-evals/...`; example domains: `example.com`, `api.example-weather.test`.
- Python 3.10+ for agent code (Runtime supports direct code deploy up to Python 3.14); Node.js 20+ for the AgentCore CLI; `uv` or `venv` for Python env management.
- Model access granted in the Bedrock console for the default Strands model (Claude on Bedrock) and the judge models before anything runs.
- Never commit: account IDs, ARNs, real bucket names, raw CloudWatch output, raw traces, session IDs, API keys, emails, or model responses containing any of the above. A `public_safety_scan` script (Week 6) enforces this in CI.

**Cost guardrails.** Everything managed here is consumption-billed: Runtime charges per-second CPU/memory per session; Evaluations bills judge-model tokens per scored span; online evaluation multiplies that by traffic × sampling rate; Gateway bills per call and tool-indexing; Memory bills per event/retrieval. Habits: AWS Budgets alarm at a low threshold from Week 1; `agentcore remove all` + `agentcore deploy` teardown after each deployed-lane session; online evaluation sampling starts at the minimum useful rate (verify the sampling-rate semantics in your account — the API expresses it as a percentage); batch evals run on pinned small datasets, not "everything, always."

**Synthetic is not the same as safe.** Failure-injection and prompt-injection rows use inert canaries (`INJECTION_CANARY_DO_NOT_FOLLOW`), never working attack payloads. An eval repo must not double as an attack cookbook.

## Source ledger

This plan paraphrases AWS and Strands APIs, CLI flags, evaluator names, and schemas so you can build against them — but paraphrases drift. **When this document and the docs disagree, the docs win.** Confirm before wiring anything up:

| Source | URL |
| --- | --- |
| AgentCore Developer Guide | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html> |
| AgentCore release notes (subscribe) | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html> |
| AgentCore CLI quickstart | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-cli.html> |
| AgentCore Evaluations | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html> |
| Built-in evaluator prompt templates | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/prompt-templates-builtin.html> |
| Batch evaluations | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-getting-started.html> |
| Online evaluations | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-online-evaluations.html> |
| Gateway | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html> |
| Memory | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html> |
| Identity | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html> |
| Policy | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html> |
| Observability | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html> |
| Managed harness (contrast lane) | <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html> |
| Strands Agents docs | <https://strandsagents.com/docs/user-guide/quickstart/python/> |
| Strands Evals SDK | <https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/> |
| Strands multi-agent & A2A | <https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/> |
| Strands GitHub (monorepo) | <https://github.com/strands-agents/harness-sdk> · <https://github.com/strands-agents/evals> |
| AgentCore samples | <https://github.com/awslabs/amazon-bedrock-agentcore-samples> |
| MCP specification (2025-11-25) | <https://modelcontextprotocol.io/specification/latest> |
| A2A protocol v1.0 | <https://a2a-protocol.org/latest/> |

## Architecture lanes

Five lanes that converge in the Week 16 capstone. Keep their datasets, schemas, and result shapes separate; scores do not transfer between lanes.

1. **Agent build lane** — Strands agents and tools; AgentCore Runtime, Gateway, Memory, Identity for hosting and integration. Weeks 1–5, 11–12, 15.
2. **Custom eval lane** — the part you own: tool-contract schemas, synthetic datasets, deterministic validators and gates, execution-trace capture, human labeling, self-built blind judge. Engine: `strands-agents-evals` for execution/reporting plus repo-owned schemas, adapters, and validators for evidence contracts. Weeks 5–10.
3. **Managed eval lane** — AgentCore Evaluations: built-in evaluators (session/trace/tool level), custom evaluators, on-demand and batch runs, online sampling. Used only after the custom lane can check its homework. Weeks 10, 13–14, 16.
4. **Platform & CI lane** — GitHub Actions, IaC (CDK via the AgentCore CLI, or Terraform where you need it), S3 artifact/versioning discipline, CloudWatch dashboards. Weeks 3, 13–14, 16.
5. **Safety & governance lane** — capability manifests, scoped IAM, AgentCore Policy, Gateway-level guardrails, Identity-scoped credentials, public-safety scanning. Weeks 5, 12, 15–16.

### Custom-lane ownership boundary

Strands Evals is the execution framework, not a second source of truth. The integration stays explicit:

| Layer | Owner | Stable artifact | Strands Evals role |
| --- | --- | --- | --- |
| Correctness definition | This repo | Week 5 contracts/taxonomy + Week 6 dataset schemas | Receives mapped `Case` objects; does not define truth. |
| Source telemetry | Strands SDK / ADOT | Pinned source profile | Captures or maps source spans. |
| Canonical trace | This repo | `execution-trace.schema.json` | Custom evaluators consume the canonical projection through an adapter. |
| Mechanical evaluation | Repo evaluators on Strands Evals | `EvaluationOutput` verdicts with evidence | Orchestrates cases × evaluators and reports. |
| Human ground truth | This repo | `human-labels-64.jsonl` | No authority; later comparisons only. |
| Judged evaluation | Own judge / managed AgentCore lane | Versioned judge outputs | `TrajectoryEvaluator` is used only where explicitly calibrated. |
| CI | This repo + Strands Evals CLI | Experiment/report JSON + committed safe fixtures | Validates serialized experiments, runs offline tasks, applies exit policy, renders reports. |

`strands-evals validate` proves a serialized Strands experiment can be loaded; it does not replace `scripts/validate_dataset.py`, contract validation, or the public-safety scan. Likewise, a Strands `Session` is a framework representation, not the repo's canonical trace schema.

## Managed evaluation boundaries (read before Week 8)

The 12-week plan's hardest-won lessons, restated for AgentCore Evaluations:

- **Managed evaluators are versioned LLM judges you do not control.** Built-in evaluator models and prompt templates are fixed and can change underneath you. Record evaluator IDs and dates in every run manifest; re-baseline when AWS updates them.
- **A judge score is a measurement, not truth.** `Builtin.ToolSelectionAccuracy` asks a judge model whether an action was "justified" — a defensible rubric, but still a model's opinion. Weeks 9–10 exist to measure how often that opinion matches humans *for this agent*.
- **Ground truth modes are assertions you wrote, not oracles.** Goal-success-with-ground-truth judges against your success assertions; garbage assertions produce confident garbage verdicts.
- **Online evaluation is a metered faucet.** Sampled live traces flow to judge models and bill accordingly. Start at the minimum sampling rate that produces signal; confirm rate semantics in the current docs.
- **Trace compatibility is an adapter contract, not a naming wish.** Evaluations reconstructs sessions from framework-specific OTEL spans and, where applicable, correlated event records. Week 6 keeps raw Strands telemetry, the repo's canonical trace, and managed input as separate shapes joined by a versioned, tested mapping. Field alignment reduces translation; it does not prove transport, event-record packaging, or service acceptance. Week 10 supplies the first live acceptance receipt.
- **Availability, quotas, and model access vary by Region.** Confirm evaluator availability in `us-east-1`, and remember evaluation configs have account limits and token-per-minute throughput caps.

## Repository shape to build toward

```text
agentcore-evals/
  README.md
  LEARNING_PLAN.md
  docs/
    weeks/                     # the 16 weekly guides (week-NN-*.md + index)
    architecture.md            # annotated AgentCore component diagram (W1)
    local-vs-agentcore.md      # deployment comparison (W3)
    tool-contract-spec.md      # contract rationale (W5)
    judge-calibration.md       # three-way agreement report (W10)
    reports/                   # public-safe weekly receipts
    assets/                    # screenshots: console, red gates, dashboards
  schemas/
    tool-contract.schema.json
    capability-manifest.schema.json
    tool-calling-example.schema.json
    execution-trace.schema.json
    human-label.schema.json
    judge-output.schema.json
  datasets/
    synthetic/
      tool-calling-100.jsonl   # W6 dataset
      chain-scenarios.jsonl    # W11 dataset
    fixtures/
      human-labels-64.jsonl    # W9 reviewed fixture
      regression/              # W13 committed CI fixtures
  src/
    agents/                    # Strands agent definitions
    tools/                     # @tool implementations + mocks
    contracts/                 # manifest loading + validation
    adapters/                  # trace normalization, managed-eval export
    judges/                    # blind judge prompt + runner (W10)
  evals/
    cases/                     # strands-evals Case definitions
    adapters/                  # canonical repo artifacts → Strands Evals types
    experiments/               # versioned serialized Experiment definitions
    evaluators/                # deterministic gates + custom evaluators
    harness.py                 # W8 local harness entrypoint
  scripts/
    validate_dataset.py
    public_safety_scan.py
    label_workbench.py         # W9 browser labeling UI
    summarize_run.py
  infra/                       # anything outside CLI-managed CDK
  .github/workflows/
    ci.yml                     # W13 regression gates
```

Weeks 1–4 start documentation-first and grow this tree; nothing lands in `main` without its schema, validator, or fixture.

---

# The 16 Weeks

Each week follows the same template: **Objective · Why it matters · Build steps · Deliverable checklist · Success criteria · Docs to consult.** Deliverables are designed to be demo-ready (shows in an interview), linkable (LinkedIn/portfolio), code-complete (runs from a fresh clone), and metrics-proven (numbers, not adjectives).

The full week-by-week detail — expanded concepts, guided-discovery exercises, gotchas and drift-watch lists, and doc-verified reading lists — lives in [`docs/weeks/`](docs/weeks/README.md), one guide per week. The summaries below are the map; the guides are the territory. Each week's **success criteria** (in its guide) are the exit gate: don't start Week N+1 with Week N's checkboxes open.

## Week 1 — AgentCore & Strands Fundamentals

Understand the AgentCore service map (Runtime, Gateway, Memory, Identity, Policy, Evaluations, Observability, built-in tools), Strands SDK basics, MCP, and A2A; stand up the local dev environment and run a hello-world agent whose first answer already goes through the tool loop. **Deliverable:** Local Dev Environment + Architecture Notes. → [Full guide](docs/weeks/week-01-fundamentals.md)

## Week 2 — Basic Agent Development with Strands

Build the first real Strands agent — the weather specimen — with a typed failure envelope that makes its behavior *labelable* later; exercise the agent loop deliberately (call / refuse / fail cleanly) and compare model providers as a controlled variable. **Deliverable:** First Functional Agent + Tool. → [Full guide](docs/weeks/week-02-first-agent.md)

## Week 3 — AgentCore Runtime & Deployment

Deploy the weather agent to AgentCore Runtime via the CLI; understand per-session microVM isolation and the credential flip to execution roles; write a measured (not vibes) local-vs-managed comparison and prove teardown/re-deploy reproducibility. **Deliverable:** AgentCore Deployment Proof. → [Full guide](docs/weeks/week-03-runtime-deployment.md)

**Closeout (2026-07-11):** Runtime deployment, managed invocation, session-isolation probing, latency/cost measurement, trace anatomy, execution-role inspection, and final teardown were completed. A standalone screenshot, A→A→B transcript, and teardown/re-deploy runbook were intentionally omitted when this specimen was closed rather than redeployed.

## Week 4 — Tool Integration Patterns

Integrate tools three ways — direct `@tool`, external MCP servers, and AgentCore Gateway (Lambda target + built-in Web Search connector) — and commit in writing to explicit tool registration over semantic discovery. **Deliverable:** Multi-Tool Agent Portfolio. → [Full guide](docs/weeks/week-04-tool-integration.md)

**Closeout (2026-07-12):** The explicit three-tool portfolio, controlled live runs, five-row ambiguity battery, external MCP description audit, discovery ADR, and same-capability direct-versus-Lambda/Gateway comparison were completed. Gateway preserved the weather description and typed domain-failure envelope but omitted the direct schema's model-visible default; the measured three-sample median added 133.6 ms through the governed seam. Two ambiguity failures and the managed Web Search description gap remain intentionally visible as Week 5–6 contract and dataset inputs.

## Week 5 — Agent/Tool Contract Architecture

Freeze the informal patterns into contracts: tool-contract and capability-manifest schemas with valid/invalid fixtures, exact-version joins, scoped manifest enforcement over direct and discovered registration paths, a two-layer isolation proof (microVM + bounded IAM receipts), and a failure taxonomy with baseline degradation behavior plus explicit retry qualifiers. **Deliverable:** Tool Contract Specification. → [Full guide](docs/weeks/week-05-tool-contracts.md)

**Progress checkpoint (2026-07-14):** The schemas, exact-version contract instances, manifest loader/enforcement, final model-visible conformance checks, constructor inventory, failure taxonomy, and normative [`tool-contract-spec`](docs/tool-contract-spec.md) are implemented and tested. The deployed lane is also complete: a disposable scratch Runtime preserved the selected model/tool/telemetry path, produced bounded denials for an adjacent model, configuration-bundle mutation, and CloudWatch log reads under the actual Runtime role, and repeated the same-session/different-session isolation canary. Public evidence lives in the [Runtime IAM and isolation report](docs/reports/week-05-runtime-iam-isolation.md) and [synthetic receipt](docs/assets/week-05-runtime-iam-isolation.json); private Runtime state and the operational scratch role were torn down. Remaining exit gates are the managed Gateway green → red → restored-green schema-drift exercise, one canonical contract-validation command wired into CI or pre-commit, and the exact-version dataset/run-identity boundary.

## Week 6 — Tool Execution Dataset & Validation Schema

Build the eval corpus: 100 hand-reviewed tool-calling rows (straightforward, multi-call, no-tool, failure-injection, adversarial, and five bounded dependency/stop cases), a canonical execution-trace schema with synthetic Strands inline/ADOT-split compatibility fixtures, deterministic versioned mocks, and validators in CI. **Deliverable:** Synthetic Dataset + Validators. → [Full guide](docs/weeks/week-06-dataset-validation.md)

## Week 7 — Minimal Tool-Calling Specimen

Reduce to a single-tool specimen with every behavioral input pinned in a run manifest; capture the declared Strands telemetry profile, normalize it through a tested adapter, record observed pre-tool assistant text or explicit null without inferring causal reasoning, run the full dataset, and close the dataset-errata window before humans label. **Deliverable:** Instrumented Agent Specimen. → [Full guide](docs/weeks/week-07-specimen.md)

## Week 8 — Local Tool Execution Harness

Make Week 8 the explicit `strands-agents-evals` integration: map versioned dataset rows to `Case` objects, run repo-owned deterministic `Evaluator` gates through an `Experiment`, separate metered task generation from cached/offline re-evaluation, validate and report through the SDK/CLI, wire the offline fixture lane into PR CI, and run a sensitivity check proving the instrument measures the agent. **Deliverable:** Local Evaluation Harness. → [Full guide](docs/weeks/week-08-local-harness.md)

## Week 9 — Human Tool-Selection Labeling

Label 64 deliberately selected traces blind, in two passes, against a schema that distinguishes defensible alternatives and fabricated parameters; measure test–retest reliability (κ with a second labeler if possible); reconcile, export the fixture, and file findings from label-vs-gate disagreements. **Deliverable:** Human Labeling Workflow. → [Full guide](docs/weeks/week-09-human-labeling.md)

## Week 10 — Tool Selection Judge Calibration

Build a blind selection judge and a full-trace execution judge (structured output, versioned prompts, measured flip rate); run AgentCore Evaluations built-ins over the same traces; publish the three-way human/own-judge/managed-judge agreement analysis with per-verdict costs and a written trust policy. **Deliverable:** Automated Judge System. → [Full guide](docs/weeks/week-10-judge-calibration.md)

## Week 11 — Multi-Tool Integration Complexity

Scale to a 5-tool dependency chain under contract discipline: chain scenarios with state-handoff traps, DAG-membership sequencing gates, cascade rules (no silent mid-chain failures), a versioned and calibrated Strands `TrajectoryEvaluator` complement, and the regression check that portfolio growth didn't cost single-tool accuracy. **Deliverable:** Multi-Tool Chain Agent. → [Full guide](docs/weeks/week-11-multi-tool-chains.md)

## Week 12 — External Integration Reliability Gates

Swap mocks for real APIs behind the same contracts; build retries with backoff, circuit breakers, and honest degradation inside the tool boundary; gate on injected failure scenarios (zero fabricated data during outages); then un-stub the write action with an idempotency check. **Deliverable:** Production Integration Gates. → [Full guide](docs/weeks/week-12-reliability-gates.md)

## Week 13 — Production Agent CI Regression

Two-lane CI: deterministic regression fixtures with mocks on every PR, managed batch evaluation against the deployed agent on merge/nightly with calibration-derived thresholds — and a deliberately seeded regression caught by the pipeline, screenshotted, and written up. **Deliverable:** CI/CD Regression Pipeline. → [Full guide](docs/weeks/week-13-ci-regression.md)

## Week 14 — Agent Execution Trace Instrumentation

Production observability: scrubbed-at-the-emitter spans to CloudWatch with a committed billboard-test receipt, an online evaluation config sampling live traffic at a justified minimum rate, and a dashboard + alarms that answer "did tool selection get worse this week?" in one glance. **Deliverable:** Observability Dashboard. → [Full guide](docs/weeks/week-14-observability.md)

## Week 15 — Advanced Agent Patterns & Safety

Refactor the chain into Graph, Swarm, and workflow orchestration plus A2A, with coordination evals (handoff fidelity, loop budgets, delegation accuracy); enforce safety outside agent code with AgentCore Policy (Cedar at the Gateway) and Gateway-level guardrails, probed by inert adversarial rows with denial receipts. **Deliverable:** Multi-Agent Orchestration. → [Full guide](docs/weeks/week-15-multi-agent-safety.md)

## Week 16 — Production Agent Architecture Reference

Close the loop: the reference architecture drawn from deployed reality (demo-grade vs production-grade, annotated honestly), the managed performance loop run as a gated experiment under holdout discipline (adopt/reject published with numbers either way), a scoped public demo with a receipts-backed metrics page, and the case study. **Deliverable:** Production Reference Architecture. → [Full guide](docs/weeks/week-16-capstone.md)

---

# Appendix A — Week × Capability Map

Which weeks exercise which parts of the stack (● = primary focus, ○ = touched):

| Week | Runtime | Gateway | Memory | Identity | Policy | Evaluations (managed) | Observability | MCP | A2A | Strands Evals (custom) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | — |
| 2 | — | — | — | — | — | — | — | — | — | — |
| 3 | ● | — | — | ○ | — | — | ○ | — | — | — |
| 4 | ○ | ● | — | ○ | — | — | — | ● | — | — |
| 5 | ○ | — | — | ○ | ○ | — | — | — | — | — |
| 6 | — | — | — | — | — | ○ | ○ | — | — | ○ |
| 7 | — | — | — | — | — | — | ○ | — | — | ○ |
| 8 | — | — | — | — | — | — | — | — | — | ● |
| 9 | — | — | — | — | — | — | — | — | — | ○ |
| 10 | — | — | — | — | — | ● | ○ | — | — | ● |
| 11 | — | — | ○ | — | — | — | ○ | — | — | ● |
| 12 | ○ | ○ | — | ● | — | — | ○ | — | — | ● |
| 13 | ● | — | — | ○ | — | ● | ○ | — | — | ● |
| 14 | ● | — | — | — | — | ● | ● | — | — | ○ |
| 15 | ● | ● | ○ | ○ | ● | ○ | ● | ○ | ● | ● |
| 16 | ● | ● | ○ | ● | ● | ● | ● | ○ | ○ | ● |

Rows 2 and 5–9 are intentionally cloud-light: the eval contract is built locally, where iteration is free and deterministic. The managed lanes earn their place only after Week 10's calibration.

# Appendix B — Metrics Glossary

Defined once, used everywhere; every number in a report links back here.

- **Tool selection accuracy** — share of evaluated decisions where the agent called a tool from the row's expected set (or correctly called none). Deterministic gate; judged variant exists for ambiguous rows.
- **Tool parameter accuracy** — share of tool calls whose arguments satisfy the row's constraints and derive from context (no fabricated values). Deterministic where constrainable; judged for faithfulness.
- **Execution success rate** — share of tool calls returning `ok: true`, reported alongside (never blended with) selection accuracy: a correct selection that fails upstream is a different problem than a wrong selection.
- **Failure-behavior compliance** — share of failure-injection rows where the agent's response matched the taxonomy-required behavior for that failure kind.
- **No-tool compliance** — share of no-tool rows answered without any tool call.
- **Sequencing accuracy** — share of chain scenarios whose call order is within the row's valid-sequence DAG.
- **Judge agreement** — per-field percent agreement (and κ where a second rater exists) between a judge lane and the human fixture, with false-pass/false-fail rates reported separately. False passes are the dangerous ones.
- **Verdict flip rate** — share of judged rows whose verdict changes across repeat runs at fixed inputs; instability budget before a judge may scale.

# Appendix C — Guardrails

Carried forward from the 12-week plan, adapted for agents. These override enthusiasm:

- **Deployment is evidence, not polish.** The public claim is scoped regression discipline over known tool-use boundaries — never production readiness, autonomy, or safety certification.
- **Judges are measurements, not truth.** Human labels, deterministic gates, repeat runs, and variance analysis keep every judge honest — including AWS's built-ins. A judge no one has calibrated is a random-number generator with good vibes.
- **Managed scores are versioned dependencies.** Record evaluator IDs/dates in run manifests; re-baseline when AWS ships changes. When this repo's paraphrase and the current docs disagree, the docs win.
- **Optimizers face holdouts.** Any proposed improvement — managed recommendations, prompt tweaks, tool-description "clarifications" — is evaluated on rows it never saw, and rejected in writing if it doesn't clear baseline. The previous plan rejected its optimizer; that was a feature.
- **Tool count is a liability until evaluated.** No tool joins the portfolio without a contract, dataset rows, and gates. "More tools" is a bigger selection surface, not a better agent.
- **Write actions are gated twice.** Stubbed until reliability gates exist (Week 12); idempotency-checked forever after.
- **Synthetic is not safe.** Adversarial rows use inert canaries, never operational payloads. This repo must not double as an attack cookbook.
- **Raw traces stay out of git.** Public artifacts carry provenance (versions, hashes, kinds, scores), not payloads. The billboard test is a CI check, not a vibe.
- **Framework schemas are adapters, not truth.** Strands Evals cases, sessions, experiments, and reports are useful execution formats. Repo contracts, canonical traces, and human labels remain the stable evidence model; SDK upgrades cross a tested adapter boundary.
- **No magic production claims.** Passing evals are scoped evidence about tested scenarios. The honest sentence is always available: "measured X on Y under Z."
