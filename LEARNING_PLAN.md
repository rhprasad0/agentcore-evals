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
- **Strands Agents 1.x** — the SDK this plan builds on (Python `strands-agents`, ~1.45 as of July 2026), plus **Strands Evals** (`strands-agents-evals`): cases, experiments, LLM and deterministic evaluators (`ToolCalled`, `Equals`, `Contains`), trajectory evaluation, and trace-based evaluation.
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
2. **Custom eval lane** — the part you own: tool-contract schemas, synthetic datasets, deterministic validators and gates, execution-trace capture, human labeling, self-built blind judge. Engine: `strands-agents-evals` plus your own validators. Weeks 5–10.
3. **Managed eval lane** — AgentCore Evaluations: built-in evaluators (session/trace/tool level), custom evaluators, on-demand and batch runs, online sampling. Used only after the custom lane can check its homework. Weeks 10, 13–14, 16.
4. **Platform & CI lane** — GitHub Actions, IaC (CDK via the AgentCore CLI, or Terraform where you need it), S3 artifact/versioning discipline, CloudWatch dashboards. Weeks 3, 13–14, 16.
5. **Safety & governance lane** — capability manifests, scoped IAM, AgentCore Policy, Gateway-level guardrails, Identity-scoped credentials, public-safety scanning. Weeks 5, 12, 15–16.

## Managed evaluation boundaries (read before Week 8)

The 12-week plan's hardest-won lessons, restated for AgentCore Evaluations:

- **Managed evaluators are versioned LLM judges you do not control.** Built-in evaluator models and prompt templates are fixed and can change underneath you. Record evaluator IDs and dates in every run manifest; re-baseline when AWS updates them.
- **A judge score is a measurement, not truth.** `Builtin.ToolSelectionAccuracy` asks a judge model whether an action was "justified" — a defensible rubric, but still a model's opinion. Weeks 9–10 exist to measure how often that opinion matches humans *for this agent*.
- **Ground truth modes are assertions you wrote, not oracles.** Goal-success-with-ground-truth judges against your success assertions; garbage assertions produce confident garbage verdicts.
- **Online evaluation is a metered faucet.** Sampled live traces flow to judge models and bill accordingly. Start at the minimum sampling rate that produces signal; confirm rate semantics in the current docs.
- **Trace shape is the real integration contract.** Evaluations consumes OTEL/OpenInference-instrumented traces (Strands emits these natively). If your custom trace schema (Week 6) aligns field-for-field with those conventions, the managed lane ingests your world without adapters.
- **Availability, quotas, and model access vary by Region.** Confirm evaluator availability in `us-east-1`, and remember evaluation configs have account limits and token-per-minute throughput caps.

## Repository shape to build toward

