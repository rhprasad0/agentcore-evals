# Week 5 — Agent/Tool Contract Architecture

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** the three-tool portfolio, now under contract
**Lanes touched:** custom eval lane begins; safety & governance lane begins (manifests, IAM)
**Prerequisites:** Week 4 exit gate closed — three tools working through three seams, discovery ADR written.

[← Week 4](week-04-tool-integration.md) · [Week index](README.md) · [Next: Week 6 →](week-06-dataset-validation.md)

---

## Objective

Freeze the informal patterns of Weeks 2–4 into formal contracts: tool interface schemas, agent capability manifests, execution-context isolation, and an explicit failure taxonomy. No magic tool discovery.

## Why this week exists

This is the pivot week — the same move as the previous plan's "eval/product contract" week, now for tools. Everything downstream (dataset rows, validators, labels, judges, CI gates) keys off these contracts. A contract that only lives in code comments cannot fail a build.

That last sentence is the design principle for the whole week. Weeks 2–4 produced *conventions*: the failure envelope, the scoped docstring, the explicit tool list. Conventions decay — the next edit, the next tool, the next contributor erodes them silently. This week converts each convention into an **artifact a machine checks**: the envelope becomes an `outputSchema` that validation can fail; the tool list becomes a manifest the agent constructor enforces; "handle timeouts gracefully" becomes a taxonomy row a gate can assert against. From here on, breaking a convention means breaking a build — which is the only kind of convention that survives fifteen more weeks.

## Concepts

### What a contract is for (and what it isn't)

A tool contract is the **single source of truth about a tool's promised behavior**, versioned in git, referenced by everything else. Its consumers, concretely:

- Week 6's dataset rows reference `toolId`s and constrain arguments *against the contract's `inputSchema`*.
- Week 6's mocks satisfy the same contract, which is what makes "the agent can't tell" true.
- Week 8's gates check observed calls against contract fields (`failureModes`, expected envelopes).
- Week 9's labelers judge behavior *against the taxonomy's required behaviors*, not personal taste.
- Week 12's retry layer reads `failureModes` + `retryable` semantics; Week 15's Policy statements are generated from manifests.

What it is not: documentation prose, an aspiration, or a Swagger-style afterthought generated *from* code. Direction matters — **the contract is authored, and code conforms to it**, because the contract is where "what should this tool do" gets decided, reviewed, and versioned.

### Anatomy of `tool-contract.schema.json`

The shape every tool in this repo must satisfy:

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

Every field earns its place by having a downstream consumer — walk them:

- **`toolId`** — namespaced identity (`weather.` prefix). Dataset rows, traces, labels, manifests, and Policy statements all join on this key; a rename is a breaking change everywhere, which is the point.
- **`version`** — semver for behavior, not just code. Decide *this week* what bumps what (Exercise 2), and note the trap: **a description edit is a behavior change**, because the description steers selection. The previous weeks proved that empirically; the version field makes it administrative fact.
- **`description`** — the scoping sentence, stated with its negative space ("Not forecasts, not history"). This exact string should be what the model sees — contract and runtime description must not fork.
- **`inputSchema` / `outputSchema`** — JSON Schema for arguments and for *both* result shapes (success and failure envelope). The output schema is what lets Week 6's validators mechanically verify every mock fixture and every live result.
- **`failureModes`** — the closed set from Week 2, now normative: a tool returning a kind outside its list is itself a contract violation, distinct from the failure it was reporting.
- **`sideEffects`** — the three-level ladder (`none` / `read_external` / `write_external`) that powers the write-action gate: `write_external` tools stay stubbed until Week 12's reliability gates exist ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)). A tool's level is its *ceiling*, judged by what it *can* do, not what it usually does.
- **`authScope`** — names the credential surface the tool needs (`owm:read`). Week 12 maps these to Identity credential providers; until then it documents blast radius.
- **`latencyBudgetMs`** — the tool's total time promise. Note it's *total*: Week 2's `requests` timeout subtlety (connect vs read) means implementation must be checked against this number, not assumed from it. Week 8 gates on it; Week 12's retry budgets compose with it.

### Capability manifests: deny-by-default, enforced at construction

The manifest is the agent-level contract: **which `toolId`s this agent may use, its side-effect ceiling, and what it declares out of scope** ("this agent does not answer non-weather questions with tools"). Three design points:

1. **Enforcement lives in construction, not review.** The agent loads its manifest and refuses to start with a tool it doesn't grant — a loud startup failure, covered by a test. This turns Week 4's explicit-registration *decision* into a mechanism; nobody has to remember it.
2. **The ceiling composes.** An agent with ceiling `read_external` cannot register any `write_external` tool, no matter what its tool list says. Two fields cross-check each other — misconfigurations have to be consistent to sneak through, which is rare.
3. **Out-of-scope declarations are eval targets.** "Does not answer non-weather questions with tools" reads like prose, but it's testable: Week 6's no-tool rows and Week 8's `NoToolGate` operationalize it. Write declarations you can gate.

