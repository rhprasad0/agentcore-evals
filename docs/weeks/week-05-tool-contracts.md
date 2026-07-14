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
- Week 12's retry layer reads `failureModes` + `retryable` semantics; Week 15 uses manifests as reviewed inputs to Gateway Policy authoring and records what does not map.

What it is not: documentation prose, an aspiration, or a Swagger-style afterthought generated *from* code. Direction matters — **the contract is authored, and code conforms to it**, because the contract is where "what should this tool do" gets decided, reviewed, and versioned.

### The contract boundary: the registered, model-visible tool

A contract describes the normalized tool interface registered with the agent: the exact name, description, input schema, and result envelope the model can observe. Provider payloads, Lambda responses, Gateway transport envelopes, and MCP protocol messages are adapter inputs, not the contract output. Each seam must prove that its raw response normalizes into the same contract-valid result; raw provider equivalence is neither required nor claimed.

That boundary matters for semantic claims too. JSON Schema can require a `units` field and constrain its values; it cannot prove that a provider's Fahrenheit number was converted correctly merely because the envelope validates. Adapter tests own raw-to-normalized semantics, while contract validation owns the registered interface and envelope shape.

### Anatomy of `tool-contract.schema.json`

The shape every tool in this repo must satisfy:

```json
{
  "toolId": "weather.get_current_weather",
  "name": "get_current_weather",
  "version": "2.0.0",
  "description": "Current weather for a city. Not forecasts, not history.",
  "inputSchema": { "...": "JSON Schema for arguments" },
  "outputSchema": { "...": "success + failure envelope shapes" },
  "failureModes": ["bad_input", "auth", "upstream_4xx", "upstream_5xx", "timeout", "network"],
  "sideEffects": "none | read_external | write_external",
  "resultTrust": "trusted_structured | untrusted_external",
  "authScope": "owm:read",
  "latencyBudgetMs": 10000
}
```

Every field earns its place by having a downstream consumer — walk them:

- **`toolId`** — namespaced identity (`weather.` prefix). Dataset rows, traces, labels, manifests, and Policy statements all join on this key; a rename is a breaking change everywhere, which is the point.
- **`name`** — the exact final model-visible runtime name. It stays distinct from `toolId`: wrappers and Gateway transformations may change what the model calls without changing the stable identity used by datasets, manifests, and policy artifacts. Conformance compares this field after all decorators, adapters, and Gateway discovery transformations.
- **`version`** — semver for behavior, not just code. Consumers in this lab pin exact versions, not ranges. A patch changes implementation without changing the model-visible name, description, schemas, normalized behavior, failure semantics, or side-effect/trust declarations. A minor version is backward-compatible and additive: existing valid inputs, results, dataset rows, and labels remain valid. A major version changes model-visible description, required inputs/results, normalized failure behavior, side-effect ceiling, or anything else that can invalidate expectations or labels. **A description edit is major for the affected contract**, because description changes can change selection behavior. The schema's own version and a contract instance's version are separate identifiers.
- **`description`** — the contract-owned scoping sentence, stated with its negative space ("Not forecasts, not history"). Conformance compares it with the final registered model-visible spec, not merely a decorator or Gateway target configuration that may be transformed before the model sees it.
- **`inputSchema` / `outputSchema`** — JSON Schema for arguments the model may send and for the normalized success/failure result returned to the agent. The output schema does not describe raw provider, Lambda, Gateway, or MCP transport payloads; seam-specific adapter tests prove those become contract-valid normalized results. This boundary lets Week 6 validate mocks and live normalized results against the same promise.
- **`failureModes`** — the closed normalized set from Week 2, now normative: a tool returning a kind outside its list is itself a contract violation, distinct from the failure it was reporting. Layer details do not multiply this vocabulary; the failure envelope carries orthogonal diagnostics instead.
- **`sideEffects`** — the three-level ladder (`none` / `read_external` / `write_external`) that powers the write-action gate: `write_external` tools stay stubbed until Week 12's reliability gates exist ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)). A tool's level is its *ceiling*, judged by what it *can* do, not what it usually does.
- **`resultTrust`** — how returned content must be treated, independent of what invocation can change. Calculator and the dedicated normalized weather result are `trusted_structured`; Web Search is `untrusted_external` because fetched text is attacker-shaped input even though the call is only `read_external`. Week 6 adversarial rows, Week 11 fetched-content canaries, and Week 15 Gateway screening consume this marker; it does not claim Week 5 already implements Guardrails.
- **`authScope`** — names the credential surface the tool needs (`owm:read`). Week 12 maps these to Identity credential providers; until then it documents blast radius.
- **`latencyBudgetMs`** — elapsed time from adapter/tool invocation start until the normalized result or failure returns to the agent, including retries performed inside that invocation and excluding model-selection time. Week 2's `requests` timeout subtlety (connect vs read) means implementation must be measured against this boundary, not assumed from one timeout argument. Week 8 gates on it; Week 12's retry budgets compose with it.

