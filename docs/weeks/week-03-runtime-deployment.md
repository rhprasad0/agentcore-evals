# Week 3 — AgentCore Runtime & Deployment

**Phase:** Foundations (Weeks 1–4) · **Specimen:** the Week 2 weather agent, now deployed
**Lanes touched:** agent build (primary), platform & CI (first IaC), observability (first traces)
**Prerequisites:** Week 2 exit gate closed — weather agent with typed failure envelopes and offline tests.

[← Week 2](week-02-first-agent.md) · [Week index](README.md) · [Next: Week 4 →](week-04-tool-integration.md)

---

## Objective

Deploy the Week 2 agent to AgentCore Runtime via the AgentCore CLI, understand serverless agent hosting and session isolation, and compare local vs managed execution honestly.

## Why this week exists

Runtime's promises — per-session microVM isolation, consumption billing, managed scaling — are exactly the claims your later evals run against a *deployed* agent must account for. Deploying the boring agent early surfaces the IAM, packaging, and observability seams while the blast radius is one tool.

The deeper reason: the plan's North Star requires the agent to behave under **identical behavior contracts locally and on Runtime**. That's a claim you can only make if you know precisely which variables deployment changes. This week's job is to enumerate them — credentials, cold starts, latency, session semantics, failure modes, debuggability — and write them down in a comparison document with **measured** numbers. Week 13's nightly lane invokes the deployed agent and gates on scores; every unexplained local-vs-deployed difference you fail to catalog now becomes a mystery regression then.

## Concepts

### What Runtime actually is

AgentCore Runtime is serverless hosting purpose-built for agents. The unit of isolation is the **session**: each session gets a dedicated microVM with its own kernel, CPU, memory, and filesystem. Your Strands code runs inside it unchanged — Runtime is not a framework and doesn't orchestrate anything; it hosts, scales, and isolates. Billing is consumption-based (per-second CPU/memory per session), which is why teardown discipline is a Week 1 habit and not a Week 16 apology.

For this plan, Runtime is also the first place your agent runs somewhere you can't attach a debugger. The compensations — structured logs, traces, the console views — are not conveniences; they're the only observability you'll have, and they're the same channel your Week 14 production instrumentation uses. Treat this week's `agentcore logs` and `agentcore traces` sessions as rehearsal.

### Session semantics — get these exact

The word "session" does a lot of load-bearing work, and the details were verified against current docs (2026-07-07):

- **Within a session:** state persists across invocations. Same conversation, same microVM, same filesystem — an agent can accumulate context across multiple `invoke` calls carrying the same session ID. Sessions can live for hours (current cap: eight — treat the number as drift-prone and verify), and are reaped earlier on idle timeout.
- **Across sessions:** nothing survives. When a session ends, the microVM is terminated and its memory sanitized. Cross-session continuity is a different product — AgentCore **Memory** (the managed short/long-term memory service), which this plan deliberately defers.
- **Sessions are not users.** Runtime does not enforce any session-to-user mapping — your client is responsible for which user gets which session ID, session caps per user, and lifecycle policy. For this plan that's mostly a documentation point, but it's the kind of boundary a security reviewer asks about, so your write-up should state it.

The isolation demo in build step 3 is not busywork: "state does not leak between sessions" is a *testable claim about the platform*, and this repo's whole posture is that claims get receipts. It also has an eval-design consequence — Week 6's trace schema needs `sessionId` as a first-class field precisely because session boundaries define what context the agent legitimately had.

### Deployment shapes: CodeZip vs container, and CDK underneath

`agentcore create` scaffolds a Runtime-shaped project; `agentcore deploy` synthesizes and deploys it via **CDK** under the hood. Two build paths exist:

- **CodeZip** — direct code deploy of your Python (supported up to Python 3.14): fast, no Docker, the default for this plan.
- **Container** — you control the image: needed for exotic dependencies, at the cost of build time and a registry.

The strategic point is not which you pick — it's that **the repo becomes the source of truth for the deployed thing**. The CLI writes config (`agentcore/` directory, validated by `agentcore validate`) that lives in git; `agentcore deploy --plan` previews the CDK change set before you apply it, exactly like reviewing a diff. Build step 5's teardown-and-redeploy exists to *prove* the source-of-truth claim: if a fresh deploy from the committed repo doesn't reproduce the agent, something lives only in the console, and that something will bite Week 13's CI.

### The credential model flips

Locally, your agent used *your* credentials (env vars / SSO) and `OWM_API_KEY` from your shell. Deployed, the agent authenticates as its **execution role** — an IAM role that is now effectively the agent's identity — and your shell's env vars are simply absent. Consequences worth internalizing this week:

