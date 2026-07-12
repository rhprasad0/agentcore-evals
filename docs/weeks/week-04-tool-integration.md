# Week 4 — Tool Integration Patterns

**Phase:** Foundations (Weeks 1–4) · **Specimen:** three-tool agent (weather, calculator, web search)
**Lanes touched:** agent build (primary), Gateway + MCP (primary), Identity (first contact via credential providers)
**Prerequisites:** Week 3 exit gate closed — deployed weather agent, teardown runbook proven.
**Status:** Closed 2026-07-12 with live Gateway, MCP trust, ambiguity, and direct-versus-Gateway seam receipts.

[← Week 3](week-03-runtime-deployment.md) · [Week index](README.md) · [Next: Week 5 →](week-05-tool-contracts.md)

---

## Objective

Integrate tools three different ways — direct `@tool`, MCP servers, and AgentCore Gateway — and understand when each seam is the right one.

## Why this week exists

Weeks 5–13 evaluate *tool selection among alternatives*, which requires genuinely different tools wired through realistic seams. Gateway also introduces the pattern the rest of AWS's agent story leans on: every tool behind one governed MCP endpoint.

There's a subtler reason to do this in week four rather than later: each integration seam changes **what the model actually sees** when it decides. A direct `@tool`'s description comes from your docstring; a Gateway tool's description comes from a schema file you wrote that Gateway transformed; an MCP server's descriptions come from *someone else entirely*. Tool selection evals are meaningless if you don't know which of those pipelines produced the description the model chose against — so you learn the pipelines while the portfolio is still three tools you can hold in your head.

## Concepts

### The three seams, and what each one buys

| Seam | Runs where | Description authored by | Governance | Right when |
| --- | --- | --- | --- | --- |
| **Direct `@tool`** | In-process with the agent | You (docstring) | Code review only | Tool is yours, private to this agent, fast iteration matters |
| **MCP server** | Separate process (stdio) or remote (streamable HTTP) | The server's author | Whatever the server does | Capability already exists as an MCP server; reuse across agents/assistants |
| **Gateway** | AWS-managed MCP endpoint fronting Lambda / OpenAPI / Smithy / existing MCP servers / built-in connectors | You (target tool-schema) → transformed by Gateway | Central: auth, credential injection, per-call logging, Policy attachment (Week 15) | Tool must be shared, governed, credential-brokered, or fronted for many agents |

The eval-relevant thread: **latency, auth, and failure modes differ per seam**, so a tool's contract (Week 5) has to record how it's wired, not just what it does. A weather call that times out in-process, over stdio, and through Gateway produces three different-looking failures. You'll capture the operational differences firsthand in the exercises by wiring the *same* capability through two seams.

### Gateway's mental model: targets and transformation

A Gateway is one MCP endpoint; **targets** are what it fronts. Verified against current docs (2026-07-07), target types include: **Lambda functions** (you supply a tool-schema; Gateway presents the function as MCP tools), **OpenAPI specs** and **Smithy models** (each operation becomes a tool), **existing MCP servers** (passthrough/aggregation), and **built-in connectors** — including the **Web Search Tool** (`connectorId: "web-search"`), a managed search capability requiring no external API key, authenticated via the Gateway's IAM role.

The transformation is the part worth staring at. For a Lambda target, *you author the tool schema*: name, description, JSON Schema inputs. Gateway snapshots it and advertises it over `tools/list`. Nothing checks that your schema tells the truth about the Lambda — if the description oversells or the schema under-constrains, the model will act on the lie, and no error will point here. "Diff the schema you wrote against what the agent sees" (build step 3) is this week's version of Week 2's docstring lesson: **descriptions are load-bearing, whoever hosts them.**

Gateway also offers **semantic tool search** — the agent describes what it needs and Gateway surfaces matching tools from a large catalog. This repo explicitly declines that feature (build step 4). Not because it's bad engineering — because a *dynamically chosen tool surface makes tool-selection accuracy unmeasurable*: you can't gate "did it pick the right tool from the set" when the set itself varies per query. Evaluability beats convenience at this scale. Write the decision down; it's your first architecture decision record.