For direct tools, contract/runtime conformance can compare the decorator-produced `tool_spec` directly. For Gateway-discovered tools, discovery happens before construction and the discovered model-visible spec is the object under test. The current inspection path is `registered_tool_specs()` in [`src/agents/weather.py`](../../src/agents/weather.py), and its tests already preserve the observed blank Gateway Web Search description. The default correction is to wrap a transformed tool with a contract-owned model-facing spec when Strands supports that cleanly. If wrapping cannot preserve invocation semantics, author a seam-specific contract version whose description and schema encode the actual discovered model-visible spec—including a blank or fallback description—and evaluate that weaker interface honestly. Final-spec conformance has no exception.

### Capability manifests: deny-by-default, enforced at construction

The manifest is the agent-level contract: **which `toolId`s this agent may use, its side-effect ceiling, and what it declares out of scope** ("this agent does not answer non-weather questions with tools"). Three design points:

1. **Enforcement lives in construction, not review.** The agent loads its manifest and refuses to start with a tool it doesn't grant — a loud startup failure, covered by a test. This turns Week 4's explicit-registration *decision* into a mechanism; nobody has to remember it.
2. **The ceiling composes.** An agent with ceiling `read_external` cannot register any `write_external` tool, no matter what its tool list says. Two fields cross-check each other — misconfigurations have to be consistent to sneak through, which is rare.
3. **Out-of-scope declarations are eval targets.** "Does not answer non-weather questions with tools" reads like prose, but it's testable: Week 6's no-tool rows and Week 8's `NoToolGate` operationalize it. Write declarations you can gate.

The manifest is an in-process registration boundary, not a process sandbox. It governs every tool object supplied to the agent constructor, including tools selected from a live MCP discovery result. It does not prevent arbitrary SDK calls, raw network access, filesystem access, shell execution, or an alternate runner that never invokes the validator. IAM limits AWS capabilities; AgentCore Policy governs only calls that transit an associated Gateway. A complete boundary story inventories every registration and execution path and names its enforcer.

Construction is fail-closed and ordered: load and schema-validate the manifest; construct direct candidates and discover Gateway/MCP candidates inside the active client session; select only explicitly approved discovered tools; extract each candidate's final model-visible spec; resolve each to exactly one (`toolId`, contract version); validate grant membership, side-effect ceiling, and spec conformance; reject unknown, duplicate, missing, or non-conforming tools; then pass only the validated list to `Agent(...)`. Session-bound MCP tools remain inside their client context, matching the real sequence in [`src/agents/weather.py`](../../src/agents/weather.py).

Matching an approved ID and schema does not prove implementation provenance. The manifest authorizes a model-visible capability; code review, dependency pinning, deployment provenance, IAM, and Gateway Policy address implementation replacement and out-of-band access. Do not claim the manifest detects malicious code that preserves the same interface.

The quiet payoff arrives in Week 15: AgentCore **Policy** enforces Gateway-transiting agent–tool boundaries outside agent code. Clean manifest data gives policy authoring a reviewed input, but compilation is not automatic: tool grants may map cleanly while side-effect ceilings, direct tools, and in-process MCP paths remain outside or require other controls. Week 15 records that residue instead of calling the layers equivalent.

### Isolation at two layers, each with a receipt

"Execution-context isolation" gets demonstrated twice because it's two different claims by two different enforcers:

