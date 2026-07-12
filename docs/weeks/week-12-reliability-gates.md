# Week 12 — External Integration Reliability Gates

**Phase:** Complexity under contract (Weeks 11–13) · **Specimen:** the chain agent meets the real world
**Lanes touched:** agent build (real APIs), Identity (credential providers — primary), custom eval lane (resilience gates)
**Prerequisites:** Week 11 exit gate closed — chain gates green, cascade behavior proven on mocks.

[← Week 11](week-11-multi-tool-chains.md) · [Week index](README.md) · [Next: Week 13 →](week-13-ci-regression.md)

---

## Objective

Swap mocks for real external APIs and evaluate resilience: rate limits, timeouts, retries with backoff, circuit breakers, graceful degradation, and honest user communication during failures.

## Why this week exists

The difference between a demo agent and a production candidate is what happens during the bad five minutes. "Handles failures gracefully" becomes a measurable claim: inject real failure conditions, gate on the observed behavior, and only then un-stub the write action.

Note the sequencing logic baked into that sentence. The write action (`notify.send`) has been stubbed since Week 11 *by contract* — `sideEffects: write_external` requires reliability gates to exist first. This week builds those gates, proves the agent behaves during failure, and only then connects anything to the outside world's send button. Reliability isn't a polish pass after the feature; it's the *precondition* for the feature.

## Concepts

### Same contracts, real world — the payoff of Week 5

Swapping the mock registry for OpenWeatherMap, a real search API, and real HTTP fetch should change **nothing** about the contracts: same envelopes, same failure kinds, same schemas. That's the test of whether Week 5's contracts described the tools or merely the mocks. Where reality disagrees — an API returns a status you never mapped, a payload shape the contract didn't admit — the discrepancy is a contract bug to fix *with a version bump*, not a special case to bury in tool code.

Week 5 already made the 429 decision explicit: `upstream_4xx` is the normalized kind, while each occurrence carries `retryable`; 404 is false and 429 is true. Week 12 must now turn that qualifier into bounded attempts and backoff without changing the baseline user-facing degradation contract. Split out a `rate_limited` kind only if live behavior requires a different user-facing truthfulness/degradation contract, not merely because retry eligibility differs.

### Credentials become infrastructure

Keys leave your shell this week. Deployed, they live in **AgentCore Identity credential providers** backed by the token vault (verified 2026-07-07): API-key providers (with header/query-parameter placement config) and OAuth2 providers (vendor-preconfigured for common services, custom via discovery URL or explicit endpoints), with the vault handling storage and — for OAuth — refresh. Secrets Manager references cover anything the provider model doesn't. Never env-var-committed; local dev may still use env vars, and the split (local: env; deployed: Identity/Secrets) gets documented so nobody "simplifies" it later into a committed key.

The eval-relevant angle: a credential failure is now a *reachable production failure mode* (expired key, revoked grant) — exactly the `auth` kind your Week 2 audit forced into reachability. This week it stops being hypothetical.

### Resilience lives inside the tool boundary

The principle, from the plan: **agents reason; tools defend.** Retry loops, backoff, and breakers belong in tool code, not in prompts, for three reasons: prompts produce *probabilistic* retry behavior (the one thing a retry policy must not be), tool-layer resilience is unit-testable and trace-visible, and the model's context shouldn't fill with retry noise — it should receive either a success or a final, honest failure envelope. The components:

- **Retry policy, derived from the taxonomy:** only occurrences with `retryable: true` may retry (currently timeout, network, upstream 5xx, and 429); exponential backoff **with jitter** prevents deterministic clients from synchronizing into thundering herds; a **budget cap** composes with the contract's `latencyBudgetMs` — attempts plus backoff spend the same total budget the contract promised. Policy is *config data* per tool, not constants in code: Week 8's gates read the decision from traces, so a hard-coded invisible retry is as bad as none.
- **Circuit breaker:** closed → open after N consecutive upstream failures → half-open probe → closed on success. Breakers exist to fail *fast* during a real outage (no user waits through five retry cycles), to stop hammering a struggling upstream, and to make recovery observable (the half-open probe). Two requirements beyond the textbook: **state transitions must be trace-visible** (Week 8's gates and Week 14's dashboard both read them), and you must decide breaker *scope* — per-tool per-process is simple; but on Runtime, each session is its own microVM, so a "global" breaker doesn't exist without external state. Per-session breakers are an honest, documented limitation at this scale.
- **Degradation responses:** when defense fails, the tool's final envelope powers an agent response that says **what failed, what's stale, and what still worked**. The taxonomy's required behaviors (Week 5) are the spec; the calibrated judge (Week 10) scores the wording against a rubric you pre-stated.

### Evaluating resilience: inject, observe, gate