The quiet payoff arrives in Week 15: AgentCore **Policy** enforces agent–tool boundaries in infrastructure, outside agent code. If your manifests are clean data now, they become Policy statements nearly mechanically — the manifest is the same claim at a lower altitude.

### Isolation at two layers, each with a receipt

"Execution-context isolation" gets demonstrated twice because it's two different claims by two different enforcers:

- **Platform layer:** Runtime's per-session microVMs (Week 3's demo, now written up against the contract's language — what state a tool invocation may assume, what it may not).
- **Identity layer:** least-privilege IAM. The deployed agent's execution role can invoke exactly what its manifest implies — the weather Lambda and nothing else — and you *prove* it with a **denied call**, captured (scrubbed) as a receipt.

The denial receipt is a pattern worth internalizing beyond this week: a security boundary that has never rejected anything is indistinguishable from a boundary that doesn't work. Current AWS guidance (verified 2026-07-07) backs the posture: CLI-generated dev policies are explicitly "not suitable for production"; resources should be scoped to specific runtime ARNs; and the execution role should hold **equal or fewer privileges than the principals who can invoke it** — an escalation rule your write-up should quote and check against your own roles.

### The failure taxonomy: from kinds to required behaviors

Week 2 named the failure kinds; this week assigns each **exactly one required agent behavior** — retry or not, degrade how, tell the user what. Two disciplines make the taxonomy usable rather than decorative:

1. **Behaviors must be observable.** "Handles gracefully" cannot be gated. "Response acknowledges the failure, names what's unavailable, contains no fabricated weather values, and offers a next step" can — each clause is checkable against a trace (some deterministically, some by the Week 10 judge). Write every required behavior as assertions you could implement.
2. **One kind, one behavior.** If you're tempted to write "it depends" for a kind, the kind is too coarse — split it (that's a schema change with a version bump, done deliberately). The mapping's crispness is what makes Week 9's `errorRecovery: compliant / non-compliant` label a judgment a human can make consistently at row 60 of a labeling session.

This document becomes Week 6's validator spec (failure-injection rows assert the required behavior) and Week 12's retry-policy input (retryable kinds get the retry protocol; non-retryable go straight to degradation). You are writing three weeks' specs in one table.

## Build steps

### 1. Write `schemas/tool-contract.schema.json`

The JSON Schema that all contract *instances* must validate against (the block above is an instance, not the schema — writing the schema that admits it and rejects garbage is the exercise). Add fixtures both ways: `valid/` instances that must pass and `invalid/` instances that must fail, each invalid one broken in a single, named way (missing field, open-set failure mode, malformed version).

### 2. Write `schemas/capability-manifest.schema.json` and one manifest per agent

Which toolIds it may call, side-effect ceiling (`write_external` requires Week 12 gates), and out-of-scope declarations. Load and validate the manifest in agent construction — an agent literally cannot register a tool its manifest doesn't grant. Cover it with the loud-startup-failure test.

### 3. Demonstrate execution-context isolation at two layers

Re-run the Week 3 session demo, written up against the contract's vocabulary; then build the IAM proof — the deployed agent's execution role can call the weather Lambda and nothing else, demonstrated with a denied call, receipt scrubbed and committed.

### 4. Formalize the failure taxonomy

For each failure kind, the *required agent behavior* (retry? degrade? tell the user what, exactly?) with code examples, written as observable assertions. This document becomes Week 6's validator spec and Week 12's retry-policy input.

## Exercises — guided discovery

**1. Every field needs a victim.** For each field of the tool contract, name the specific downstream artifact (week + file) that breaks if the field is missing or wrong. If you can't name one, argue for deleting the field.
- *Hint 1:* Work backward from the consumers list in Concepts — then find the one field this file doesn't fully justify. Is `authScope` earning its place *this* week, or is it a promissory note? Decide what you think.

**2. Semver for tools.** Write the versioning policy: what bumps patch, minor, major — for code changes, schema changes, and description changes.
- *Hint 1:* Classify by blast radius: which changes can invalidate existing dataset rows? Which invalidate *labels*?
- *Hint 2:* A description edit changed selection behavior in Week 2's Exercise 5. Can a change that alters agent behavior ever be a patch?

**3. The loud failure.** Implement manifest enforcement and write the test that proves an un-manifested tool kills construction with an actionable error.
- *Hint 1:* Where in your agent-construction path do you already have both the manifest and the candidate tool list in hand?
- *Hint 2:* "Actionable" means the error names the tool, the manifest file, and the fix. Test the message, not just the raise.
- *Hint 3:* Don't forget the ceiling: a second test where the toolId is granted but its `sideEffects` exceeds the agent's ceiling.