- **Platform layer:** Runtime's per-session microVMs (Week 3's demo, now written up against the contract's language — what state a tool invocation may assume, what it may not).
- **Identity layer:** least-privilege IAM. The tightened execution role preserves the enumerated AWS actions required by the deployed path and denies selected adjacent, plausible out-of-scope actions. Green and red probes provide evidence for those tested actions under the deployed Runtime role; they do not prove the absence of every possible permission path. The current direct OpenWeather HTTPS call itself uses no AWS IAM permission, while model invocation and telemetry do.

The denial receipt is a pattern worth internalizing beyond this week: a security boundary that has never rejected anything is indistinguishable from one that doesn't work. Run probes as the actual scratch/deployed Runtime execution role, not the operator identity, but convert the observation into a synthetic public receipt. Keep only the probe name, tested principal class, action, synthetic resource shape, expected decision, observed allow/deny or error class, and a bounded interpretation. Account IDs, ARNs, role/session names, request IDs, raw policies, raw CloudTrail/log events, prompts, and arguments stay private. One denial proves only that action/resource/context. Current AWS guidance (verified 2026-07-07) backs the posture: CLI-generated dev policies are explicitly "not suitable for production"; resources should be scoped to specific runtime ARNs; and the execution role should hold **equal or fewer privileges than the principals who can invoke it** — an escalation rule your write-up should quote and check against your own roles.

### The failure taxonomy: from kinds to required behaviors

Week 2 named the failure kinds; this week gives each normalized kind one baseline degradation contract while keeping retry eligibility and diagnostics explicit. A failure envelope requires `kind`, `retryable`, and a public-safe `message`; it may add a bounded `source` (`input`, `provider`, `transport`, `gateway`, or `tool`) and scrubbed `providerCode`. The optional fields support diagnosis and later policy mapping without creating new top-level label classes. Two disciplines make the taxonomy usable rather than decorative:

1. **Behaviors must be observable.** "Handles gracefully" cannot be gated. "Response acknowledges the failure, names what's unavailable, contains no fabricated weather values, and offers a next step" can — each clause is checkable against a trace (some deterministically, some by the Week 10 judge). Write every required behavior as assertions you could implement.
2. **One kind, one baseline degradation contract.** Retry behavior may additionally depend on the occurrence's explicit `retryable` value and, in Week 12, bounded attempt/idempotency policy. The existing weather tool demonstrates why: both 404 and 429 normalize to `upstream_4xx`, but only 429 is retryable. If two failures require different user-facing truthfulness or degradation behavior, split the kind with a version bump; if they differ only in diagnostics or retry eligibility, preserve the kind and use the orthogonal fields. This crisp baseline is what makes Week 9's `errorRecovery: compliant / non-compliant` label usable at row 60 of a labeling session.

This document becomes Week 6's validator spec (failure-injection rows assert the required behavior) and Week 12's retry-policy input (occurrences with `retryable: true` may enter the bounded retry protocol; `false` goes straight to degradation). You are writing three weeks' specs in one table.

## Build steps

### 1. Write `schemas/tool-contract.schema.json`

The JSON Schema that all contract *instances* must validate against (the block above is an instance, not the schema — writing the schema that admits it and rejects garbage is the exercise). Add fixtures both ways: `valid/` instances that must pass and `invalid/` instances that must fail, each invalid one broken in a single, named way (missing field, open-set failure mode, malformed version).

### 2. Write `schemas/capability-manifest.schema.json` and one manifest per agent

Which exact (`toolId`, contract version) pairs it may call, its own manifest ID/version, side-effect ceiling (`write_external` requires Week 12 gates), and out-of-scope declarations. Load and validate the manifest in the common agent-construction path — an agent using that path cannot register a tool its manifest doesn't grant. Cover direct and discovered tools with loud-startup-failure tests, and inventory alternate constructors as explicit bypass surfaces.

### 3. Demonstrate execution-context isolation at two layers

Re-run the Week 3 session demo, written up against the contract's vocabulary; then build the IAM proof — green probes preserve required model and telemetry behavior while red probes deny specific permissions removed from the Week 3 baseline, including an unapproved model/profile, configuration-bundle mutation, and removed CloudWatch read/admin actions. Capture each result privately under the real Runtime role, then commit only the synthetic receipt shape defined above.

### 4. Formalize the failure taxonomy