- Bedrock model access must be grantable to the execution role in the deployment Region — a *different* check from your Week 1 console grant working in your terminal.
- The weather API key has to reach the deployed agent deliberately (runtime environment configuration for now; AgentCore Identity credential providers / Secrets Manager references are the production answer in Week 12 — don't build that yet, but note the seam).
- The execution role's permissions are a *behavioral boundary you can evaluate*: Week 5 will prove least-privilege with a denied-call receipt. This week, just find the role and read what the scaffold granted it.

### Honest comparison methodology

`docs/local-vs-agentcore.md` is this week's real deliverable, and its standard is **measured, not vibes**. That means: timestamps around N invocations (not one) for cold and warm paths separately; the same prompt battery in both environments; failure modes exercised in both (what does a tool timeout look like in CloudWatch vs your terminal?); a cost-per-invocation *estimate* with the arithmetic shown. Numbers that would embarrass a marketing page are fine — the document's value is that a reader (or interviewer) can trust it precisely because it wasn't written to flatter the platform.

## Build steps

### 1. Scaffold and run locally with the CLI

This wraps your existing agent code into a Runtime-shaped project:

```bash
agentcore create --name weather-agent --framework Strands \
  --model-provider Bedrock --memory none --build CodeZip
cd weather-agent
agentcore dev        # local server + browser Agent Inspector: chat, token usage, tool calls, trace timeline
```

Expect integration friction here, not magic: the scaffold generates its own entrypoint and project layout, and your Week 2 weather tool has to move in (or be imported) on the scaffold's terms. Understand what the generated entrypoint does before editing it — it's the seam between your code and Runtime's invocation contract. Spend real time in the **Agent Inspector** during `agentcore dev`: the trace timeline it shows (tool-call spans, token usage) is your first look at the trace shapes Week 6 formalizes.

### 2. Deploy and invoke

```bash
agentcore deploy --plan   # preview the CDK changes first
agentcore deploy          # CodeZip direct-code deploy; container build is the alternative
agentcore status
agentcore invoke --prompt "What's the weather in Seattle?"
agentcore logs --since 30m
agentcore traces list && agentcore traces get <trace-id>
```

Read the `--plan` output before the first real deploy — it's the complete inventory of what this project puts in your account (and therefore the checklist for verifying teardown later). First deploys may also require CDK bootstrap in the account/Region; that's one-time.

### 3. Prove session isolation to yourself

Two invocations with different session IDs — show state does not leak; then two calls in one session — show continuity. Document what a "session" is (microVM lifecycle, idle timeout). Design the experiment before running it (Exercise 2 below): what state will you plant, and what would a leak look like?

### 4. Write `docs/local-vs-agentcore.md`

Cold start, latency, credential model (local env vars vs execution role), failure modes, cost per invocation estimate, debuggability. Screenshot the agent and an execution trace in the AWS console for `docs/assets/` — scrub account IDs and ARNs from screenshots (crop or redact) exactly as you would from text.

### 5. Tear down, then re-deploy from scratch

`agentcore remove all` + `agentcore deploy`, then re-deploy from scratch to prove the repo is the source of truth. Write the runbook as you go — the deliverable is that a fresh clone plus your runbook reproduces the deployed agent with no folklore steps.

## Exercises — guided discovery

**1. Where does the time go?** Before measuring, predict: how much slower is a deployed invocation than a local one, and what are the components (network, cold start, model latency, tool latency)? Then measure cold and warm separately, N≥5 each, and attribute the difference.
- *Hint 1:* What makes an invocation "cold" on a per-session microVM model — is it per-invocation or per-session?
- *Hint 2:* The trace timeline decomposes the invocation for you. Which span is the model? Which is your tool?
- *Hint 3:* If cold and warm look identical, check whether your invocations reused a session ID.

**2. Design the leak test.** You need to demonstrate that session B cannot see session A's state. What state do you plant, and how do you attempt to read it?
- *Hint 1:* What kinds of state exist in the microVM? (Conversation history is one; the filesystem is another.)
- *Hint 2:* An agent tool that writes/reads a scratch file makes the filesystem claim directly testable with two prompts.
- *Hint 3:* A negative result ("B couldn't see it") is only meaningful if the positive control passes — first prove A *can* see its own state on a second invocation in-session.

**3. Read the execution role.** Find the IAM role your deployed agent runs as. What did the scaffold grant it? What's the *smallest* set of permissions the weather agent actually needs?
- *Hint 1:* `agentcore status` and the `--plan` output both leak the role's identity; so does the console's agent detail page.
- *Hint 2:* List what the agent actually touches: Bedrock model invocation, logs/traces emission... and? Anything else is candidate for removal.
- *Hint 3:* Don't tighten it yet — Week 5 does least-privilege with a denial receipt. This week you're building the "before" picture.

**4. Trace anatomy.** Pull one trace via `agentcore traces get` and one via the console. Find the tool-call span. Which fields would Week 6's execution-trace schema need to capture from it? Which fields are *missing* that you'd want (e.g., the model's stated reason for choosing the tool)?
- *Hint 1:* Look for the span attributes carrying tool name and arguments — note their exact field names; OTEL naming alignment is a Week 6 investment.
- *Hint 2:* Raw traces don't go in git. Where will your public-safe summary of this exercise live? ([Working assumptions](../../LEARNING_PLAN.md#working-assumptions).)

**5. Audit the teardown.** After `agentcore remove all` + deploy of the removal, verify the account is actually clean — without trusting the CLI's word for it.
- *Hint 1:* The `--plan` output from step 2 was the inventory. What does CloudFormation say about the stack now?
- *Hint 2:* Common stragglers across IaC tools: log groups, ECR images (container path), bootstrap artifacts. Which apply to a CodeZip deploy?

**6. Price one invocation.** From the pricing model (per-second CPU/memory per session) and your measured numbers, estimate the cost of one warm invocation and one full session. Show the arithmetic in the comparison doc.
- *Hint 1:* What's the session's billed lifetime relative to its last invocation — does idle time bill? Verify in the pricing docs rather than assuming.
- *Hint 2:* The point isn't the (tiny) number — it's knowing which knob dominates cost before Week 13 runs nightly invocation batteries.

## Gotchas & drift watch

- **Scaffold ≠ your repo layout.** `agentcore create` makes its own project directory; decide deliberately how it relates to this repo's target tree (`src/agents/`, `src/tools/`) rather than letting two source trees drift. Document the choice.
- **CDK bootstrap** is a one-time per-account/Region prerequisite; a first `deploy` failing with bootstrap errors is expected, not broken.
- **Two IAM hats:** *your* deployer credentials (need CDK/CloudFormation/IAM powers) vs the *agent's* execution role (needs Bedrock + logging). Errors name which principal was denied — read them carefully; fixing the wrong hat is the classic loop.
- **Env vars don't deploy.** `OWM_API_KEY` in your shell means nothing to Runtime. Configure it via the project's runtime environment settings for now; flag it in the comparison doc as the seam Identity/Secrets fills in Week 12. Never bake it into code or committed config.
- **Model access is per-Region and per-principal reality-check:** the deployed agent calling Bedrock in `us-east-1` under its execution role is a different auth path than your laptop; if `invoke` fails with access errors while local runs fine, start there.
- **Idle sessions may still bill** (memory-seconds while the microVM lingers to timeout) — verify current semantics on the pricing page and fold into Exercise 6.
- **Teardown after every deployed-lane session** (`agentcore remove all` + deploy). The plan's cost guardrails assume the habit; the budget alarm from Week 1 is the backstop, not the plan.
- **CLI drift:** command surface verified 2026-07-07 (`create`, `dev`, `deploy --plan`, `status`, `invoke`, `logs --since`, `traces list/get`, `remove`). When `agentcore --help` disagrees with this file, the binary wins; fix the doc.

## Deliverable checklist — AgentCore Deployment Proof

- [ ] Weather agent live on AgentCore Runtime, deployed via committed CLI/CDK config.
- [ ] `docs/local-vs-agentcore.md` comparison with measured (not vibes) latency numbers.
- [ ] Console screenshots: agent resource + execution trace with tool-call span visible.
- [ ] Session isolation demo transcript.
- [ ] Teardown/re-deploy runbook proving reproducibility.

## Success criteria

- [ ] `agentcore invoke` returns a tool-backed answer with the tool-call span visible in `agentcore traces`.
- [ ] Fresh-clone → deployed agent works following only your runbook.
- [ ] Account returns to zero deployed agent resources after teardown.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07.

- [Get started with the AgentCore CLI (Runtime path)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) — scaffold → dev → deploy → invoke, the exact workflow of build steps 1–2.
- [Use isolated sessions for agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html) — microVM lifecycle, ephemeral context, idle timeout, session headers; the source for build step 3's write-up and the "sessions are not users" caveat.
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) — where traces/logs land and how to view them; skim now, deep-dive in Week 14.
- [AgentCore FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/) — pricing model summaries per service; pair with the AgentCore pricing page for Exercise 6's arithmetic.

## Self-check

1. Two `invoke` calls arrive with the same session ID; two more with different session IDs. Describe exactly what each pair shares — compute, filesystem, conversation state.
2. Your deployed agent suddenly can't call Bedrock, but local runs fine. Name the two most likely principals/config points, in the order you'd check them.
3. What does `agentcore deploy --plan` show, and which later week's discipline does reviewing it rehearse?
4. Why does this plan use CodeZip rather than containers, and what would force the switch?
5. State the difference between Runtime session state and AgentCore Memory in one sentence each.
6. What, concretely, proves your teardown worked — name the checks beyond the CLI's exit code.