**4. Engineer the denial.** Design the minimal execution role for the weather agent, then produce the denial receipt for an out-of-scope call.
- *Hint 1:* Inventory first (Week 3, Exercise 3): what does the agent legitimately touch? Bedrock invoke, logs/traces, the weather Lambda — what else, if anything?
- *Hint 2:* Pick the out-of-scope call to attempt: something adjacent and plausible (another Lambda, an S3 read). What makes a denial *legible* in the receipt — which fields of the error do you keep?
- *Hint 3:* Scrub before committing: role ARNs and account IDs out, action + resource *shape* + error code in.

**5. The taxonomy table.** Six kinds × required behavior, each behavior decomposed into observable assertions, each assertion tagged with how it will be checked (deterministic gate / judge / human-only).
- *Hint 1:* Start from what you *observed* in Week 2 Exercise 4 — where observed behavior was fine, canonize it; where it wasn't, the required behavior is the correction.
- *Hint 2:* The hardest column is "tell the user what, exactly?" — write the *criteria* for a good message, not a template message (templates rot; criteria gate).
- *Hint 3:* For `timeout` (retryable) vs `upstream_4xx` (not): do your two behaviors actually differ in a way a gate could distinguish? If not, why keep two kinds?

**6. Re-describe all three tools as contract instances.** Weather, calculator, web search — including the seam differences: what's the calculator's `latencyBudgetMs` rationale? What `sideEffects` level is web search? What does the Gateway seam do to `authScope`?
- *Hint 1:* Search reads the outside world — can `read_external` results be treated as trusted input? (Note the thought; Week 15's injection probes cash it.)
- *Hint 2:* If a field feels meaningless for the calculator (`authScope`?), that's evidence about your schema: optional field, or empty-string convention? Decide once, in the schema.

## Gotchas & drift watch

- **Pin the JSON Schema dialect.** Put `$schema` in your schemas and pin the validator library version; "valid" must mean the same thing in CI as on your machine. The JSON Schema spec's own site lists dialect differences — pick one (2020-12 is current) and stop thinking about it.
- **Contract/runtime forking.** The contract's `description` and the docstring the decorator ships to the model can silently diverge. Either generate one from the other or add a validator asserting equality — divergence here re-opens the exact hole contracts close.
- **Fixtures follow the billboard rule too.** Invalid fixtures tempt you toward realistic-looking ARNs and keys to test the safety scanner — use obviously-fake placeholders (`<AWS_ACCOUNT_ID>`, `INJECTION_CANARY_DO_NOT_FOLLOW` style) so the repo never contains a plausible secret even as a negative example.
- **Denial-receipt safety:** run the denial experiment against scratch resources, not by breaking your working deployment's role mid-session; IAM changes propagate with delay, which can make results look flaky — wait out propagation before concluding.
- **Don't schema-plate.** The temptation this week is a contract field for everything imaginable (rate limits! owners! runbooks!). Every field is maintenance forever; Exercise 1's rule — no consumer, no field — is the brake. You can always add fields with a version bump; removing them breaks consumers you forgot.
- **The CLI's dev IAM policies are explicitly not production-grade** (verified in current docs) — your least-privilege work deliberately diverges from what `agentcore` scaffolds. Expect friction; document where you tightened.

## Deliverable checklist — Tool Contract Specification

- [ ] `tool-contract.schema.json` + `capability-manifest.schema.json` with valid and invalid fixtures.
- [ ] All three tools re-described as contract instances; manifest-enforced registration in agent code.
- [ ] `docs/tool-contract-spec.md`: rationale, isolation demo (microVM + IAM denial receipt), failure taxonomy with required behaviors.
- [ ] `scripts/validate_dataset.py` seed: schema validation wired into a pre-commit/CI check.

## Success criteria

- [ ] An agent constructed with an un-manifested tool fails loudly at startup (test proves it).
- [ ] Invalid contract fixtures fail validation; valid ones pass — in CI.
- [ ] Every failure kind maps to exactly one required behavior, written down.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07, except where marked external.

- [JSON Schema specification](https://json-schema.org/specification) *(external)* — dialect selection, `$schema`, validation keywords; you need enough to author two schemas confidently, not the whole spec.
- [Security best practices for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html) — least privilege, ARN-scoped resources, the execution-role-privilege rule, condition keys; the standard your Exercise 4 role is held to.
- [IAM permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) — what the CLI's dev policies actually grant (read it to see what you're tightening *from*).
- [Use isolated sessions for agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html) — re-read for build step 3's platform-layer write-up.

## Self-check

1. Recite the contract's fields and, for each, its first downstream consumer by week.
2. Why must manifest enforcement fail at *construction* rather than at first tool call? Name the failure mode the difference prevents.
3. Your teammate "clarifies" a tool description in a PR with no version bump. Walk the harm chain if it merges — which artifacts silently desync?
4. What makes a required behavior *gateable*? Convert "handles auth errors gracefully" into three observable assertions.
5. State the IAM escalation rule about execution roles vs invoking principals, and explain the attack it forecloses.
6. Why is a denial receipt stronger evidence than a policy file showing the permission absent?