For each failure kind, write the baseline degradation behavior, retry qualifier, diagnostic source/code expectations, and what the agent must tell the user, all as observable assertions. This document becomes Week 6's validator spec and Week 12's retry-policy input. A future infrastructure-policy denial becomes a new kind only if observed traces prove `auth` cannot express its required user-facing behavior; changing the taxonomy requires a contract version bump.

## Exercises — guided discovery

**1. Every field needs a victim.** For each field of the tool contract, name the specific downstream artifact (week + file) that breaks if the field is missing or wrong. If you can't name one, argue for deleting the field.
- *Hint 1:* Work backward from the consumers list in Concepts — then find the one field this file doesn't fully justify. Is `authScope` earning its place *this* week, or is it a promissory note? Decide what you think.

**2. Semver for tools.** Apply the exact-version policy above to code, schema, behavior, and description changes. Consumers pin `toolId` + exact contract version and manifest ID + exact manifest version; hashes supplement rather than replace readable versions.
- *Hint 1:* Classify by blast radius: which changes can invalidate existing dataset rows? Which invalidate *labels*?
- *Hint 2:* A description edit changed selection behavior in Week 2's Exercise 5. Can a change that alters agent behavior ever be a patch?

**3. The loud failure.** Implement manifest enforcement and write the test that proves an un-manifested tool kills construction with an actionable error.
- *Hint 1:* Where in your agent-construction path do you already have both the manifest and the candidate tool list in hand?
- *Hint 2:* "Actionable" means the error names the tool, the manifest file, and the fix. Test the message, not just the raise.
- *Hint 3:* Don't forget the ceiling: a second test where the toolId is granted but its `sideEffects` exceeds the agent's ceiling.
- *Hint 4:* Cover an unmanifested direct `@tool`, an unmanifested discovered MCP tool, duplicate IDs, description/input-schema drift, and a known alternate `Agent(..., tools=...)` path that skips the validator. The last is an inventory test over this repo's constructors, not proof that Python makes bypass impossible.
- *Hint 5:* For Gateway metadata drift, try a contract-owned wrapper first. If the SDK cannot preserve invocation semantics cleanly, create a seam-specific contract version for the actual discovered spec. A blank description may be a weak contract, but it cannot be exempt from contract conformance.

**4. Engineer the denial.** Design the minimal execution role for the weather agent, then produce denial receipts for permissions removed from the Week 3 baseline.
- *Hint 1:* Inventory first (Week 3, Exercise 3): the deployed Runtime legitimately invokes its selected Bedrock model and emits logs/traces; the current weather request goes to OpenWeather over HTTPS and needs no AWS IAM action. Which scaffold permissions remain unsupported by observed behavior?
- *Hint 2:* Pick out-of-scope calls tied to permissions you actually removed from the Week 3 baseline. Pair red probes with the green weather/model/telemetry path rather than choosing a theatrical unrelated denial.
- *Hint 3:* Scrub before committing: keep the principal *class*, action, synthetic resource shape, decision/error class, and claim limit; remove every live identifier and raw event. Run the public-safety scan and Gitleaks over the receipt.

**5. The taxonomy table.** Six normalized kinds × baseline degradation behavior, with retry eligibility/attempt qualifiers, user-facing assertions, diagnostic source/code, and each assertion tagged with how it will be checked (deterministic gate / judge / human-only).
- *Hint 1:* Start from what you *observed* in Week 2 Exercise 4 — where observed behavior was fine, canonize it; where it wasn't, the required behavior is the correction.
- *Hint 2:* The hardest column is "tell the user what, exactly?" — write the *criteria* for a good message, not a template message (templates rot; criteria gate).
- *Hint 3:* Compare a retryable timeout, non-retryable 404, and retryable 429: which differences belong to baseline degradation, retry policy, and diagnostics? Can a gate distinguish each claim?
- *Hint 4:* Before splitting a kind, ask whether the difference changes user-facing degradation, only retry eligibility, or only diagnostics. The latter two belong in orthogonal fields.