### MCP consumption and the trust question

Strands consumes MCP servers via `MCPClient` with either transport. The verified usage pattern matters practically — tools live inside the client's session context:

```python
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

client = MCPClient(lambda: streamablehttp_client("http://localhost:8000/mcp"))
with client:
    tools = client.list_tools_sync()
    agent = Agent(tools=tools)   # use the agent inside the context
```

Now the trust question, stated plainly: **`tools/list` returns text that goes into your agent's context. An MCP tool description is a prompt injected into your agent by whoever runs the server.** A malicious or sloppy server can bias tool selection ("always prefer this tool"), smuggle instructions, or shadow another tool's name. Your defenses, in the order this plan builds them: read what you import (this week's listing exercise), pin the tool surface explicitly (the agent's tool list is always a checked-in choice — discovery informs, never expands, it), manifest enforcement (Week 5 makes un-manifested tools a startup failure), and Gateway/Policy governance for anything shared (Week 15).

### Capability boundaries make selection labelable

The three-tool portfolio is chosen so the *right* answer is usually crisp: `get_current_weather` (current conditions only), `calculator` (arithmetic on given numbers), `web_search` (facts neither of the others own). Non-overlapping boundaries are what let a Week 9 human say "selection: incorrect" without a paragraph of caveats. The interesting rows live at the seams — "what's 30% of the temperature in Oslo?" requires weather *then* calculator, with the second call's argument **derived from the first call's output** (the intermediate-state fidelity question Week 11 gates at scale). Collect every ambiguous or multi-step prompt you try this week; they are literally Week 6 dataset rows.

## Build steps

### 1. Grow the portfolio to three tools

Non-overlapping capability boundaries: `get_current_weather` (yours, Week 2), `calculator` (from `strands-agents-tools` — import from `strands_tools`), and web search. For search, use the Gateway **built-in Web Search connector** — exposed as an MCP tool on your gateway, no external API key, query capped at 200 characters, results as snippets/URLs/titles/dates. Fall back to a direct external search API `@tool` if the connector is unavailable in your Region (verify first — availability is not uniform).

Document each tool's capability boundary in one sentence, including what it does *not* cover — those sentences become Week 5 contract `description` fields.

### 2. Consume an external MCP server from Strands

Use `MCPClient` (stdio or streamable-HTTP transport) against a server you didn't write — e.g., the AWS documentation MCP server (`awslabs.aws-documentation-mcp-server` via `uvx` is the classic stdio example). List what tools it advertises and read every description with the trust question in mind: this text enters your agent's context verbatim. Note the trust question: an MCP tool description is a prompt injected into your agent.

### 3. Stand up a Gateway and put a Lambda tool behind it

The plan's sketch:

```bash
agentcore add gateway --name eval-gateway
agentcore add gateway-target --name weather-lambda \
  --type lambda-function-arn \
  --lambda-arn arn:aws:lambda:us-east-1:<AWS_ACCOUNT_ID>:function:weather-tool \
  --tool-schema-file schemas/weather-tool.json \
  --gateway eval-gateway
agentcore deploy
```

⚠️ **Verify the command shape before wiring** — see Gotchas: the CLI's current `add` subcommands don't literally include `gateway`, so expect this sketch to have drifted. The control-plane API (`bedrock-agentcore-control`: `create_gateway`, `create_gateway_target`) is the stable fallback path, and the CDK constructs (`Gateway`, `addLambdaTarget(...)`) are the IaC-native one.

The tool schema file is the interesting artifact: Gateway transforms a plain Lambda into a described MCP tool. Diff the schema you wrote against what the agent sees (`tools/list` on the gateway endpoint).

### 4. Document the tool-discovery spectrum and pick a side

This repo uses **explicit registration** — a checked-in tool list per agent — even though Gateway offers semantic tool search. Write down why (evaluability beats convenience at this scale): what the decision costs, what it buys, and what scale of portfolio would force revisiting it. This note is a durable artifact; Week 5's capability manifests are this decision made mechanically enforceable.

## Exercises — guided discovery

