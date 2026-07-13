# Week 1 — AgentCore & Strands Fundamentals

**Phase:** Foundations (Weeks 1–4) · **Specimen:** hello-world agent with one tool
**Lanes touched:** first contact with every AgentCore service (see [Appendix A](../../LEARNING_PLAN.md#appendix-a--week--capability-map))
**Prerequisites:** none — this is the starting line. Read the plan's [Working assumptions](../../LEARNING_PLAN.md#working-assumptions) and [Appendix C — Guardrails](../../LEARNING_PLAN.md#appendix-c--guardrails) first.

[Week index](README.md) · [Next: Week 2 →](week-02-first-agent.md)

---

## Objective

Understand the AgentCore architecture (Runtime, Gateway, Memory, Identity, Policy, Evaluations, Observability, built-in tools), Strands SDK basics, the MCP protocol, and A2A communication. Stand up a local development environment.

## Why this week exists

The previous plan evaluated a chatbot; agents add a new failure surface — the tool-call loop — and AgentCore is nine-plus services with overlapping names. A week spent drawing the map prevents fifteen weeks of confusing Runtime (hosting) with the managed harness (orchestration), or Policy (deterministic control) with Guardrails (content evaluation).

There is a second reason the map matters for *this* plan specifically: every AgentCore service is a different **seam where agent behavior can be measured or governed**. Runtime is where deployed behavior diverges from local behavior (Week 3). Gateway is where tool descriptions get transformed before the model sees them (Week 4). Observability is where the trace shape — your eval contract's raw material — gets decided (Weeks 6–7, 14). Evaluations is a judge you will spend Weeks 9–10 deciding whether to believe. If you can't say which seam a behavior lives at, you can't design the eval that catches it regressing.

## Concepts

### The AgentCore service map

AgentCore (GA October 2025) is not one product; it is a set of composable services that each do one job for agents built with *any* framework. Learn them as a table first, then as a diagram in your own hand (build step 4):

| Service | One job | What it is *not* | First heavy use |
| --- | --- | --- | --- |
| **Runtime** | Serverless agent hosting: each user session gets a dedicated microVM (isolated compute, memory, filesystem), destroyed and sanitized when the session ends | Not an orchestrator, not a framework — your Strands code runs inside it unchanged | Week 3 |
| **Gateway** | Turns APIs, Lambda functions, and existing MCP servers into governed MCP tools behind one endpoint | Not a tool *author* — you still write the Lambda/API; Gateway describes and fronts it | Week 4 |
| **Memory** | Managed short-term (session events) and long-term (extracted facts) memory for agents | Not the microVM's session state — that dies with the session; Memory persists across them | Week 11+ (lightly) |
| **Identity** | OAuth inbound (who may invoke the agent) and outbound (what the agent may access), with a token vault for credentials | Not IAM — it complements IAM for user-level and third-party-API auth | Week 12 |
| **Policy** | Deterministic, code-level control over which agent–tool interactions are allowed | Not Bedrock Guardrails (that's LLM-based *content* evaluation); Policy is allow/deny logic the model can't argue with | Week 15 |
| **Built-in tools** | Code Interpreter, Browser, Web Search as managed tools | Not your tool portfolio — this plan mostly builds its own tools on purpose | Week 4 (Web Search) |
| **Observability** | OpenTelemetry traces, metrics, logs into CloudWatch; session/trace/span views | Not evaluation — it records what happened, it doesn't score it | Weeks 3, 7, 14 |
| **Evaluations** | Managed LLM-as-judge scoring over agent traces: 13 built-in evaluators at session, trace, and tool level, plus custom evaluators; online, on-demand, and batch modes | Not ground truth — it's a versioned judge you must calibrate before trusting (Weeks 9–10) | Weeks 10, 13–14, 16 |
| **AgentCore CLI** | `npm install -g @aws/agentcore` — scaffolds projects, local dev server with Agent Inspector, CDK-backed deploys, eval commands | Not required — everything has console/API paths — but it's this plan's primary interface | Week 3 onward |

Two confusion pairs worth memorizing now, because their names actively invite the mistake:

- **Runtime vs. the managed harness.** Runtime *hosts* code you wrote. The managed harness (preview) is a declarative service that *assembles* an agent from config (model + tools + instructions) in a few API calls. This plan builds on Runtime; the harness appears only as a contrast lane.
- **Policy vs. Guardrails.** Policy is deterministic allow/deny over agent–tool interactions — infrastructure, not inference. Bedrock Guardrails is model-based content screening. Week 15 uses both, at different layers, for different failure classes.

### The agent loop — the new failure surface

A Strands agent is a loop: the model reads the conversation, **reasons**, either produces a final answer or **selects a tool** and emits arguments; Strands **executes** the tool and appends the result to the conversation; the model reads it and continues until it **synthesizes** a response. Everything this plan evaluates lives at one of those four stages:

1. **Reasoning** — did the model understand what was asked? (Hardest to gate; mostly judged, Week 10.)
2. **Tool selection** — did it call a tool it should have? Did it *refrain* when it should have? (Deterministic gates, Week 8; the plan's flagship metric.)
3. **Parameter construction** — are the arguments right, and *derived from context* rather than fabricated? (Week 6 arg constraints; `Builtin.ToolParameterAccuracy` in Week 10.)
4. **Execution & synthesis** — did the tool succeed; did the model represent the result honestly, including failures? (Failure taxonomy, Week 5; failure-behavior gates, Week 8.)

When you run the hello-world agent below, the deliverable is not the answer — it's the **message list** (`agent.messages`), which records each loop stage as a message entry. Being able to point at the list and say "this entry is selection, this one is the tool result, this one is synthesis" is the week's real skill. Every trace schema, gate, and judge in this repo is a formalization of that annotation exercise.

### Strands SDK mental model

Strands (`strands-agents`, Python 1.x) is a **model-driven** SDK: you give it a model, tools, and a prompt, and the SDK runs the loop — there is no graph to wire for a single agent. The pieces you touch this week:

- **`Agent`** — holds the system prompt, tool list, model, and conversation state. Calling `agent("...")` runs the whole loop.
- **`@tool`** — decorates a plain Python function into a tool. The *docstring becomes the tool description the model reads*, and the *type-hinted signature becomes the input schema*. This means tool descriptions are prompts — versioned, evaluated artifacts, not comments. Week 13's seeded regression will exploit exactly this.
- **Model providers** — Strands defaults to Claude on Bedrock; Anthropic API, Ollama (local), LiteLLM, and others are swappable behind the same `Agent`. Provider choice changes tool-calling behavior, which is why Week 2 treats it as a controlled variable.

If the default Bedrock call fails this week, fix **model access** now (Bedrock console → Model access, in `us-east-1`) — not in Week 3 when a deploy failure will have five other possible causes.

### MCP primer (half-page version)

The Model Context Protocol (spec revision **2025-11-25**) is a client–server protocol that standardizes how an agent discovers and invokes external capabilities. What you need for this plan:

- **Three primitives.** Servers expose **tools** (model-invoked functions with JSON Schema inputs), **resources** (application-read data, addressed by URI), and **prompts** (user-selected templates). This plan cares almost exclusively about tools.
- **Two transports.** **stdio** (server runs as a local subprocess — what most dev-tool MCP servers use) and **streamable HTTP** (remote servers; what Gateway speaks). Strands' `MCPClient` supports both (Week 4).
- **Discovery is dynamic.** A client calls `tools/list` and gets tool names, descriptions, and schemas at runtime. That's powerful and dangerous: **an MCP tool description is a prompt injected into your agent by whoever runs the server.** This plan's answer is explicit registration and capability manifests (Week 5) — you pin what the agent may use; discovery never expands it.
- **Where it shows up here.** Gateway turns Lambdas/APIs into MCP tools (Week 4); external MCP servers get consumed as tool sources (Week 4); the MCP tool schema is the shape your tool contracts formalize (Week 5).

### A2A primer (half-page version)

Agent2Agent (**v1.0**, governed by the Linux Foundation) standardizes *agent-to-agent* communication — a different altitude than MCP's *agent-to-tool*:

- **Agent Card** — a published JSON description of an agent: identity, capabilities, endpoint, auth requirements. Discovery document and trust anchor in one.
- **Tasks and messages** — a client agent sends a task; the remote agent works it through a lifecycle (submitted → working → completed/failed), exchanging messages and artifacts along the way. Long-running, stateful — unlike a tool call.
- **Rule of thumb** — if the remote thing has its own model and makes its own decisions, it's an agent → A2A. If it deterministically executes what it's told, it's a tool → MCP. The line matters to evals: a tool's correctness is checkable against a contract; a delegated agent's correctness needs the coordination evals of Week 15.
- **Where it shows up here.** Week 15 wraps one Strands agent as an `A2AServer` and consumes it from another; Runtime speaks the A2A contract for deployed agents.

### Billing meters and safety habits — day one, not later

Everything managed here is consumption-billed, and the meters run per *use*, not per *month*: Runtime charges per-second CPU/memory per session; Evaluations bills judge-model tokens per scored span; Gateway bills per call; Memory per event/retrieval. None of that is scary at this plan's scale **if** two habits start now:

1. **AWS Budgets alarm at a low threshold, this week**, before anything is deployed. It's a Week 1 success criterion, not a nice-to-have.
2. **Public-repo discipline from the first commit.** Placeholders only: `<AWS_ACCOUNT_ID>`, `us-east-1`, `example.com`. Never commit account IDs, ARNs, raw traces, session IDs, keys, or model output containing any of those. The `public_safety_scan` script (Week 6) will enforce it in CI; the habit starts before the tooling exists. Full rules: [AGENTS.md](../../AGENTS.md) and the plan's [Working assumptions](../../LEARNING_PLAN.md#working-assumptions).

## Build steps

### 1. Install the toolchain and verify versions

```bash
python3 --version          # 3.10+
node --version             # 20+
npm install -g @aws/agentcore
agentcore --version
uv venv && source .venv/bin/activate
uv pip install strands-agents strands-agents-tools
aws configure              # or SSO; then grant Bedrock model access in the console
```

Note the split: **agent code is Python; the AgentCore CLI is an npm package.** Two runtimes, both required, independently versioned. `agentcore update` handles CLI updates later.

Before moving on, confirm each layer independently rather than debugging the stack top-down later:

- `aws sts get-caller-identity` returns your identity (credentials work).
- Bedrock model access shows the Claude models you'll use as **Access granted** (console → Bedrock → Model access).
- `python -c "import strands"` succeeds inside the venv.

### 2. Write the hello-world agent

One custom tool calling one AWS service, so the first agent you ever run already goes through the tool loop:

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

Why *this* hello world: the question is unanswerable from model memory. The only way the agent can answer correctly is by calling the tool — so success is verifiable from the message list, not from vibes. (And mind the output: the ARN it prints is exactly the kind of thing that never goes in a commit.)

### 3. Annotate the agent loop

Read the Strands agent-loop docs, then capture the message list (`agent.messages`) from your run and label each entry with the loop stage it represents: model reasoning → tool selection (the `toolUse` block: which tool, what arguments) → execution (the `toolResult` block) → response synthesis. Commit the annotated version (scrubbed of account ID/ARN — replace with placeholders) as a doc.

This annotation is the seed of everything: Week 6's execution-trace schema is this exercise formalized into JSON Schema; Week 7 records assistant text immediately before a `toolUse` block as optional `selectionReasoning`, or explicit null when no such text is emitted. It never invents a causal explanation.

### 4. Write `docs/architecture.md`

A Mermaid diagram of the AgentCore components with one-sentence annotations *in your own words* — including the two 2026 additions most plans omit: **Policy** and **Evaluations**. Add a half-page primer each for MCP (spec rev 2025-11-25: tools/resources/prompts, stdio + streamable HTTP transports) and A2A (v1.0: Agent Cards, tasks, messages). The Concepts section above is a starting map, but the deliverable is your paraphrase, checked against the docs — if you can only reproduce my table, you've memorized, not learned.

### 5. Optional dev-environment upgrade

Register the AgentCore MCP server from `awslabs/mcp` with your coding assistant so it can inspect AgentCore resources during later weeks. (Meta note: this is MCP being used *on* your dev environment — the same protocol you just wrote a primer about, in its stdio-transport form.)

## Exercises — guided discovery

Work these before checking any answer source. Hints escalate; stop at the first one that unblocks you.

**1. Predict the message list.** Before running `hello.py`, write down the exact sequence of messages you expect `agent.messages` to contain (roles and content types, not words). Then run and diff.
- *Hint 1:* How many distinct roles can appear, and who authors the tool result?
- *Hint 2:* Strands docs, "Agent Loop" concept page — look at the message-flow diagram.
- *Hint 3:* A single tool-using turn produces at least: user → assistant (with `toolUse`) → user (with `toolResult`) → assistant (final text). Which of those did you miss?

**2. Force a refusal.** Ask the hello agent "What is the capital of France?" What *should* happen, given its system prompt — and what actually happens?
- *Hint 1:* The system prompt says "Answer AWS facts only via tools; never guess." Is this an AWS fact? Is there a tool for it?
- *Hint 2:* Check `agent.messages` — did it call `caller_identity` anyway? (Some models call an irrelevant tool rather than decline.)
- *Hint 3:* Whatever you observed is your first data point for Week 6's **no-tool rows** — write it down as a future dataset row.

**3. Which service am I touching?** For each request, name the AgentCore service where it lives: (a) "the agent should keep working memories of this user across sessions", (b) "the agent may only call the weather tool, never the email tool", (c) "wrap our existing REST API as agent tools", (d) "score last week's production conversations for tool-selection quality", (e) "run the agent so two users can never see each other's state", (f) "the agent needs a GitHub token at runtime without me hardcoding it."
- *Hint 1:* Each answer is one row of the service-map table.
- *Hint 2:* (b) has two defensible answers at different layers — one deterministic, one content-based. Which is which?

**4. Find the tool schema.** Somewhere between your `@tool` function and the model, a JSON schema for `caller_identity` exists. Find where you can observe it.
- *Hint 1:* What did the decorator do with your docstring and type hints?
- *Hint 2:* Strands docs on Python tools — look for how tool specs surface on the agent (tool registry / tool config).
- *Hint 3:* Compare what you find against what you'd have written by hand — this gap (authored intent vs. generated schema) is what Week 5's tool contracts close.

**5. Cost meter walk.** Using the AgentCore pricing page, write down which meter each of these turns: one `agentcore invoke` against a deployed agent; one online-eval-sampled trace; one Gateway tool call. No numbers needed — just name the meters.
- *Hint 1:* Runtime bills differently than Lambda — what's the unit?
- *Hint 2:* Evaluations' meter isn't per-trace. What is it?

## Gotchas & drift watch

- **Model access is the classic Week 1 wall.** `AccessDeniedException` from Bedrock means model access wasn't granted in the console for that Region — it is not an IAM problem in your terminal. Grant access for the default Strands model *and* the judge models you'll want by Week 10.
- **Two runtimes, two failure styles.** `agentcore` failing is a Node/npm problem; the agent failing is Python/boto3. Don't debug one with the other's tools.
- **Default model drift.** Strands' default Bedrock model changes across SDK releases (docs currently show recent Claude models; the exact default in *your* installed version is what matters — check `agent.model.config` rather than trusting any doc, including this one).
- **Region discipline.** This plan assumes `us-east-1`. AgentCore feature availability is not uniform across Regions — verify before each managed-lane week, and remember *available* is not *enabled*.
- **The CLI surface was verified against docs on 2026-07-07** (commands: `create`, `dev`, `deploy`, `invoke`, `logs`, `traces`, `status`, `add`, `remove`, `run`, `evals`, `pause`, `resume`, `package`, `validate`, `fetch`, `update`). The CLI is new and moving — when a flag in this repo's docs disagrees with `agentcore --help`, trust the binary and file a doc fix. Subscribe to the [release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html).
- **Don't build ahead.** Per [AGENTS.md](../../AGENTS.md): this week's exit gate is the Success criteria below — Week 2 doesn't start with them open.

## Deliverable checklist — Local Dev Environment + Architecture Notes

- [ ] Repo initialized with the target tree, `README.md`, and this plan.
- [ ] `src/agents/hello.py` runs from a fresh clone with documented setup.
- [ ] `docs/architecture.md`: annotated component diagram + MCP/A2A primers.
- [ ] Annotated agent-loop trace (message list with your labels) committed as a doc.

## Success criteria

- [ ] You can explain, without notes, when a request touches Runtime vs Gateway vs Memory vs Policy.
- [ ] Hello-world agent answers via the tool (verified in the message list — not from model memory).
- [ ] Budget alarm active; teardown habits documented before anything is deployed.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07. When these and this file disagree, the docs win.

- [What is Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — the service map from the source; read it *after* drafting your own diagram, as the check.
- [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-cli.html) — install + first project; the command list your Week 3 workflow uses.
- [AgentCore release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html) — subscribe; this plan's paraphrases drift against it by design.
- [Strands Agents Python quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/) — `Agent`, `@tool`, model providers, credentials; the code you write this week is this page.
- [Strands agent loop concepts](https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/) — the reasoning → selection → execution cycle you annotate in build step 3.
- [AgentCore FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/) — surprisingly useful one-paragraph answers for the service-boundary questions (harness vs Runtime, CLI vs SDK).
- [MCP specification (2025-11-25)](https://modelcontextprotocol.io/specification/latest) — skim architecture + tools; you need the primitives and transports, not the wire format yet.
- [A2A protocol v1.0](https://a2a-protocol.org/latest/) — read "What is A2A" and the Agent Card topic; depth waits for Week 15.

## Self-check

Answer without looking anything up. If any of these takes more than a sentence of hesitation, revisit that concept before closing the week.

1. A request comes in: "book me a flight using the corporate travel API, and remember my seat preference for next time." Name every AgentCore service that request plausibly touches, in order.
2. What are the four stages of the agent loop, and at which stage does a *fabricated tool argument* originate? A *silently swallowed tool failure*?
3. Why is a tool docstring a versioned artifact in this repo rather than a comment?
4. MCP tool vs. A2A agent: which one gets a task lifecycle, and why does the difference change how you'd evaluate it?
5. What two habits were required *this* week specifically because they can't be retrofitted credibly later?