**6. Re-describe all three tools as contract instances.** Weather, calculator, web search — including the seam differences: what's the calculator's `latencyBudgetMs` rationale? What `sideEffects` and `resultTrust` values apply to each? What does the Gateway seam do to `authScope`?
- *Hint 1:* Search reads the outside world — can `read_external` results be treated as trusted input? (Note the thought; Week 15's injection probes cash it.)
- *Hint 2:* If a field feels meaningless for the calculator (`authScope`?), that's evidence about your schema: optional field, or empty-string convention? Decide once, in the schema.

## Gotchas & drift watch

- **Pin the JSON Schema dialect.** Put `$schema` in your schemas and pin the validator library version; "valid" must mean the same thing in CI as on your machine. The JSON Schema spec's own site lists dialect differences — pick one (2020-12 is current) and stop thinking about it.
- **Contract/runtime forking.** The contract's `description` and the docstring the decorator ships to the model can silently diverge. Either generate one from the other or add a validator asserting equality — divergence here re-opens the exact hole contracts close.
- **Gateway metadata is measured, not assumed.** The managed Web Search seam has already produced a blank model-visible description. Prefer a wrapper that restores the intended contract-owned spec; otherwise version a seam-specific contract that records the actual discovered spec and its weaker selection surface. Target configuration is not evidence of what the model saw, and no seam bypasses final-spec conformance.
- **Registration enforcement has a scope.** Search for every `Agent(..., tools=...)`, direct `@tool`, and in-process MCP client. Route known constructors through the common validator or document and test the bypass. Manifest success is not evidence that arbitrary SDK/network calls are impossible.
- **Fixtures follow the billboard rule too.** Invalid fixtures tempt you toward realistic-looking ARNs and keys to test the safety scanner — use obviously-fake placeholders (`<AWS_ACCOUNT_ID>`, `INJECTION_CANARY_DO_NOT_FOLLOW` style) so the repo never contains a plausible secret even as a negative example.
- **Denial-receipt safety:** run the denial experiment against scratch resources, not by breaking your working deployment's role mid-session; IAM changes propagate with delay, which can make results look flaky — wait out propagation before concluding.
- **Don't schema-plate.** The temptation this week is a contract field for everything imaginable (rate limits! owners! runbooks!). Every field is maintenance forever; Exercise 1's rule — no consumer, no field — is the brake. You can always add fields with a version bump; removing them breaks consumers you forgot.
- **The CLI's dev IAM policies are explicitly not production-grade** (verified in current docs) — your least-privilege work deliberately diverges from what `agentcore` scaffolds. Expect friction; document where you tightened.

## Deliverable checklist — Tool Contract Specification

Canonical validation command: `uv run --locked python -m scripts.validate_contracts`. It checks both schemas against Draft 2020-12, exercises every valid and invalid fixture, validates all checked-in tool contracts and capability manifests, verifies artifact path identities, and resolves every exact manifest grant. [Contract validation CI](../../.github/workflows/contract-validation.yml) runs the same command on pushes and pull requests.

- [x] Offline lane: `tool-contract.schema.json` + `capability-manifest.schema.json`, valid/invalid fixtures, three exact-version contract instances, manifest loader/enforcement, model-visible conformance tests, taxonomy, and validation command.
- [x] Every registered direct or discovered tool resolves to one exact contract version and passes grant, ceiling, and final-spec checks before `Agent(...)`; known alternate constructors are inventoried.
- [x] `docs/tool-contract-spec.md`: rationale, contract boundary, enforcement-scope matrix, failure taxonomy, Runtime isolation write-up, and bounded IAM evidence. Matrix columns: surface; registration/execution path; contract/manifest enforcer; outer control; negative test; known bypass/claim limit.
- [x] Deployed lane: required model/tool/telemetry behavior remains green; selected removed permissions deny under the Runtime role; synthetic receipts pass public-safety scanning.
- [x] Schema/fixture validation is wired into CI without prematurely naming contract validation as dataset validation.

## Success criteria

- [x] Unmanifested direct and discovered tools, duplicate IDs, side-effect ceiling violations, and any mismatch with the applicable direct or seam-specific final spec fail before `Agent(...)` (tests prove it).
- [x] Invalid contract/manifest fixtures fail validation; valid ones pass — in CI.
- [x] Every failure kind has baseline degradation assertions plus explicit retry qualifiers and bounded diagnostics.
- [x] The shared dataset/run binding resolver joins exact contract and manifest versions; a version change creates a different identity component, mismatched grants fail rather than retarget, and Weeks 6–7 consume the boundary without automatic migration.
- [x] IAM claims name the tested actions and principal context, and committed receipts contain no live identifiers or raw events.

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