```text
agentcore-evals/
  README.md
  LEARNING_PLAN.md
  docs/
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

## Week 1 — AgentCore & Strands Fundamentals

**Objective.** Understand the AgentCore architecture (Runtime, Gateway, Memory, Identity, Policy, Evaluations, Observability, built-in tools), Strands SDK basics, the MCP protocol, and A2A communication. Stand up a local development environment.

**Why it matters.** The previous plan evaluated a chatbot; agents add a new failure surface — the tool-call loop — and AgentCore is nine-plus services with overlapping names. A week spent drawing the map prevents fifteen weeks of confusing Runtime (hosting) with the managed harness (orchestration), or Policy (deterministic control) with Guardrails (content evaluation).

**Build steps.**

1. Install the toolchain and verify versions:

   ```bash
   python3 --version          # 3.10+
   node --version             # 20+
   npm install -g @aws/agentcore
   agentcore --version
   uv venv && source .venv/bin/activate
   uv pip install strands-agents strands-agents-tools
   aws configure              # or SSO; then grant Bedrock model access in the console
   ```

2. Write the hello-world agent — one custom tool calling one AWS service, so the first agent you ever run already goes through the tool loop:

   ```python
   # src/agents/hello.py
   import boto3
   from strands import Agent, tool

   @tool
   def caller_identity() -> dict:
       """Return the AWS account ID and ARN this environment is authenticated as."""
       ident = boto3.client("sts").get_caller_identity()
       return {"account": ident["Account"], "arn": ident["Arn"]}

   agent = Agent(
       system_prompt="You are a lab assistant. Answer AWS facts only via tools; never guess.",
       tools=[caller_identity],
   )
   agent("Which AWS identity am I running as?")
   ```

   Strands defaults to Claude on Bedrock — if this errors, fix model access now, not in Week 3.

3. Read the agent loop docs and annotate what actually happened: model reasoning → tool selection → execution → response synthesis. Capture the message list (`agent.messages`) and label each entry.
4. Write `docs/architecture.md` with a Mermaid diagram of the AgentCore components and one-sentence annotations *in your own words*, including the two 2026 additions most plans omit: Policy and Evaluations. Add a half-page primer each for MCP (spec rev 2025-11-25: tools/resources/prompts, stdio + streamable HTTP transports) and A2A (v1.0: Agent Cards, tasks, messages).
5. Optional dev-environment upgrade: register the AgentCore MCP server from `awslabs/mcp` with your coding assistant so it can inspect AgentCore resources during later weeks.

**Deliverable checklist — Local Dev Environment + Architecture Notes.**

- [ ] Repo initialized with the target tree, `README.md`, and this plan.
- [ ] `src/agents/hello.py` runs from a fresh clone with documented setup.
- [ ] `docs/architecture.md`: annotated component diagram + MCP/A2A primers.
- [ ] Annotated agent-loop trace (message list with your labels) committed as a doc.

**Success criteria.**

- [ ] You can explain, without notes, when a request touches Runtime vs Gateway vs Memory vs Policy.
- [ ] Hello-world agent answers via the tool (verified in the message list — not from model memory).
- [ ] Budget alarm active; teardown habits documented before anything is deployed.

**Docs to consult.** AgentCore "What is" + CLI quickstart; Strands Python quickstart; MCP spec overview; A2A v1.0 topics.

## Week 2 — Basic Agent Development with Strands

**Objective.** Build the first real Strands agent with a single tool, understand the agent loop deeply, run it locally, and explore model providers.

**Why it matters.** The weather agent becomes the specimen for the entire eval contract (Weeks 5–10). Building it with explicit error handling now — rather than retrofitting — is what makes its behavior *labelable* later. A tool that fails vaguely cannot be evaluated crisply.

**Build steps.**

1. Implement the weather tool against OpenWeatherMap (free tier), with a typed failure envelope instead of raw exceptions:

   ```python
   # src/tools/weather.py
   import os, requests
   from strands import tool

   FAILURE_KINDS = ("bad_input", "auth", "upstream_4xx", "upstream_5xx", "timeout", "network")

   @tool
   def get_current_weather(city: str, units: str = "metric") -> dict:
       """Get current weather for a city. units: 'metric' or 'imperial'.

       Returns {ok, city, temp, conditions} on success or
       {ok: False, error: {kind, message, retryable}} on failure.
       """
       if not city or not city.strip():
           return _fail("bad_input", "city must be non-empty", retryable=False)
       try:
           resp = requests.get(
               "https://api.openweathermap.org/data/2.5/weather",
               params={"q": city, "units": units, "appid": os.environ["OWM_API_KEY"]},
               timeout=5,
           )
       except requests.Timeout:
           return _fail("timeout", "upstream exceeded 5s", retryable=True)
       except requests.RequestException as exc:
           return _fail("network", str(exc), retryable=True)
       if resp.status_code >= 500:
           return _fail("upstream_5xx", f"status {resp.status_code}", retryable=True)
       if resp.status_code >= 400:
           return _fail("upstream_4xx", f"status {resp.status_code}", retryable=False)
       data = resp.json()
       return {"ok": True, "city": city, "temp": data["main"]["temp"],
               "conditions": data["weather"][0]["description"]}
   ```

   The failure envelope (`kind` ∈ a closed set, `retryable` explicit) is the seed of Week 5's failure taxonomy and Week 6's validators.

2. Exercise the agent loop deliberately: ask questions that should call the tool, questions that shouldn't (`"What's the capital of France?"`), and questions that should fail cleanly (`"Weather in ''?"`, key unset, network blocked). Log full conversations to `docs/reports/week-02-conversations.md` (scrubbed).
3. Swap model providers behind the same agent — Bedrock default vs one alternative (`strands.models` providers: Bedrock, Anthropic, OpenAI, etc.) — and note tool-calling behavior differences. Provider choice is a variable your evals will control for later.
4. Write a second custom `@tool` from scratch (any small utility) purely to internalize the decorator contract: docstring → tool description, signature → input schema. Tool descriptions are prompts; treat them as versioned artifacts from day one.

**Deliverable checklist — First Functional Agent + Tool.**

- [ ] Weather agent with typed failure envelope, graceful degradation messages, and unit-tested tool code (mock the HTTP layer).
- [ ] Conversation logs: success, refusal-to-call, and each failure kind, committed scrubbed.
- [ ] Custom `@tool` implementation with notes on how docstring/signature surface to the model.
- [ ] Provider-swap notes (Bedrock vs one other) on tool-calling differences.

**Success criteria.**

- [ ] Every `FAILURE_KINDS` value is reachable in a test and produces a distinct, user-appropriate agent response.
- [ ] The agent does *not* call the weather tool for non-weather questions (spot-checked now; gated in Week 8).
- [ ] Tool unit tests pass offline — no network, no API key.

**Docs to consult.** Strands tools + model-providers concepts; OpenWeatherMap API reference.

## Week 3 — AgentCore Runtime & Deployment

**Objective.** Deploy the Week 2 agent to AgentCore Runtime via the AgentCore CLI, understand serverless agent hosting and session isolation, and compare local vs managed execution honestly.

**Why it matters.** Runtime's promises — per-session microVM isolation, consumption billing, managed scaling — are exactly the claims your later evals run against a *deployed* agent must account for. Deploying the boring agent early surfaces the IAM, packaging, and observability seams while the blast radius is one tool.

**Build steps.**

1. Scaffold and run locally with the CLI (this wraps your existing agent code into a Runtime-shaped project):

   ```bash
   agentcore create --name weather-agent --framework Strands \
     --model-provider Bedrock --memory none --build CodeZip
   cd weather-agent
   agentcore dev        # local server + browser Agent Inspector: chat, token usage, tool calls, trace timeline
   ```

2. Deploy and invoke:

   ```bash
   agentcore deploy --plan   # preview the CDK changes first
   agentcore deploy          # CodeZip direct-code deploy; container build is the alternative
   agentcore status
   agentcore invoke --prompt "What's the weather in Seattle?"
   agentcore logs --since 30m
   agentcore traces list && agentcore traces get <trace-id>
   ```

3. Prove session isolation to yourself: two invocations with different session IDs, show state does not leak; then two calls in one session, show continuity. Document what a "session" is (microVM lifecycle, idle timeout).
4. Write `docs/local-vs-agentcore.md`: cold start, latency, credential model (local env vars vs execution role), failure modes, cost per invocation estimate, debuggability. Screenshot the agent and an execution trace in the AWS console for `docs/assets/`.
5. Tear down (`agentcore remove all` + `agentcore deploy`), then re-deploy from scratch to prove the repo is the source of truth.

**Deliverable checklist — AgentCore Deployment Proof.**

- [ ] Weather agent live on AgentCore Runtime, deployed via committed CLI/CDK config.
- [ ] `docs/local-vs-agentcore.md` comparison with measured (not vibes) latency numbers.
- [ ] Console screenshots: agent resource + execution trace with tool-call span visible.
- [ ] Session isolation demo transcript.
- [ ] Teardown/re-deploy runbook proving reproducibility.

**Success criteria.**

- [ ] `agentcore invoke` returns a tool-backed answer with the tool-call span visible in `agentcore traces`.
- [ ] Fresh-clone → deployed agent works following only your runbook.
- [ ] Account returns to zero deployed agent resources after teardown.

**Docs to consult.** AgentCore CLI quickstart; Runtime concepts (sessions, direct code deploy vs container); Observability view docs.

## Week 4 — Tool Integration Patterns

**Objective.** Integrate tools three different ways — direct `@tool`, MCP servers, and AgentCore Gateway — and understand when each seam is the right one.

**Why it matters.** Weeks 5–13 evaluate *tool selection among alternatives*, which requires genuinely different tools wired through realistic seams. Gateway also introduces the pattern the rest of AWS's agent story leans on: every tool behind one governed MCP endpoint.

**Build steps.**

1. Grow the portfolio to three tools with non-overlapping capability boundaries: `get_current_weather` (yours), `calculator` (from `strands-agents-tools`), and web search. For search, use the Gateway **built-in Web Search connector** (GA June 2026, exposed as an MCP tool on your gateway) — fall back to a direct external search API `@tool` if it's unavailable in your Region.
2. Consume an external MCP server from Strands (`MCPClient` with stdio or streamable-HTTP transport) — e.g., the AWS documentation MCP server — and list what tools it advertises. Note the trust question: an MCP tool description is a prompt injected into your agent.
3. Stand up a Gateway and put a Lambda tool behind it:

   ```bash
   agentcore add gateway --name eval-gateway
   agentcore add gateway-target --name weather-lambda \
     --type lambda-function-arn \
     --lambda-arn arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:weather-tool \
     --tool-schema-file schemas/weather-tool.json \
     --gateway eval-gateway
   agentcore deploy
   ```

   The tool schema file is the interesting artifact: Gateway transforms a plain Lambda into a described MCP tool. Diff the schema you wrote against what the agent sees.
4. Document the tool-discovery spectrum and pick a side: this repo uses **explicit registration** (a checked-in tool list per agent) even though Gateway offers semantic tool search. Write down why (evaluability beats convenience at this scale).

**Deliverable checklist — Multi-Tool Agent Portfolio.**

- [ ] Agent with three working tools and clear capability boundaries documented per tool.
- [ ] MCP client integration example with advertised-tool listing and trust notes.
- [ ] Gateway with Lambda target: schema file, creation commands, before/after transformation notes.
- [ ] `docs/` note on integration seams: when `@tool` vs MCP vs Gateway, and the explicit-registration decision.

**Success criteria.**

- [ ] One conversation exercises all three tools correctly with no misfires (transcript committed).
- [ ] The same weather capability is reachable via direct `@tool` *and* via Gateway — and you can articulate the operational difference.
- [ ] Ambiguous prompts ("what's 30% of the temperature in Oslo?") produce defensible tool sequences — noted as future eval rows.

**Docs to consult.** Strands MCP tools docs; Gateway target configuration (Lambda/OpenAPI/MCP-server types); Web Search tool docs.

## Week 5 — Agent/Tool Contract Architecture

**Objective.** Freeze the informal patterns of Weeks 2–4 into formal contracts: tool interface schemas, agent capability manifests, execution-context isolation, and an explicit failure taxonomy. No magic tool discovery.

**Why it matters.** This is the pivot week — the same move as the previous plan's "eval/product contract" week, now for tools. Everything downstream (dataset rows, validators, labels, judges, CI gates) keys off these contracts. A contract that only lives in code comments cannot fail a build.

**Build steps.**

1. Write `schemas/tool-contract.schema.json` — the shape every tool in this repo must satisfy:

   ```json
   {
     "toolId": "weather.get_current_weather",
     "version": "1.2.0",
     "description": "Current weather for a city. Not forecasts, not history.",
     "inputSchema": { "...": "JSON Schema for arguments" },
     "outputSchema": { "...": "success + failure envelope shapes" },
     "failureModes": ["bad_input", "auth", "upstream_4xx", "upstream_5xx", "timeout", "network"],
     "sideEffects": "none | read_external | write_external",
     "authScope": "owm:read",
     "latencyBudgetMs": 5000
   }
   ```

2. Write `schemas/capability-manifest.schema.json` and one manifest per agent: which toolIds it may call, side-effect ceiling (`write_external` requires Week 12 gates), and out-of-scope declarations ("this agent does not answer non-weather questions with tools"). Load and validate the manifest in agent construction — an agent literally cannot register a tool its manifest doesn't grant.
3. Demonstrate execution-context isolation at two layers: Runtime's per-session microVMs (re-run the Week 3 demo, now written up against the contract) and least-privilege IAM (the deployed agent's execution role can call the weather Lambda and nothing else — prove it with a denied call).
4. Formalize the failure taxonomy: for each failure kind, the *required agent behavior* (retry? degrade? tell the user what, exactly?) with code examples. This document becomes Week 6's validator spec and Week 12's retry-policy input.

**Deliverable checklist — Tool Contract Specification.**

- [ ] `tool-contract.schema.json` + `capability-manifest.schema.json` with valid and invalid fixtures.
- [ ] All three tools re-described as contract instances; manifest-enforced registration in agent code.
- [ ] `docs/tool-contract-spec.md`: rationale, isolation demo (microVM + IAM denial receipt), failure taxonomy with required behaviors.
- [ ] `scripts/validate_dataset.py` seed: schema validation wired into a pre-commit/CI check.

**Success criteria.**

- [ ] An agent constructed with an un-manifested tool fails loudly at startup (test proves it).
- [ ] Invalid contract fixtures fail validation; valid ones pass — in CI.
- [ ] Every failure kind maps to exactly one required behavior, written down.

**Docs to consult.** JSON Schema spec; Runtime session/isolation docs; IAM condition keys for AgentCore.

## Week 6 — Tool Execution Dataset & Validation Schema

**Objective.** Build the synthetic evaluation corpus: 100 tool-calling scenarios, an execution-trace schema aligned with OTEL conventions, tool-selection fixtures, success/failure validators, and deterministic mock tools.

**Why it matters.** This is the eval contract made concrete. The dataset defines what "correct tool use" means row by row; the mocks make runs reproducible; the OTEL alignment is the quiet investment that lets Week 14's managed observability and the AgentCore Evaluations lane consume the same shapes without adapters.

**Build steps.**

1. Design `schemas/tool-calling-example.schema.json`, then generate `datasets/synthetic/tool-calling-100.jsonl`. Every row:

   ```json
   {
     "exampleId": "tc-0042",
     "prompt": "Is it warmer in Oslo or Bergen right now?",
     "expected": {
       "toolIds": ["weather.get_current_weather"],
       "minCalls": 2, "maxCalls": 2,
       "argConstraints": [{"path": "$.city", "inSet": ["Oslo", "Bergen"]}],
       "mustNotCall": ["search.web_search"],
       "responseMust": ["compare", "name both cities"]
     },
     "failureInjection": null,
     "tags": ["multi-call", "comparison"]
   }
   ```

   Distribution to hit: ~40 straightforward single-tool rows, ~15 multi-call rows, ~15 **no-tool rows** (the model should answer directly or decline — "more tool calls" is not "better agent"), ~15 failure-injection rows (mock returns each failure kind; expected behavior comes from the Week 5 taxonomy), ~10 adversarial/ambiguous rows including inert injection canaries and forced-choice traps. Generate drafts with an LLM, then hand-review every row — you are the dataset's editor, not its typist.
2. Design `schemas/execution-trace.schema.json` for normalized runs: session/trace/span ids, per-span `tool.name`, `tool.arguments`, `tool.result.ok`, `tool.result.kind`, latency, token counts, and the model's stated reasoning for tool choice where available. Name fields to match OTEL GenAI / OpenInference semantic conventions wherever one exists.
3. Build deterministic mocks: a mock registry that returns fixture responses per (toolId, args-hash), including scripted failures for injection rows. Mocked tools satisfy the same tool contracts — the agent cannot tell.
4. Extend `scripts/validate_dataset.py`: schema-validate every row, check tag/kind coverage against the taxonomy, verify canaries are inert, and fail on real-looking secrets (fold in `public_safety_scan.py`).

**Deliverable checklist — Synthetic Dataset + Validators.**

- [ ] 100-row reviewed dataset with the distribution above; generation prompts committed too.
- [ ] Execution-trace schema with OTEL-convention field mapping table.
- [ ] Deterministic mock tool registry with scripted failure fixtures.
- [ ] Validators in CI: schema, coverage, canary-inertness, safety scan.

**Success criteria.**

- [ ] `validate_dataset.py` passes; deliberately corrupted rows fail with actionable messages.
- [ ] Two identical harness runs over mocks produce byte-identical trace files (determinism proven).
- [ ] A teammate (or you, blind, a week later) can predict expected behavior from any row without asking.

**Docs to consult.** OTEL GenAI semantic conventions; OpenInference spec; AgentCore Observability trace docs (for field-name alignment).

## Week 7 — Minimal Tool-Calling Specimen

**Objective.** Reduce to a single-tool agent specimen with full instrumentation: normalized execution traces, tool-selection reasoning capture, and stubbed externals with controlled responses.

**Why it matters.** Weeks 8–10 need an agent whose every run produces a complete, normalized, deterministic record. One tool means tool-*selection* questions reduce to "call it or not, with what args" — unambiguous for human labelers. Complexity returns in Week 11, under contract.

**Build steps.**

1. Configure the specimen: weather agent, weather tool only (mock registry from Week 6 behind it), pinned model ID, pinned system prompt, temperature pinned low. Record all pins in a run manifest (`runId`, model, prompt hash, dataset version, mock fixture version, date).
2. Instrument with Strands hooks/callbacks + OTEL export to capture every loop step; write the adapter (`src/adapters/`) that normalizes raw traces into `execution-trace.schema.json` shape. Capture the model's tool-selection reasoning: the assistant message content preceding each tool call, stored as `selectionReasoning` on the span.
3. Run the full 100-row dataset through the specimen. Store normalized traces under `datasets/runs/<runId>/` (git-ignored raw, committed public-safe summaries).
4. Review 10 traces by hand end-to-end and annotate surprises — mislabeled expectations in the dataset get fixed *now*, with a changelog entry, before humans label against them.

**Deliverable checklist — Instrumented Agent Specimen.**

- [ ] Specimen config + run manifest schema; everything pinned and recorded.
- [ ] Trace normalization adapter with tests (raw fixture in → schema-valid trace out).
- [ ] Full-dataset run: 100 normalized traces + a public-safe summary report.
- [ ] Dataset errata changelog from the hand review.

**Success criteria.**

- [ ] 100/100 traces validate against the trace schema.
- [ ] Re-running with the same manifest reproduces identical tool-call sequences (mocked lane).
- [ ] Every trace answers, mechanically: which tool, what args, what result kind, what did the agent say, and *why did it choose the tool*.

**Docs to consult.** Strands observability/hooks docs; OTEL exporter configuration.

## Week 8 — Local Tool Execution Harness

**Objective.** An automated local harness that replays the dataset through the specimen and reports tool-selection accuracy, execution success rates, error-handling compliance, and timeout behavior — deterministically, in CI, without cloud calls.

**Why it matters.** This is the clipboard the rest of the plan writes on. Every later claim — "the judge agrees with humans", "the PR regressed tool selection", "the multi-tool agent sequences correctly" — is a harness report. Deterministic gates come first because they are cheap, explainable, and never hallucinate.

**Build steps.**

1. Build `evals/harness.py` on `strands-agents-evals` primitives, loading Cases from the Week 6 dataset:

   ```python
   from strands_evals import Case, Experiment
   from strands_evals.evaluators import ToolCalled, Contains
   from evals.evaluators.gates import ExpectedToolsGate, ArgConstraintGate, FailureBehaviorGate, NoToolGate

   cases = load_cases("datasets/synthetic/tool-calling-100.jsonl")
   evaluators = [ExpectedToolsGate(), ArgConstraintGate(), FailureBehaviorGate(), NoToolGate()]
   experiment = Experiment(cases=cases, evaluators=evaluators)
   report = await experiment.run_evaluations_async(run_specimen)   # replays via mock registry
   report.run_display()
   ```

   Custom deterministic gates (extending the SDK's `ToolCalled`/`Equals`/`Contains` family) implement the Week 6 `expected` block: right tools, right call counts, arg constraints satisfied, forbidden tools untouched, failure-injection rows produce the taxonomy-required behavior, no-tool rows stay tool-free.
2. Report per-tag and per-kind, not just overall: tool-selection accuracy on ambiguous rows is the number that matters; a blended average hides it. Emit text (console), JSON (machine), and Markdown (docs/reports) — same numbers, three renderings, via `scripts/summarize_run.py`.
3. Wire the harness into GitHub Actions on every PR (mocked lane only — fast, free, deterministic). Keep unlabeled-quality questions out of scope: the harness validates *mechanical* contract compliance; response *quality* waits for human labels (Week 9). Say so in the report footer.
4. Baseline: run three times, confirm identical results; then flip one system-prompt word and watch which gates move. That sensitivity check is your first evidence the harness measures the agent, not the harness.

**Deliverable checklist — Local Evaluation Harness.**

- [ ] `evals/harness.py` + custom gate evaluators with unit tests.
- [ ] Reports in text/JSON/Markdown with per-tag breakdowns; committed baseline report.
- [ ] CI workflow running dataset validation + harness on PRs.
- [ ] Sensitivity-check note (what moved when the prompt changed).

**Success criteria.**

- [ ] Harness runs the 100-row dataset locally in minutes, offline, deterministically.
- [ ] Baseline metrics recorded: overall + per-tag tool-selection accuracy, execution success rate, failure-behavior compliance, no-tool compliance.
- [ ] A deliberately broken tool description produces a visibly worse report (proven, screenshotted).

**Docs to consult.** Strands Evals deterministic evaluators + experiments docs.

## Week 9 — Human Tool-Selection Labeling

**Objective.** A browser-based labeling workflow and a reviewed 64-row human-labeled fixture covering tool-selection correctness, execution quality, and error-recovery behavior — labeled blind.

**Why it matters.** Human labels are the only ground truth this repo recognizes. Every judge — yours in Week 10, AWS's built-ins, the Week 16 optimization loop — gets measured against this fixture. Sixty-four careful rows beat six hundred careless ones; the previous plan's 48-row fixture caught real failures precisely because every row was actually reviewed.

**Build steps.**

1. Extend the previous plan's `label_workbench.py` pattern: a local browser UI that shows one trace at a time — prompt, tool calls with args, results, final response — and collects labels against `schemas/human-label.schema.json`:
   - `toolSelection`: correct / incorrect / defensible-alternative
   - `parameterQuality`: correct / wrong-value / fabricated
   - `executionQuality`: pass / fail (+ tags: ignored-tool-failure, hallucinated-tool-output, over-called, under-called)
   - `errorRecovery` (failure-injection rows only): compliant / non-compliant with the Week 5 taxonomy
   - free-text rationale, required on every fail
2. **Blind protocol:** the workbench hides the dataset's `expected` block and all harness verdicts. You label what the agent did, not whether it matched your own spec — divergences between labels and gates are findings, not annoyances.
3. Select 64 traces deliberately: every tag represented, all failure kinds covered, every harness-gate disagreement candidate included, plus a random fill. Label in two passes on different days; compute self-agreement (test–retest) per label field as your inter-rater proxy — and recruit a second labeler for a 16-row overlap subset if you can (report Cohen's κ).
4. Reconcile: where second-pass labels disagree with first-pass, adjudicate with written rationale. Export the reviewed fixture to `datasets/fixtures/human-labels-64.jsonl`. File dataset/harness bugs the labels exposed.

**Deliverable checklist — Human Labeling Workflow.**

- [ ] Browser labeling workbench (screenshot in docs) + label schema with fixtures.
- [ ] Reviewed 64-row blind-labeled fixture with rationales.
- [ ] Reliability metrics: test–retest agreement per field (and κ on the overlap subset if second labeler).
- [ ] Findings report: label-vs-gate disagreements and what they revealed.

**Success criteria.**

- [ ] 64/64 rows schema-valid with rationales on every fail label.
- [ ] Test–retest agreement ≥ 0.85 on `toolSelection` (if lower, the label definitions are the bug — fix and relabel).
- [ ] At least one genuine agent failure documented from labeling (if zero, the dataset is too easy — add harder rows and say so).

**Docs to consult.** Your own Week 5–6 schemas; previous repo's labeling workflow docs.

## Week 10 — Tool Selection Judge Calibration

**Objective.** Build a blind LLM judge that predicts tool-selection correctness and execution quality, calibrate it against the human fixture, and run the same traces through managed AgentCore Evaluations built-ins — a three-way agreement analysis: human vs your judge vs AWS's judge.

**Why it matters.** This is the flagship week. Anyone can call an LLM a judge; the portfolio-grade move is publishing agreement numbers, false-pass/false-fail analysis, and a decision about *which* judge to trust *for what* — including the managed one AWS would sell you. Judges only earn scaling rights (labeling rows 65–10,000) after they match humans on rows 1–64.

**Build steps.**

1. Build the blind judge (`src/judges/`): Claude on Bedrock via the Converse API, structured-output contract mirroring the built-in evaluators' shape (`{reasoning, score}` JSON). **Separation rule:** the tool-selection judge sees the conversation up to the tool call and the available-tools list — *never actual tool outputs* — so it evaluates the decision, not the outcome. A separate execution-quality judge sees the full trace. Version the judge prompts like code.
2. Run the judge over the 64 labeled traces ×3 repeats (measure verdict flip rate). Compute per-field: agreement, false-pass rate, false-fail rate, and where judge confidence diverges from human rationale. Analyze every disagreement by hand — some will be judge errors, some will be *your* label errors; both go in the report.
3. Managed lane: run AgentCore Evaluations **on-demand** over the same traces with `Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, and `Builtin.GoalSuccessRate` (`agentcore add evaluator` / the Evaluate API path — confirm current invocation shape in the docs; results land in a CloudWatch log group as JSON). Export scores via a small adapter into the same comparison frame.
4. Publish `docs/judge-calibration.md`: the three-way table, a confusion matrix per judge, cost-per-verdict for each lane, and a written policy — e.g., "own judge for PR-time selection checks (cheap, calibrated, blind); managed built-ins for production sampling (no infra); disagreements route to human review."

