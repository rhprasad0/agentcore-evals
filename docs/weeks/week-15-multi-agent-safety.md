# Week 15 — Advanced Agent Patterns & Safety

**Phase:** Production & orchestration (Weeks 14–16) · **Specimen:** the chain, refactored into explicit multi-agent orchestration
**Lanes touched:** agent build (multi-agent), safety & governance (primary — Policy, Gateway guardrails), custom eval lane (coordination gates)
**Prerequisites:** Week 14 exit gate closed — observability live; you'll need the trace plumbing to see cross-agent behavior at all.

[← Week 14](week-14-observability.md) · [Week index](README.md) · [Next: Week 16 →](week-16-capstone.md)

---

## Objective

Multi-agent orchestration (Graph, Swarm, and the workflow tool), A2A communication, and safety boundaries enforced outside agent code (AgentCore Policy + Gateway-level guardrails) — with coordination accuracy and boundary violations measured, not asserted.

## Why this week exists

Multi-agent systems multiply the failure surface: handoffs lose context, swarms loop, and "the other agent said so" becomes a provenance hole. The eval-first stance extends naturally — coordination is just tool selection at a higher altitude, and safety controls the agent can't reason its way around beat safety instructions in prompts.

Both halves of that sentence structure the week. **Coordination as high-altitude tool selection** means your existing machinery transfers: "did the orchestrator delegate to the right agent" is the same question shape as "did the agent pick the right tool," so DAG gates, no-tool analogues (should it have delegated *at all*?), and state-fidelity checks (Week 11's sentinels) all generalize. **Safety outside agent code** means the enforcement point moves where the model can't argue with it: a Cedar policy at the gateway evaluates every tool request *before* it executes, deterministically, invisible to the agent's reasoning — which is categorically stronger than a system-prompt plea, because a manipulated agent can't negotiate with infrastructure it never sees.

## Concepts

### Three orchestration patterns, one comparison

Refactor the Week 11 chain into explicit orchestration and run **the same scenarios** through all three — the comparison, not any single pattern, is the deliverable:

- **Graph** (`GraphBuilder`): a deterministic DAG *you* design — research → review, edges fixed. The model decides *within* nodes; you decide the topology. Failure modes shift accordingly: wrong topology is your bug, not the model's.
- **Swarm**: agents hand off dynamically — the *model* chooses the structure at runtime. Maximum flexibility, maximum eval surface: handoff loops, ping-ponging, context loss between hops.
- **Workflow tool**: the fixed pipeline as a tool — appropriate when the sequence is genuinely constant and the model shouldn't be spending tokens deciding it.

The plan's sketch:

```python
from strands.multiagent import GraphBuilder
builder = GraphBuilder()
builder.add_node(research_agent, "research")
builder.add_node(review_agent, "review")
builder.add_edge("research", "review")
graph = builder.build()
```

Note where the model *chooses* structure vs where you impose it — that choice is itself eval-relevant: every decision you move from model to topology is a decision that can no longer be wrong at runtime (and no longer needs a gate), at the price of flexibility. The comparison report's punchline is a recommendation: *which pattern for which shape of task*, backed by coordination-accuracy numbers on identical scenarios — the kind of engineering judgment that separates "used a framework" from "understood the trade."

### A2A: agents as network peers, with a verified constraint

Strands wraps an agent as a network-addressable peer via `A2AServer` (from `strands.multiagent.a2a`), which publishes an **Agent Card** — the JSON self-description (identity, capabilities, endpoint URL) that clients discover before sending tasks. Consume it from another agent via the A2A client tooling (`A2AAgent`), and inspect the Card — it's the A2A analogue of a tool description, with the same trust question attached.

The constraint, verified in current docs (2026-07-08): **A2A agents work in Graph patterns but are not supported in Swarm** — Swarm's coordination relies on tool-based handoff capabilities the A2A protocol doesn't yet carry. This is the plan's "capability-check, don't assume" in action: the constraint is documented today, may lift later, and your write-up should date it. When deployed, note Runtime's A2A protocol contract and Gateway HTTP-passthrough as the managed fronting path.

### Coordination evals: your Week 11 toolkit, one level up

- **Handoff fidelity** — did agent B receive what agent A produced, *unmutated*? The Week 11 sentinel technique generalizes: plant fixture-unique values in A's output, gate on their intact arrival in B's input. Context lost or paraphrased-into-error at a handoff is the multi-agent version of hallucinated intermediate state.
- **Loop detection** — a span-count budget per session, gated. Swarms that ping-pong burn real tokens fast; the budget is both an eval gate and a cost circuit-breaker. Pick the budget from observed healthy runs, not intuition.
- **Delegation accuracy** — rows where the orchestrator *should not* delegate (answer directly, or decline) — the no-tool row analogue, guarding against the multi-agent demo bias that more handoffs look more impressive.
- **Cross-agent trace stitching** — one user request through three agents must be *one* trace, not three fragments. That requires trace-context propagation across agent boundaries (W3C trace context; verify what Strands' A2A client propagates vs what you must carry manually). Week 14's dashboard grows a cross-agent view; debugging multi-agent systems without stitching is timestamp archaeology.

### Policy: map the manifest into Gateway infrastructure

AgentCore Policy, verified against current docs (2026-07-08), works like this: you create a **policy engine**, author **deterministic policies in Cedar** (the open-source authorization language), and **attach the engine to a Gateway**. From then on, every tool request through that gateway is evaluated against the policies *before* tool access — deny-by-default once an engine is attached: if nothing permits a request, it's denied. The Week 5 manifest is a reviewed input, not source code that compiles losslessly. Gateway tool grants can map to Cedar `permit` statements; targeted `forbid` statements carve out refusals; conditions can key on **user identity and tool input parameters**. Side-effect ceilings, `resultTrust`, out-of-scope declarations, direct tools, and in-process MCP paths may remain residue for other controls.

Three operational facts worth their weight:

1. **Start in `LOG_ONLY` mode** — decisions log to CloudWatch without blocking; validate every rule behaves as intended, then switch to `ENFORCE`. (Verified best practice — and good science: observe, then intervene.)
2. **Natural-language authoring exists** — describe the rule in English, get candidate Cedar, validated against tool schemas with automated reasoning that flags overly-permissive/overly-restrictive/unsatisfiable policies. Use it as a drafting aid; *review the Cedar* — you version the policy, not the English.
3. **Policy governs the gateway path only.** A direct `@tool` in agent code never transits the gateway and is invisible to Policy. This has an architectural consequence: for the safety story to be complete, governed tools route through Gateway (the Week 4 seam decision pays off), while the in-code capability manifest (Week 5) remains the enforcement for everything in-process. Two layers, complementary scopes — your write-up should draw exactly this boundary.

### Guardrails at the gateway: probabilistic detection, deterministic enforcement

The division of labor, verified: **Bedrock Guardrails detect** (prompt injection, sensitive-information exposure — probabilistic, model-based screening of tool traffic), and when they flag, they **signal Policy, which enforces** — the deterministic allow/deny at the gateway layer, outside agent code, where the agent "cannot see or reason around" the check. Keep the epistemics straight in your evals: detection is probabilistic (don't build a deterministic CI gate on whether Guardrails fires — that's judge-shaped), but *enforcement given detection* is deterministic (the denial and its trace receipt are gateable facts).

Use Week 5's `resultTrust` mechanically: for every `untrusted_external` contract, record whether its result transits the screened Gateway path and which Guardrail/Policy control applies. An `untrusted_external` direct tool or in-process MCP result is explicitly outside Gateway screening until rerouted; its Week 6 adversarial result-content coverage remains evidence about behavior, not infrastructure enforcement.

### Attack your own boundaries — with inert ammunition

The adversarial probes extend Week 6's canary rows to the multi-agent, policy-enforced world: prompts that ask agents to exceed their manifests, exfiltrate context across a handoff, or chain into un-granted tools. Rules of engagement per [Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails): inert canaries only (`INJECTION_CANARY_DO_NOT_FOLLOW`), no operational payloads — the repo must not double as an attack cookbook. The deliverable isn't "the attack failed"; it's the **denial visible in traces** — policy decision logs plus the trace span showing the blocked call — for every probe. Violations blocked at the policy/gateway layer, with receipts, are the week's version of Week 5's IAM denial: a boundary that has demonstrably rejected something.

## Build steps

### 1. Refactor the chain into explicit orchestration and compare patterns

**Graph** (deterministic DAG via `GraphBuilder` — research → review chain), **Swarm** (dynamic handoffs between a researcher/summarizer/checker), and the **workflow tool** for the fixed pipeline — same scenarios through all three, coordination accuracy measured per pattern.

### 2. A2A: wrap, consume, inspect

Wrap one agent as an `A2AServer`, consume it from another via the A2A client tooling; inspect the Agent Card. Document the Graph-works / Swarm-unsupported constraint (dated). When deployed, note Runtime's A2A contract and Gateway HTTP-passthrough as the managed fronting path.

### 3. Extend evals to coordination

Handoff-fidelity gates (sentinels across boundaries), loop detection (span-count budget per session), delegation-accuracy rows (should the orchestrator have delegated at all?), and cross-agent trace stitching in the dashboard.

### 4. Build the safety lane outside the code

Build a mapping/residue table from each Week 5 manifest: Gateway tool grant → Cedar action/resource/condition; unmapped manifest fields → their actual enforcer; non-Gateway paths → manifest/IAM coverage or a routing change. Use that reviewed mapping to author a deny-by-default AgentCore Policy engine for Gateway-transiting tools, plus Bedrock Guardrails for screened `untrusted_external` Gateway results. Then attack the mapped boundaries with inert-canary adversarial rows. Violations blocked at the policy/gateway layer — with the denial visible in traces — are the deliverable; non-Gateway surfaces retain their separately named controls and claim limits.

## Exercises — guided discovery

**1. One task, three patterns, one table.** Run identical scenarios through Graph, Swarm, and workflow; report coordination accuracy, token cost, latency, and failure modes per pattern.
- *Hint 1:* Design scenarios that *discriminate*: one with a genuinely fixed sequence (workflow's home turf), one needing runtime judgment about routing (Swarm's pitch), one in between.
- *Hint 2:* The recommendation sentence has the form "for tasks shaped like X, use Y, because measured Z." If your numbers don't support such a sentence, which scenario is missing?

**2. Map the manifest to Cedar and record the residue.** Take one agent's Week 5 capability manifest and hand-translate only the Gateway-relevant grants and conditions; produce a table of mapped fields, unmapped fields, non-Gateway paths, and their actual enforcers.
- *Hint 1:* Which manifest fields map cleanly (Gateway toolIds → actions on the Gateway resource) and which don't (`sideEffects`, `resultTrust`, out-of-scope declarations, direct tools, in-process MCP)? The residue *defines* the multi-layer boundary.
- *Hint 2:* Feed your English version of one rule to the natural-language authoring path and diff its Cedar against yours. Who missed a case? (Check with the validator's automated reasoning — an unsatisfiable-condition finding on either version is a lesson.)

**3. Build the handoff-fidelity gate, then seed the bug.** Sentinel through the Graph; gate on intact arrival; then deliberately corrupt a handoff (truncate A's output in the edge plumbing) and confirm the gate catches it — that's a success criterion, not an option.
- *Hint 1:* Where can corruption plausibly enter — the edge serialization, a summarizing intermediary, a context-window truncation? Seed the realistic one.
- *Hint 2:* Distinguish *mutation* from *legitimate transformation*: if B is a summarizer, verbatim sentinel-passing is the wrong spec. What does fidelity mean per edge type? Write it per edge, like DAG legality lived per row.

**4. Set the loop budget from evidence.** Instrument span counts across healthy runs of each pattern; set per-pattern budgets; then construct the prompt that makes the Swarm ping-pong and confirm the budget gate fires.
- *Hint 1:* What makes two agents hand off endlessly? (Mutual "you're better suited for this" is the classic.) You're building the failure to prove the detector — keep the killed run's trace as the receipt.
- *Hint 2:* Is the budget a gate (eval verdict) or a runtime kill switch (cost protection)? Answer: it needs to be both — where does each live?

**5. Run the probe battery in both modes.** Adversarial rows against `LOG_ONLY` first, then `ENFORCE`.
- *Hint 1:* LOG_ONLY answers "would my policies have caught this?" *before* enforcement risk. What did the log-mode run catch that surprised you — and did any probe succeed that a policy should have stopped? Fix before flipping.
- *Hint 2:* The receipt per probe: the policy decision log entry + the trace showing the denied call + the agent's user-facing behavior after denial. That third element is new — what *should* an agent say when infrastructure blocks it? (Your Week 5 taxonomy has no kind for "forbidden by policy." Does it need one? Decide with a version bump.)

**6. Stitch one request across three agents.** Produce the single trace for a user request that transits orchestrator → researcher → reviewer, and put it on the Week 14 dashboard.
- *Hint 1:* What propagates trace context across the A2A hop — the SDK, or you? Verify empirically: same trace ID on both sides, or two traces?
- *Hint 2:* If stitching fails at a boundary, the fallback is a shared session attribute joined at query time — inferior but honest. Document which you achieved; "stitched natively vs joined manually" is a real architectural finding.

## Gotchas & drift watch

- **Policy's scope is the gateway, full stop.** Any tool reachable without transiting the governed gateway is ungoverned by Policy — audit the final architecture for bypass paths (direct `@tool`s, MCP servers consumed in-process) and either route them through Gateway or explicitly document them as manifest-only surfaces. An unnoticed bypass path turns the safety story into safety theater.
- **Swarm costs compound.** Dynamic handoffs mean unbounded model calls until something stops them — run Swarm experiments with the loop budget *and* a hard token ceiling from day one; the first runaway shouldn't be discovered on the bill.
- **A2A-in-Swarm is unsupported *today*** (verified 2026-07-08) — the docs are explicit, and the reason (tool-based handoffs the protocol can't express) tells you what to re-check in release notes later. Capability-check, don't assume — in both directions.
- **Cedar is code, but not compiled manifest code.** Version and test policies against the Gateway-generated Cedar schema; preserve the mapping/residue table that explains which manifest claims they implement and which remain under other controls. Keep `LOG_ONLY` runs as evidence that the ENFORCE flip was informed, not hopeful.
- **Guardrails add latency and cost per screened call** — screening tool traffic is inference. Note the per-call overhead in the comparison table; safety layers get costed like everything else here.
- **Denial receipts are public-safe by construction only if you make them so** — policy logs can embed principal identifiers and raw arguments. The committed receipts follow the Week 5 pattern: action + resource shape + decision, identifiers scrubbed.
- **Multi-agent traces strain the Week 6 schema.** Agent identity per span, handoff edges, task lifecycle states — check whether the schema needs another versioned extension (the Week 11 `parentSpanId` precedent) before the coordination gates try to read fields that aren't there.

## Deliverable checklist — Multi-Agent Orchestration

- [ ] Graph, Swarm, and workflow implementations of the same task with comparison notes.
- [ ] A2A server/client demo: Agent Card, task lifecycle transcript, Graph-not-Swarm constraint documented.
- [ ] Coordination eval suite: handoff fidelity, loop budgets, delegation accuracy — with numbers.
- [ ] Policy + Gateway-guardrail configs in repo; adversarial-probe report showing denials with trace receipts.

## Success criteria

- [ ] Coordination accuracy reported per pattern on identical scenarios (and a recommendation of which pattern for which shape of task).
- [ ] Zero adversarial probes achieve un-manifested tool access; every block has a trace receipt.
- [ ] A handoff-corruption bug seeded deliberately is caught by the fidelity gate.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-08, except where marked external.

- [Policy in Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) — policy engines, Cedar, gateway association, natural-language authoring, validation, example policies; the whole safety-lane spine.
- [Strands: Agent-to-Agent](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/) — `A2AServer`, `A2AAgent`, the Swarm-unsupported note, and Graph integration examples.
- [Strands: Graph](https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/) — `GraphBuilder`, edges, and the "Remote Agents with A2AAgent" section for mixing local and remote nodes.
- [Strands A2A server API reference](https://strandsagents.com/docs/api/python/strands.multiagent.a2a.server/) — AgentCard construction and URL overrides, for the Card-inspection exercise.
- [Policy + interceptors at the gateway (AWS blog)](https://aws.amazon.com/blogs/machine-learning/secure-ai-agents-with-policy-and-lambda-interceptors-in-amazon-bedrock-agentcore-gateway/) — the permit-baseline/forbid-carve-out pattern with working Cedar, and the LOG_ONLY→ENFORCE staging practice.
- [A2A protocol v1.0](https://a2a-protocol.org/latest/) *(external)* — Agent Cards, task lifecycle, message/artifact semantics; the protocol truth behind the SDK conveniences.
- [AgentCore FAQs — Policy × Guardrails](https://aws.amazon.com/bedrock/agentcore/faqs/) — the probabilistic-detection / deterministic-enforcement division in AWS's own words.

## Self-check

1. "Coordination is tool selection at a higher altitude" — cash this out: name the Week 6/8/11 artifact each coordination gate generalizes.
2. For each pattern (Graph, Swarm, workflow): who decides the structure, when, and what failure class that ownership creates or eliminates?
3. Why is a Cedar forbid at the gateway categorically stronger than "do not use the delete tool" in a system prompt? Name the threat model where the difference is decisive.
4. Draw the two-layer safety boundary: which surfaces does Policy govern, which does the in-code manifest govern, and what audit finds a gap between them?
5. Explain "probabilistic detection, deterministic enforcement" and its consequence for what you may and may not gate CI on.
6. Your Swarm run terminated at the span budget. List the three hypotheses (real loop / budget too tight / legitimate long task) and the trace evidence that separates them.
7. What does the A2A Agent Card have in common with an MCP tool description — and therefore, which Week 4 lesson applies to it unchanged?