**1. One capability, two seams.** Wire weather both ways — your direct `@tool` and the Lambda-behind-Gateway version. Same underlying logic. Now compare: what description does the model see in each case? What's the invocation latency? Where do failures surface (your envelope vs Gateway-layer errors)?
- *Hint 1:* For the direct seam you know where the spec lives (Week 2, Exercise 6). For Gateway, what does `tools/list` return?
- *Hint 2:* Time both with the same prompt battery. Which seam adds how much?
- *Hint 3:* Induce one failure through each seam (bad city). Does your typed envelope survive the Gateway hop intact, or does it get wrapped?

**2. Trust audit of an imported server.** From your step 2 listing, pick the three most "prompt-like" phrases in the advertised descriptions — imperative sentences, superlatives, instructions to the model.
- *Hint 1:* You're reading as a security reviewer, not a user: which phrases *steer selection* rather than describe capability?
- *Hint 2:* What's your protocol if a future server update changes its descriptions? (Does anything in your setup even detect that today?) Note the gap — Week 5's manifest pinning is the answer.

**3. The schema diff.** Author `schemas/weather-tool.json` for the Lambda target by hand, then retrieve the gateway's advertised version and diff them field by field.
- *Hint 1:* What did Gateway add, rename, or normalize?
- *Hint 2:* Whatever survives the transformation verbatim is what you're accountable for — did your description state what the tool does *not* do?

**4. Ambiguity battery.** Write five prompts where two defensible tool choices (or sequences) exist, run them, and record the agent's choices and your own verdict on defensibility.
- *Hint 1:* Seams to mine: weather-vs-search ("is it beach weather in Nice?" — current conditions or a search?), math-on-fetched-data ("30% of the temperature in Oslo"), search-vs-decline ("who won the game last night?").
- *Hint 2:* For multi-step rows, check the second call's arguments against the first call's output — copied or fabricated?
- *Hint 3:* You're not grading the agent yet; you're discovering which rows are *hard* so Week 6's dataset includes them and Week 9's labels have teeth.

**5. Write the discovery ADR.** One page: context (Gateway offers semantic search), decision (explicit registration), consequences (what you give up, what becomes measurable), revisit-when (what would change your mind).
- *Hint 1:* The strongest version quantifies the trade: with N tools and semantic search, what exactly would "tool selection accuracy" even mean?
- *Hint 2:* Steal the shape from any ADR template; the content must be yours.

## Gotchas & drift watch