**Deliverable checklist — Automated Judge System.**

- [ ] Blind judge + execution judge with versioned prompts, structured output schema, repeat-run variance stats.
- [ ] Managed on-demand evaluation run over the same traces, with export adapter.
- [ ] `docs/judge-calibration.md`: three-way agreement, FP/FN analysis, per-verdict cost, trust policy.
- [ ] Disagreement casebook (every human-vs-judge conflict adjudicated in writing).

**Success criteria.**

- [ ] Your judge's agreement with humans on `toolSelection` beats a majority-class baseline by a margin you state — and you can name its failure modes.
- [ ] Verdict flip rate across repeats measured and reported (if >5%, temperature/prompt work before any scaling).
- [ ] The trust policy names concrete uses for each judge lane, including "not trusted for X yet."

**Docs to consult.** Built-in evaluator prompt templates (read the actual rubrics you're comparing against); on-demand evaluation docs; Bedrock Converse structured output.

## Week 11 — Multi-Tool Integration Complexity

**Objective.** Scale to a 5-tool agent with dependency chains (search → fetch → summarize → convert → notify), and extend the eval contract to sequencing, intermediate-state handling, and cascade-failure behavior.

**Why it matters.** Chains are where agents actually break: a defensible step-2 choice after a bad step-1 result, stale intermediate state, or a failure at step 4 that the user hears about as a cheerful success. Each new tool arrives *with* its contract, dataset rows, and gates — complexity under contract, not complexity then panic.

**Build steps.**

1. Add tools per the Week 5 contract discipline: `search.web_search`, `fetch.get_url` (allowlisted domains), `text.summarize` (a second, cheaper model behind a tool boundary — a deliberate agent-as-tool seam), `convert.units`, `notify.send` (**stub sink only** — `sideEffects: write_external` stays gated until Week 12). Update the capability manifest.
2. Author `datasets/synthetic/chain-scenarios.jsonl` (~40 rows): full-chain tasks, partial-chain tasks (agent should skip unneeded steps), mid-chain failure injections (fetch 403s, summarizer timeout), and state-handoff traps (does step 3 use step 2's actual output or a hallucinated version?). Extend the trace schema with `parentSpanId`/`stepIndex` if Week 6's shape didn't already cover it.
3. Extend harness gates: valid-sequence sets per scenario (DAG membership, not one golden path — "defensible alternative order" is a legal verdict), intermediate-state fidelity checks (grep step-N inputs for step-N−1 outputs), and cascade rules from the taxonomy (a failed step must surface, not vanish). Add `strands-evals`' trajectory evaluation as the LLM-judged complement to the deterministic sequence gates, using Week 10's calibration posture.
4. Visualize: generate a Mermaid execution-flow diagram *from trace data* per scenario (a `scripts/` renderer). Baseline the chain agent on the original 100-row dataset too — adding four tools must not regress single-tool selection accuracy; that number goes in the report.

**Deliverable checklist — Multi-Tool Chain Agent.**

- [ ] 5-tool agent with contracts, manifest, and stub-gated write action.
- [ ] Chain scenario dataset + sequencing/state/cascade gates with tests.
- [ ] Trace-derived execution flow visualizations (committed for 3+ interesting runs).
- [ ] Regression note: single-tool metrics before vs after the portfolio grew.

**Success criteria.**

- [ ] Sequencing accuracy ≥ target you set *before* running (state it in the report either way).
- [ ] Every mid-chain failure injection surfaces in the final response (zero silent cascade failures).
- [ ] Single-tool selection accuracy within noise of the Week 8 baseline — or the regression is investigated in writing.

**Docs to consult.** Strands multi-agent concepts (agents-as-tools); Strands Evals trajectory evaluators.

## Week 12 — External Integration Reliability Gates

**Objective.** Swap mocks for real external APIs and evaluate resilience: rate limits, timeouts, retries with backoff, circuit breakers, graceful degradation, and honest user communication during failures.

**Why it matters.** The difference between a demo agent and a production candidate is what happens during the bad five minutes. "Handles failures gracefully" becomes a measurable claim: inject real failure conditions, gate on the observed behavior, and only then un-stub the write action.

**Build steps.**

1. Wire real integrations behind the same contracts: OpenWeatherMap, a real search API, real HTTP fetch. Keys live in AgentCore Identity credential providers / Secrets Manager references when deployed — never env-var-committed.
2. Build the resilience layer *inside the tool boundary* (agents reason; tools defend): per-tool retry policy from the failure taxonomy (retryable kinds only, exponential backoff + jitter, budget-capped), a small circuit breaker (closed → open on N consecutive upstream failures → half-open probe), and degradation responses that tell the user what failed, what's stale, and what still worked.
3. Evaluate it: a failure-injection proxy (or fault-flag on the tool wrapper) drives scripted scenarios — burst 429s, hard timeouts, 30-minute outage simulation. New gates: retry compliance (counts/backoff observed in traces), breaker state transitions, degradation-message quality (judged lane, calibrated rubric), and **no fabricated data during outages** (deterministic: outage-window responses must not contain plausible-looking weather numbers).
4. Un-stub `notify.send` to a real sink you own (e.g., SNS → your email) only after the gates above pass; write actions get an additional idempotency check (same request twice → one send).
5. Record a short live demo: agent answering during an induced outage, degrading honestly, recovering when the breaker half-opens.

**Deliverable checklist — Production Integration Gates.**

- [ ] Real-API tools with Identity/Secrets-managed credentials and committed resilience configs.
- [ ] Circuit breaker + retry implementation with unit tests and trace-visible state.
- [ ] Failure-scenario eval suite with gates; report on all scenarios.
- [ ] Live outage demo recording/transcript + the un-stubbed, idempotent write action.

**Success criteria.**

- [ ] Zero fabricated tool data across all outage scenarios (gate, not aspiration).
- [ ] Retry/backoff behavior in traces matches the declared policy exactly.
- [ ] Degradation messages score ≥ your pre-stated rubric bar with the calibrated judge, spot-checked by you.

**Docs to consult.** AgentCore Identity credential providers; Secrets Manager references; your Week 5 taxonomy (it is the spec).

## Week 13 — Production Agent CI Regression

**Objective.** A deployed chain agent with a two-lane CI regression pipeline — fast deterministic fixtures on every PR, managed batch evaluation against the deployed agent on merge/nightly — and a preserved red-gate receipt of a caught tool-selection regression.

**Why it matters.** The previous plan's most persuasive artifact was a screenshot of CI failing for the right reason. Same move, bigger claim: changes to prompts, tool descriptions, or the portfolio cannot silently regress tool selection, because committed fixtures and score thresholds stand in the way.

**Build steps.**

1. Deploy the Week 12 agent via `agentcore deploy` (config in repo; observability enabled). Freeze `datasets/fixtures/regression/`: ~30 rows spanning single-tool, chain, no-tool, and failure-injection cases, each with pinned expected behavior — chosen from rows that have *already caught something*.
2. `ci.yml` lane 1 (every PR, minutes, free): dataset validation → safety scan → unit tests → harness over regression fixtures with mocks → thresholds (e.g., tool-selection gate pass rate = 100% on regression rows; they're regression rows *because* they must not flake).
3. Lane 2 (merge to main / nightly): invoke the *deployed* agent over the pinned prompt set, normalize fresh traces, then run **AgentCore batch evaluation** over them with the calibrated evaluator set (`Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, goal success) plus your own judge; fail the workflow if scores drop below the Week 10-informed thresholds. Post the score table as a job summary.
4. Prove the gate is alive: open a PR that plausibly-innocently breaks tool selection (e.g., "improve" the weather tool description to also claim forecasts), watch lane 1 or 2 go red, screenshot it, revert, and write the incident up in `docs/reports/`. A gate that has never fired is decoration.

**Deliverable checklist — CI/CD Regression Pipeline.**

- [ ] Deployed agent + committed regression fixtures with selection rationale.
- [ ] `ci.yml`: PR lane + deployed/batch-eval lane with thresholds and score-table summaries.
- [ ] **Red-gate receipt:** screenshot + written incident report of the caught regression.
- [ ] Runbook: what to do when each lane fails (including "the managed evaluator changed underneath us").

**Success criteria.**

- [ ] PR lane completes fast enough that you never skip it (< ~5 min).
- [ ] The seeded regression was caught by the pipeline, not by you eyeballing (receipt proves which gate fired).
- [ ] Batch-eval thresholds trace to Week 10 calibration, not round numbers pulled from air.

**Docs to consult.** Batch evaluations getting-started; GitHub Actions OIDC→AWS auth; `agentcore invoke` scripting.

## Week 14 — Agent Execution Trace Instrumentation

**Objective.** Production observability: normalized traces flowing to CloudWatch, an online evaluation config sampling live traffic, and a dashboard showing tool-selection patterns, timing, error rates, and satisfaction signals — with sensitive data kept out by design.

**Why it matters.** Weeks 6–13 built offline truth; production truth drifts. Online evaluation is the managed bridge — sampled live traces scored by the same evaluators you calibrated — and the previous plan's rule still binds: instrument provenance, never log payloads you wouldn't put on a billboard.

**Build steps.**

1. Enable AgentCore Observability end to end (one-click/CLI enablement; Strands emits OTEL natively — confirm exporter env/config against current docs). Verify your Week 6 field-name alignment paid off: spans in CloudWatch carry the shapes your adapters expect.
2. Scrub at the emitter: span attributes carry toolId, args-*shape* hashes, result kind, latencies, token counts, model/prompt/dataset versions — not raw user text, not raw tool payloads, not secrets. Prove it with a CloudWatch Logs Insights query committed to docs (the "billboard test" receipt).
3. Create the online evaluation config on the deployed agent:

   ```bash
   agentcore add online-eval --name prod_quality \
     --runtime weather-chain-agent \
     --evaluator "Builtin.ToolSelectionAccuracy" "Builtin.ToolParameterAccuracy" "Builtin.GoalSuccessRate" \
     --sampling-rate <MINIMUM_USEFUL_RATE> \
     --enable-on-create
   agentcore deploy
   ```

   Verify sampling-rate semantics and cost in the current docs before enabling; results land in a dedicated CloudWatch log group as JSON.
4. Build the CloudWatch dashboard: tool-call volume by toolId, selection-accuracy trend (online eval scores over time), p50/p95 tool latency, error rate by failure kind, breaker-state changes, session counts, and a satisfaction proxy you define honestly (e.g., no-retry follow-up rate — documented as a proxy, not "user satisfaction"). Alarm on selection-accuracy drop and error-rate spike.

**Deliverable checklist — Observability Dashboard.**

- [ ] End-to-end tracing: local dev and deployed agent both land normalized spans in CloudWatch.
- [ ] Billboard-test receipt: committed query + screenshot showing no sensitive payloads in logs.
- [ ] Online evaluation config live at a justified sampling rate, scores visible on the dashboard.
- [ ] Dashboard JSON in `infra/`, screenshot in docs, alarms wired to email/SNS.

**Success criteria.**

- [ ] A single trace is followable from `agentcore invoke` → CloudWatch span tree → online-eval score.
- [ ] Scrubbing verified by query, not by hope; one seeded "sensitive" test string provably absent downstream.
- [ ] Dashboard answers "did tool selection get worse this week?" in one glance.

**Docs to consult.** Observability configure/view docs; online evaluation creation; CloudWatch GenAI observability pages.

## Week 15 — Advanced Agent Patterns & Safety

**Objective.** Multi-agent orchestration (Graph, Swarm, and the workflow tool), A2A communication, and safety boundaries enforced outside agent code (AgentCore Policy + Gateway-level guardrails) — with coordination accuracy and boundary violations measured, not asserted.

**Why it matters.** Multi-agent systems multiply the failure surface: handoffs lose context, swarms loop, and "the other agent said so" becomes a provenance hole. The eval-first stance extends naturally — coordination is just tool selection at a higher altitude, and safety controls the agent can't reason its way around beat safety instructions in prompts.

**Build steps.**

1. Refactor the chain into explicit orchestration and compare patterns on the same scenarios: **Graph** (deterministic DAG via `GraphBuilder` — research → review chain), **Swarm** (dynamic handoffs between a researcher/summarizer/checker), and the **workflow tool** for the fixed pipeline. Note where the model *chooses* structure vs where you impose it — that choice is itself eval-relevant.

   ```python
   from strands.multiagent import GraphBuilder
   builder = GraphBuilder()
   builder.add_node(research_agent, "research")
   builder.add_node(review_agent, "review")
   builder.add_edge("research", "review")
   graph = builder.build()
   ```

2. A2A (v1.0): wrap one agent as an `A2AServer`, consume it from another via the A2A client tooling; inspect the Agent Card. Constraint to document: A2A agents work in Graph patterns but are **not currently supported in Swarm** — capability-check, don't assume. When deployed, note Runtime's A2A protocol contract and Gateway HTTP-passthrough as the managed fronting path.
3. Extend evals to coordination: handoff-fidelity gates (did agent B receive what agent A produced, unmutated?), loop detection (span-count budget per session), delegation-accuracy rows (should the orchestrator have delegated at all?), and cross-agent trace stitching in the dashboard.
4. Safety lane, outside the code: an **AgentCore Policy** allowing each agent exactly its manifest's tools under stated conditions (deny-by-default posture; the capability manifest from Week 5 becomes enforceable infrastructure), plus **Bedrock Guardrails at the Gateway layer** for prompt-injection/content screening on tool traffic. Then attack your own boundaries with the inert-canary adversarial rows: prompts that ask agents to exceed manifests, exfiltrate context, or chain into un-granted tools. Violations blocked at the policy/gateway layer — with the denial visible in traces — are the deliverable.

**Deliverable checklist — Multi-Agent Orchestration.**

- [ ] Graph, Swarm, and workflow implementations of the same task with comparison notes.
- [ ] A2A server/client demo: Agent Card, task lifecycle transcript, Graph-not-Swarm constraint documented.
- [ ] Coordination eval suite: handoff fidelity, loop budgets, delegation accuracy — with numbers.
- [ ] Policy + Gateway-guardrail configs in repo; adversarial-probe report showing denials with trace receipts.

**Success criteria.**

- [ ] Coordination accuracy reported per pattern on identical scenarios (and a recommendation of which pattern for which shape of task).
- [ ] Zero adversarial probes achieve un-manifested tool access; every block has a trace receipt.
- [ ] A handoff-corruption bug seeded deliberately is caught by the fidelity gate.

**Docs to consult.** Strands multi-agent (Graph/Swarm/workflow/A2A) docs; AgentCore Policy; Gateway guardrails integration; A2A v1.0 spec.

## Week 16 — Production Agent Architecture Reference

**Objective.** Close the loop: the complete deployed system with public demo, documented metrics, an eval-driven improvement pipeline — including the managed performance loop run under holdout discipline — and the LinkedIn-ready case study.

**Why it matters.** The capstone claim is deliberately narrow and therefore credible: *a tool-calling agent system whose selection accuracy, reliability, and safety boundaries are continuously measured, with receipts.* The previous plan ended by rejecting a managed optimizer that failed its holdout; this one ends by giving AgentCore's optimization loop the same fair trial.

**Build steps.**

1. Assemble the reference architecture and draw it as it *is* (from configs and traces, not aspiration): Strands agents on Runtime, tools via Gateway with Policy + guardrails, Identity-managed credentials, Memory where used, OTEL → CloudWatch with online evals, two-lane CI, and the custom eval stack around it all. One Mermaid diagram, one page of honest annotations, including what's demo-grade vs production-grade.
2. Run the **managed performance loop** as a gated experiment: enable Failure Insights / recommendations over accumulated production traces; take one proposed change (system prompt or tool description); evaluate it with batch evaluation *and* your harness on a **holdout split** (rows never used for tuning); adopt only if it beats baseline on holdout without regressing safety/no-tool rows. Publish the accept/reject decision with numbers either way — a documented rejection is as portfolio-worthy as an adoption.
3. Public demo: a thin, rate-limited, prompt-scoped web front end on the deployed agent (the Week 12 degradation story is your outage insurance), plus a metrics page sourced from real eval receipts: tool-selection accuracy (harness + online), parameter accuracy, execution success rate, judge-agreement summary, and the red-gate history.
4. Write the case study: the eval-first arc (contract → dataset → harness → labels → judges → gates → production loop), three failures the process caught with receipts, the judge trust policy, and what you'd do differently. Post it; pin the repo.

**Deliverable checklist — Production Reference Architecture.**

- [ ] Reference architecture doc + diagram matching deployed reality.
- [ ] Performance-loop experiment report: proposal, holdout design, verdict with numbers.
- [ ] Public demo (scoped, rate-limited) + metrics page fed by real eval artifacts.
- [ ] LinkedIn case study published; README front page updated to capstone state.

**Success criteria.**

- [ ] Fresh-clone reader reaches any claimed metric's receipt within two clicks.
- [ ] The optimization adopt/reject decision is defensible from published holdout numbers alone.
- [ ] The demo survives an induced tool outage in public without fabricating data.

**Docs to consult.** Optimization/recommendations, batch evaluations, A/B testing docs; your entire `docs/reports/` history — the case study is mostly already written.

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
- **No magic production claims.** Passing evals are scoped evidence about tested scenarios. The honest sentence is always available: "measured X on Y under Z."
