# Week 14 — Agent Execution Trace Instrumentation

**Phase:** Production & orchestration (Weeks 14–16) · **Specimen:** the deployed chain agent under continuous observation
**Lanes touched:** observability (primary), managed eval lane (online evaluations), platform (dashboard as IaC)
**Prerequisites:** Week 13 exit gate closed — CI lanes green, red-gate receipt preserved.

[← Week 13](week-13-ci-regression.md) · [Week index](README.md) · [Next: Week 15 →](week-15-multi-agent-safety.md)

---

## Objective

Production observability: normalized traces flowing to CloudWatch, an online evaluation config sampling live traffic, and a dashboard showing tool-selection patterns, timing, error rates, and satisfaction signals — with sensitive data kept out by design.

## Why this week exists

Weeks 6–13 built offline truth; production truth drifts. Online evaluation is the managed bridge — sampled live traces scored by the same evaluators you calibrated — and the previous plan's rule still binds: instrument provenance, never log payloads you wouldn't put on a billboard.

The drift argument deserves one more sentence, because it justifies the spend: your offline numbers describe the agent *on your dataset, under your pins*. Live traffic asks questions your dataset didn't anticipate, in phrasings you didn't test, at hours when upstreams degrade. Online evaluation samples that reality and scores it with judges whose agreement with humans you *measured* (Week 10) — which is the only reason a dashboard trend line deserves belief. Observability without calibrated evaluation is a mood ring; calibrated evaluation without live sampling is a lab result. This week joins them.

## Concepts

### Scrub at the emitter, or you've already lost

The design rule: **span attributes carry provenance, never payloads.** Concretely — toolId, args-*shape* hashes (the structure of the arguments, hashed, so you can detect drift without storing values), result kind, latencies, token counts, model/prompt/dataset versions. Not raw user text; not raw tool payloads; not secrets. Two reasons this must happen in the emitter (your instrumentation code) rather than downstream:

1. **Logs are write-once exposure.** Once a payload lands in CloudWatch, it's replicated into retention, queryable by anyone with log access, and potentially sampled into evaluation inputs. Filtering at the dashboard is cosmetic; the data already escaped.
2. **The billboard test must be checkable.** "We don't log sensitive data" is a claim; a **committed CloudWatch Logs Insights query that searches for a seeded sensitive test string and returns nothing** is a receipt. Build step 2 makes the claim mechanical — plant the canary in a test invocation, prove its absence downstream, commit the query and the empty result.