A failure-injection proxy (or a fault-flag on the tool wrapper) drives scripted scenarios — burst 429s, hard timeouts, a 30-minute outage simulation. The wrapper-flag approach is deterministic and CI-friendly; a proxy is more realistic (real sockets, real timeouts) but heavier — you likely want the flag for gates and the proxy for the live demo. New gates, each mapped to a resilience component:

- **Retry compliance** — observed attempt counts and inter-attempt delays in traces match the *declared* policy exactly (counts, backoff shape, budget ceiling).
- **Breaker transitions** — the scripted failure sequence produces exactly the expected state path (closed→open at attempt N, half-open probe at T, re-close on success).
- **Degradation-message quality** — judged lane, calibrated rubric, spot-checked by you (Week 10's trust policy names this use).
- **No fabricated data during outages** — deterministic: outage-window responses must not contain plausible-looking weather numbers. This is the repo's crispest honesty gate: during a total weather-API outage there is *no legitimate source* for "22°C", so its presence is fabrication, mechanically detectable.

### The write action, finally — with idempotency

Only after the gates above pass does `notify.send` un-stub, to a real sink **you own** (e.g., SNS → your email). Write actions get one more discipline: **idempotency** — the same logical request twice produces one send. That requires an idempotency key (derived from what? — Exercise 5) and a dedup point, and it's not optional garnish: this week's own retry layer is precisely the thing that would double-send without it. Your retry policy and your write tool must be provably safe *together*.

## Build steps

### 1. Wire real integrations behind the same contracts

OpenWeatherMap, a real search API, real HTTP fetch. Keys live in AgentCore Identity credential providers / Secrets Manager references when deployed — never env-var-committed. Contract discrepancies found during the swap are version-bumped fixes, not shims.

### 2. Build the resilience layer inside the tool boundary

Per-tool retry policy from the failure taxonomy (`retryable: true` occurrences only, exponential backoff + jitter, budget-capped), a small circuit breaker (closed → open on N consecutive upstream failures → half-open probe), and degradation responses that tell the user what failed, what's stale, and what still worked. Policies as config; transitions in traces; unit tests for the state machine.

### 3. Evaluate it

Failure-injection proxy or fault-flag drives scripted scenarios — burst 429s, hard timeouts, 30-minute outage simulation. Gates: retry compliance (counts/backoff observed in traces), breaker state transitions, degradation-message quality (judged lane, calibrated rubric), and no fabricated data during outages (deterministic).

### 4. Un-stub `notify.send` — with an idempotency check

Real sink you own, only after the gates pass; same request twice → one send, proven by test. The contract version bump (stub → real) is the visible artifact of the gate being satisfied.

### 5. Record the live demo

The agent answering during an induced outage, degrading honestly, recovering when the breaker half-opens. Short, scrubbed, committed to docs — this recording is Week 16's outage-insurance receipt.

## Exercises — guided discovery

**1. Derive the retry policy from artifacts you already have.** For each failure kind: retry or not, max attempts, backoff base, jitter, and the arithmetic showing the worst case fits `latencyBudgetMs`.
- *Hint 1:* Work the budget backward: 5000ms budget, first attempt takes up to 5s... wait. Does the *contract's* budget bound the attempt or the total? Your Week 5 reading of `latencyBudgetMs` decides — and may need a clarifying version note.
- *Hint 2:* Why jitter, in one sentence, and what trace evidence distinguishes jittered backoff from fixed?

**2. Prove the settled 429 behavior.** Implement and test 404 → no retry and 429 → bounded retry/backoff, while both retain the `upstream_4xx` baseline degradation contract after attempts end.
- *Hint 1:* Which trace assertions prove that retry eligibility differed without inventing two user-facing failure contracts?
- *Hint 2:* What observed user-facing truthfulness or degradation difference—not merely retry timing—would justify a future `rate_limited` kind, version bump, dataset update, and relabeling?

**3. Design the breaker as a testable state machine.** States, transition triggers, probe policy, scope (per-tool? per-endpoint? per-session?) — then the unit tests that walk every transition.
- *Hint 1:* What counts as "consecutive failures" — all kinds, or only kinds that indicate the *upstream* is sick? (Does a `bad_input` open the breaker? Should it?)
- *Hint 2:* On Runtime, where does breaker state live and die? Write the honest sentence about per-session scope into the tool's contract notes.

**4. Build the no-fabrication gate, then attack it.** Implement the outage-window numeric check, then construct the false positive and the false negative it's vulnerable to.
- *Hint 1:* False positive candidate: the agent legitimately says "earlier today it was 20°C" from in-session history. Is that fabrication? What does the gate need to know to decide — and is excluding it worth the complexity?
- *Hint 2:* False negative candidate: fabrication without digits ("mild and pleasant"). Does the deterministic gate catch it? Which lane does ("degradation-message quality" judge)? Write the division of labor down — it's Week 8's gates-vs-judges boundary, applied.

**5. Choose the idempotency key.** Same *logical* request twice → one send. Define "same logical request."
- *Hint 1:* Hash of recipient + payload? Then a genuinely repeated daily notification dedups wrongly. Include a time window? A request ID from upstream context? Each answer fails somewhere — pick the failure you can live with and document it.
- *Hint 2:* Where does dedup state live, and what's its TTL? (The microVM session question again — does your answer survive a session boundary, and does it need to?)

**6. Pre-state the degradation rubric.** Before running the judged gate: the criteria a degradation message must meet, as a scored rubric, with the pass bar declared.
- *Hint 1:* Your taxonomy's required behaviors are the skeleton; the rubric adds wording-quality criteria (names the failure, no blame-shifting, offers what still works, no fake precision).
- *Hint 2:* Week 10's trust policy governs this judge. What spot-check rate did you commit to, and where do disagreements route?

## Gotchas & drift watch

- **Real-API runs are a separate lane with separate baselines.** Latency, failure rates, and even tool-selection behavior (real payloads differ from fixtures) will not match the mocked lane. Per the plan's [architecture lanes](../../LEARNING_PLAN.md#architecture-lanes), scores do not transfer between lanes — report them side by side, never blended, and keep the mocked lane running in CI as the deterministic anchor.
- **Rate limits are a shared resource.** Your burst-429 scenario and your normal test runs draw from the same OWM quota; a careless afternoon locks you out of your own demo. Scenario scripts should track and budget real calls — and the 30-minute "outage" should be *simulated* at the injection seam, not induced by actually exhausting the quota.
- **Identity setup order matters.** Credential providers are account-level resources with quotas; create them once, reference them from tool config — don't scaffold per-experiment. Verify the current provider setup flow in the docs (CLI `agentcore add identity` vs console vs API) before wiring; this corner of the CLI was among the newer surfaces at verification time.
- **Breaker + retry interaction bugs are the classic ones.** Retries inside an open breaker (should be impossible), breaker counting retry attempts as separate failures (N=3 opens on one bad request), half-open probe racing concurrent calls. Your state-machine tests should cover all three explicitly.
- **The demo recording is a public artifact.** Scrub keys from any visible terminal, account IDs from consoles, and remember model output can echo inputs. Rehearse the outage before recording — breakers make timing-dependent theater.
- **Un-stubbing is one-way socially, even if not technically.** Once `notify.send` sends real email, every future harness run that exercises it *sends real email*. The mock registry still covers it in the mocked lane — confirm the harness's lane wiring before the first full-corpus run after un-stubbing, or your inbox becomes the report.

## Deliverable checklist — Production Integration Gates

- [ ] Real-API tools with Identity/Secrets-managed credentials and committed resilience configs.
- [ ] Circuit breaker + retry implementation with unit tests and trace-visible state.
- [ ] Failure-scenario eval suite with gates; report on all scenarios.
- [ ] Live outage demo recording/transcript + the un-stubbed, idempotent write action.

## Success criteria

- [ ] Zero fabricated tool data across all outage scenarios (gate, not aspiration).
- [ ] Retry/backoff behavior in traces matches the declared policy exactly.
- [ ] Degradation messages score ≥ your pre-stated rubric bar with the calibrated judge, spot-checked by you.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07, except where marked.

- [Configure credential providers (AgentCore Identity)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-providers.html) — API-key and OAuth2 providers, the token vault, vendor-preconfigured integrations; build step 1's credential path.
- [AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html) — the service overview: inbound vs outbound auth, workload identity.
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/) *(standard service docs)* — for references the provider model doesn't cover.
- Your Week 5 taxonomy (`docs/tool-contract-spec.md`) — **it is the spec** for this week's retry policies and degradation behaviors; where this week's reality fights it, the taxonomy gets a versioned amendment, not an exception.

## Self-check

1. Why do retries and breakers live in tool code rather than prompts? Give all three reasons and the eval consequence of each.
2. Walk the breaker's full state path during the 30-minute outage scenario: what opens it, what the user experiences while open, what the half-open probe does, and what trace evidence each phase leaves.
3. Explain why 404 and 429 share a normalized kind but differ in `retryable`, and state what observed user-facing difference would justify splitting out `rate_limited` with a version bump.
4. Why is "no fabricated data during outages" deterministically checkable when general hallucination isn't? What makes the outage window special?
5. Explain how the retry layer and the idempotent write action protect each other — and what specifically goes wrong if either exists without the other.
6. What claim does the live outage demo support that the gate report alone doesn't — and for which future audience?