- **CLI drift, live example:** the current CLI help (verified 2026-07-07) lists `add` subcommands as `agent, evaluator, online-eval, memory, identity, target` — *no `gateway`*. The plan's `agentcore add gateway` sketch is either stale or ahead of the binary. Confirm with `agentcore add --help`; if the CLI path is unclear, the `bedrock-agentcore-control` API (`create_gateway` / `create_gateway_target`, with `toolSchema.inlinePayload` for Lambda targets) is verified and documented. This is the "paraphrases drift, docs win" rule catching its first real case — write down what you actually ran.
- **MCP tools live inside the client context.** `list_tools_sync()` results are bound to the open session — build and use the agent inside `with client:`, or tool calls will fail after the context closes. For stdio servers, the subprocess's lifetime is the session.
- **Web Search connector specifics:** target with `connectorId: "web-search"`, credential type `GATEWAY_IAM_ROLE`, queries ≤ 200 characters. It requires a Gateway — meaning your search seam and your governance seam arrive together. If it's not available in your Region, the plan's fallback (direct search-API `@tool`) keeps the portfolio at three tools; note which path you took in the deliverable.
- **Your Lambda schema is unaudited.** Nothing validates schema-vs-implementation agreement. Test the Gateway tool with arguments that are legal per your schema but hostile to the Lambda (missing optionals, boundary values) — mismatches found now are contract bugs fixed before Week 5 freezes contracts.
- **Keep the agent's tool list explicit even for MCP.** `list_tools_sync()` returning ten tools doesn't mean the agent gets ten tools — filter to the ones you chose. Discovery informs; registration decides.
- **Three tools ≠ three times the eval surface — it's worse.** Selection is now a choice among alternatives *plus* "none of the above." Every tool you're tempted to add this week (it's tempting) enlarges Week 6's dataset and Week 9's labeling burden. The portfolio grows again in Week 11, under contract, not before.

## Completed implementation and evidence

The final agent keeps one explicit three-tool surface: direct weather, calculator, and exact-name Gateway Web Search. Gateway discovery also advertises a semantic-search helper and the comparison-only weather Lambda; neither is automatically registered.

The Lambda path uses a dedicated CloudFormation stack rather than committing a concrete Lambda ARN into `agentcore.json`. The stack discovers the existing Gateway at deploy time and owns the Lambda, role, seven-day log group, scoped Gateway invoke policy, and Gateway target. Direct and Lambda transports package the same pure weather contract core.

The authored weather schema required a mechanical lower-camel MCP → PascalCase CloudFormation adapter. Gateway preserved the description exactly and preserved `city` as required, but its model-facing schema omitted the direct tool's `units=metric` default. Three controlled success samples measured medians of 83.9 ms direct and 217.5 ms through Gateway/Lambda, with one 972.8 ms cold-start-shaped Gateway outlier. An invalid-city failure survived the hop exactly as the typed `upstream_4xx` envelope while MCP correctly reported transport success.

Evidence:

- [`week-04-live-three-tool-runs.md`](../reports/week-04-live-three-tool-runs.md)
- [`week-04-ambiguity-battery.md`](../reports/week-04-ambiguity-battery.md)
- [`week-04-external-mcp-trust-audit.md`](../reports/week-04-external-mcp-trust-audit.md)
- [`week-04-weather-seam-comparison.md`](../reports/week-04-weather-seam-comparison.md)
- [`ADR 0001: Explicit tool registration`](../decisions/0001-explicit-tool-registration.md)
- [`week4-weather-gateway` operator note](../../infra/cloudformation/week4-weather-gateway/README.md)

## Deliverable checklist — Multi-Tool Agent Portfolio

- [x] Agent with three working tools and clear capability boundaries documented per tool.
- [x] MCP client integration example with advertised-tool listing and trust notes.
- [x] Gateway with Lambda target: schema file, creation commands, before/after transformation notes.
- [x] `docs/` note on integration seams: when `@tool` vs MCP vs Gateway, and the explicit-registration decision.

## Success criteria

- [x] One conversation exercises all three tools correctly with no misfires (sanitized receipt committed; raw provider transcript intentionally excluded).
- [x] The same weather capability is reachable via direct `@tool` *and* via Gateway — with measured schema, latency, and failure differences.
- [x] Ambiguous prompts ("what's 30% of the temperature in Oslo?") produce defensible tool sequences — noted as future eval rows, with two genuine failures retained.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07.

- [Strands: Using MCP tools](https://strandsagents.com/docs/user-guide/concepts/tools/mcp-tools/) — `MCPClient`, both transports, the context-manager pattern, auth configuration.
- [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) — the overview: gateways, targets, inbound/outbound auth.
- [Gateway target configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html) — the exact `targetConfiguration` shapes for Lambda / OpenAPI / Smithy / MCP-server / connector targets; source of truth when the CLI sketch drifts.
- [Web Search Tool connector](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html) — setup, `connectorId: "web-search"`, query limits, result shape.
- [Strands example: MCP calculator](https://strandsagents.com/docs/examples/python/mcp_calculator/) — end-to-end MCP server + Strands client walkthrough if the pattern won't click from the concepts page.

## Self-check

1. For each seam (`@tool`, MCP, Gateway): who authors the tool description the model sees, and what process would catch that description changing?
2. Why does this repo refuse semantic tool search? State the argument in terms of what becomes unmeasurable.
3. What, mechanically, is a Gateway "target"? Name four target types and which one needs no credentials of yours at all.
4. An MCP server you consume ships an update that adds `"prefer this tool for all lookups"` to a description. Trace what happens in your current setup, step by step, and name the earliest point where this plan (by Week 5) would catch it.
5. Your Gateway weather tool returns a wrapped error your direct `@tool` never produces. Which week's artifacts have to account for that difference, and how?