Tension to manage honestly: the managed evaluators *need* conversational content to judge (a judge can't score helpfulness from hashes). The resolution is scoping, not contradiction — the spans that feed evaluation carry what evaluation needs within your own account's boundary; what you *exclude* is secrets, credentials, and anything your working-assumptions rules bar from ever being emitted; and what you *publish* (dashboard screenshots, docs) is aggregates and provenance only. Know which layer each rule protects.

### The plumbing, verified (2026-07-08)

The enablement story has three moving parts, and your Week 6 investment gets its final grade here:

- **Strands emits OTEL natively** — spans for the agent lifecycle, model calls, tool executions, following GenAI semantic conventions. You instrumented and normalized these in Week 7.
- **AgentCore Observability** ingests spans into CloudWatch (one-time enablement; the CloudWatch GenAI observability console renders sessions/traces/spans). For agent-code telemetry, the documented path adds the **ADOT SDK** (`aws-opentelemetry-distro`) and runs the agent under `opentelemetry-instrument`; supported instrumentation libraries include OpenInference and OpenLLMetry.
- **Your Week 6 field alignment pays or it doesn't:** the success check is that spans in CloudWatch carry the shapes your adapters expect — same names, same nesting. Where they don't, you write the delta into the Week 6 mapping table and adjust; the goal is that the *managed* pipeline and *your* pipeline describe one world.

### Online evaluation: a metered faucet with a shape

Semantics verified against current docs: an **online evaluation config** names up to 10 evaluators (built-in and/or custom), a data source (the agent's CloudWatch log group + OTel service name), a **sampling percentage (0.01–100%)**, and a **session timeout** — how long after the last span AgentCore waits before treating a session as complete and scoring it. The service then runs on its own schedule: discovers completed sessions, samples per your rate, scores, and writes results to a dedicated evaluation-results log group — plus **CloudWatch metrics in EMF under the `Bedrock-AgentCore/Evaluations` namespace, keyed by evaluator name and config ID**, which is exactly what your dashboard and alarms consume. Evaluation runs under its own **execution IAM role** (distinct from the agent's runtime role — another least-privilege surface).

The plan's sketch (verify flags against `agentcore --help` — this surface is new):

```bash
agentcore add online-eval --name prod_quality \
  --runtime weather-chain-agent \
  --evaluator "Builtin.ToolSelectionAccuracy" "Builtin.ToolParameterAccuracy" "Builtin.GoalSuccessRate" \
  --sampling-rate <MINIMUM_USEFUL_RATE> \
  --enable-on-create
agentcore deploy
```

Discipline items: start at the **minimum sampling rate that produces signal** (Exercise 3 does the arithmetic — rate × traffic × tokens × judge pricing is your monthly bill); use **pause/resume** (first-class CLI commands) when you're not actively demoing — a portfolio project's traffic is bursty and the faucet doesn't need to run between sessions; and record config ID + evaluator IDs in the manifest, because the EMF metrics are keyed by them and renaming a config orphans your dashboard history.

### The dashboard answers questions; it doesn't display data

Design each widget as the answer to a question someone will actually ask:

| Question | Widget |
| --- | --- |
| Did tool selection get worse this week? | Online-eval selection-accuracy trend (the EMF metric), with the Week 13 threshold drawn on it |
| What is the agent actually doing? | Tool-call volume by toolId |
| Is an upstream hurting us? | Error rate by failure kind; breaker state changes |
| Are we slow, and where? | p50/p95 tool latency by toolId |
| How much is this costing? | Session counts, token counts |
| Are users okay? | The **satisfaction proxy** — e.g., no-retry follow-up rate — *labeled as a proxy, with its definition on the dashboard* |

That last row carries the plan's honesty rule: define the proxy honestly and document it as a proxy, not "user satisfaction." A metric named for what it measures ("sessions without a rephrase-and-retry within N turns") survives scrutiny; a metric named for what you wish it measured doesn't. Alarms: selection-accuracy drop and error-rate spike, thresholds traceable to the Week 13 memo (not round numbers), wired to email/SNS. Dashboard JSON lives in `infra/` — the dashboard is infrastructure, reviewed like it.

## Build steps

### 1. Enable AgentCore Observability end to end

One-click/CLI enablement; Strands emits OTEL natively — confirm exporter env/config against current docs (ADOT path for agent-code telemetry). Verify your Week 6 field-name alignment paid off: spans in CloudWatch carry the shapes your adapters expect; log the deltas in the mapping table.

### 2. Scrub at the emitter — and prove it

Span attributes carry toolId, args-shape hashes, result kind, latencies, token counts, model/prompt/dataset versions — not raw user text, not raw tool payloads, not secrets. Prove it with a CloudWatch Logs Insights query committed to docs (the "billboard test" receipt): seed a sensitive-looking test string through an invocation, query for it downstream, commit the query and its empty result.

### 3. Create the online evaluation config on the deployed agent

Evaluators from your calibrated set; sampling at the minimum useful rate (verify rate semantics and cost in current docs before enabling); session timeout matched to your agent's real session pattern; results landing in the dedicated log group as JSON, metrics in EMF.

### 4. Build the CloudWatch dashboard and alarms

The widget table above: tool-call volume by toolId, selection-accuracy trend (online eval scores over time), p50/p95 tool latency, error rate by failure kind, breaker-state changes, session counts, and the honestly-defined satisfaction proxy. Alarm on selection-accuracy drop and error-rate spike. Dashboard JSON in `infra/`, screenshot in docs, alarms wired to email/SNS.

## Exercises — guided discovery

**1. Write the span-attribute allowlist.** For every attribute your emitter sets: name, source, and the reason it's billboard-safe. Everything not on the list doesn't ship.
- *Hint 1:* The interesting entry is the args-shape hash. What exactly gets hashed — key names? types? values? — such that "same call shape" is detectable but "what city did the user ask about" is not recoverable?
- *Hint 2:* Cross-check the list against what the online evaluators need to function (they read the spans too). What's the minimal addition that satisfies the judge without widening exposure, and which boundary (account-internal vs published) does each field sit behind?

**2. Build the billboard-test query catalog.** Beyond the seeded canary: queries for email-shaped strings, key-shaped strings, and your account ID, across both the agent log group and the evaluation-results log group.
- *Hint 1:* Why must the *results* log group be queried too? Trace how a payload could arrive there without ever appearing in your emitter code.
- *Hint 2:* These queries are CI-shaped. What would it take to run them scheduled, alarming on nonzero results — and is that worth building this week or noting for later?

**3. Do the sampling arithmetic.** Your expected demo-week traffic × sampling rate × average session tokens × evaluation pricing = monthly cost. Find the minimum rate that still yields statistically meaningful weekly trend points.
- *Hint 1:* At toy traffic (tens of sessions/day), what rate gives ≥ n sessions/week per evaluator for a trend you'd defend? Sometimes the honest answer at portfolio scale is a high rate on low traffic, paused when idle — the opposite of production instincts.
- *Hint 2:* Which knob dominates the bill — rate, traffic, or session length? Check by moving each 10×.

**4. Tune the session timeout deliberately.** Pick the value and defend it against both failure modes.
- *Hint 1:* Too short: sessions scored mid-conversation (what does a goal-success judge say about half a conversation?). Too long: scores lag and idle sessions hold the queue. What does *your* invocation pattern (Week 3's session semantics) imply?
- *Hint 2:* How would you *detect* the too-short failure in the results log group? (What field would look systematically wrong?)

**5. Follow one request all the way.** One `agentcore invoke` → its span tree in the GenAI observability console → its session's online-eval score in the results log group → its point on the dashboard trend.
- *Hint 1:* What identifiers join each hop? (Session ID and trace ID — where does each appear in each system?) This walk is the success criterion; screenshot each hop, scrubbed.
- *Hint 2:* If the sampled score never appears, list the three most likely culprits in order (sampling missed it / session not yet "complete" / data-source config mismatch) and the check for each.

**6. Interrogate the proxy.** Write the satisfaction proxy's definition, its known confounds, and the sentence on the dashboard that keeps it honest.
- *Hint 1:* No-retry follow-up rate: what non-satisfaction causes a no-retry session (user gave up)? What satisfaction-compatible behavior looks like a retry (user asked a genuinely new question)?
- *Hint 2:* Name the decision this proxy is allowed to influence and the decision it isn't (e.g., "worth investigating" vs "agent is good"). Proxies earn narrow jobs.

**7. Audit the Strands Evals CloudWatch mapper.** For a small billboard-safe synthetic/test session set, retrieve the same AgentCore Runtime session through the repo's CloudWatch adapter and Strands Evals' `CloudWatchProvider`, then compare the mapped tool-call facts.
- *Hint 1:* Compare session/trace identity, observed tool name, arguments/result presence, status, and final response. Which differences are provider-query behavior, mapper behavior, or canonical repo extensions?
- *Hint 2:* The provider is a useful compatibility lens, not a replacement for `src/adapters/`. Promote a discovered difference into a synthetic regression fixture only if it changes a required canonical fact.
- *Hint 3:* Never commit either provider's raw output. The public receipt is the field-level comparison and package/source-profile versions.

## Gotchas & drift watch

- **The faucet runs while you sleep.** Online evaluation bills per sampled session continuously. Pause the config (`agentcore pause`) outside demo windows; the Week 3 teardown habit extends to evaluation configs. Budget alarm still standing guard from Week 1.
- **Metric identity is config identity.** EMF metrics key on evaluator name + config ID; deleting and recreating a config (vs pausing) breaks dashboard continuity. Name configs like you'll keep them.
- **Two IAM roles in play** — the agent's runtime role and the evaluation execution role. Permission errors during scoring implicate the latter; don't debug the former for an hour first (the Week 3 lesson, third appearance).
- **Log retention is a cost and an exposure window.** Set explicit retention on both the agent and results log groups — indefinite retention of even scrubbed telemetry is spend without purpose.
- **Console views drift fastest.** The GenAI observability console pages get reorganized more often than APIs; if a screenshot in this repo stops matching the console, trust the data (log groups, metrics), not the layout.
- **Verify the online-eval CLI flags before wiring** — `add online-eval` exists in the verified command list, but flag names in the plan's sketch (`--sampling-rate`, `--enable-on-create`) should be confirmed against `agentcore add online-eval --help`; the control-plane API (`OnlineEvaluationConfig`) is the fallback path with verified field semantics.
- **Remote provider convenience is another adapter boundary.** `CloudWatchProvider` queries Runtime log groups and maps records into a Strands `Session`; its output can drift with SDK/query changes. Compare it with the repo adapter on synthetic/test sessions, but keep canonical evidence and public-safety policy repo-owned.
- **Alarms need a destination that wakes you.** An alarm to an unmonitored email is decoration (Week 13's rule, applied to ops). Test-fire both alarms once — the test fire is itself a receipt for the docs.

## Deliverable checklist — Observability Dashboard

- [ ] End-to-end tracing: local dev and deployed agent both land normalized spans in CloudWatch.
- [ ] Billboard-test receipt: committed query + screenshot showing no sensitive payloads in logs.
- [ ] Online evaluation config live at a justified sampling rate, scores visible on the dashboard.
- [ ] Dashboard JSON in `infra/`, screenshot in docs, alarms wired to email/SNS.

## Success criteria

- [ ] A single trace is followable from `agentcore invoke` → CloudWatch span tree → online-eval score.
- [ ] Scrubbing verified by query, not by hope; one seeded "sensitive" test string provably absent downstream.
- [ ] Dashboard answers "did tool selection get worse this week?" in one glance.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-08, except where marked.

- [Add observability to AgentCore resources](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html) — enablement, the ADOT path (`aws-opentelemetry-distro` + `opentelemetry-instrument`), supported instrumentation libraries.
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) — the session/trace/span views and where each surface lives.
- [Create online evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-online-evaluations.html) — config fields: evaluators, data source, sampling, session timeout, execution role; the authoritative source for build step 3's flags and semantics.
- [Build custom code-based evaluators (AWS blog)](https://aws.amazon.com/blogs/machine-learning/build-custom-code-based-evaluators-in-amazon-bedrock-agentcore/) — the clearest end-to-end description of online-eval mechanics (discovery, sampling, EMF metrics, alarms) at verification time; also previews custom evaluators if your dashboard wants a deterministic metric scored online.
- [Strands Evals remote trace providers](https://strandsagents.com/docs/user-guide/evals-sdk/how-to/trace_providers/) — `CloudWatchProvider`, `CloudWatchSessionMapper`, and provider error boundaries used by Exercise 7's compatibility audit; pin and record the package version.
- CloudWatch Logs Insights query syntax *(standard CloudWatch docs)* — for the billboard-test catalog.

## Self-check

1. State the scrub-at-emitter rule and the two reasons downstream filtering doesn't substitute. What's the receipt that proves compliance?
2. Walk the online-evaluation pipeline from a live user session to a point on your dashboard: discovery, sampling, scoring, EMF, widget. Name the config fields that govern each hop.
3. Why does the selection-accuracy trend line deserve belief in this repo when the same line on a random team's dashboard wouldn't? (One word: which week?)
4. Your dashboard shows selection accuracy sliding 5 points over two weeks while your nightly lane 2 is green. Reconcile — what differs between what the two systems measure, and which do you investigate first?
5. Defend your satisfaction proxy's name and definition against "isn't this just user satisfaction?" — then against "isn't this meaningless?"
6. Which two IAM roles touch evaluation results, and what least-privilege statement applies to each?
