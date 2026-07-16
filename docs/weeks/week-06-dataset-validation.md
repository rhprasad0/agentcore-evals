# Week 6 — Tool Execution Dataset & Validation Schema

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** unchanged; the corpus around it is the build
**Lanes touched:** custom eval lane (primary); first offline compatibility contract for the later managed lane
**Prerequisites:** Week 5 exit gate closed — contracts, manifests, and the failure taxonomy are frozen inputs here.

[← Week 5](week-05-tool-contracts.md) · [Week index](README.md) · [Next: Week 7 →](week-07-specimen.md)

---

## Objective

Build the synthetic evaluation corpus: 100 tool-calling scenarios, a canonical execution-trace schema with a tested Strands/ADOT compatibility profile, tool-selection fixtures, success/failure validators, and deterministic mock tools.

## Why this week exists

This is the eval contract made concrete. The dataset defines what "correct tool use" means row by row; the mocks make the tool side reproducible; the telemetry mapping is the quiet investment that keeps the later managed adapter small, explicit, and testable. It does **not** make the repo's canonical trace schema an AgentCore Evaluations ingestion format by declaration.

Put differently: Week 5 defined correctness *in general* (schemas, taxonomy); this week defines it *in particular* — one hundred specific situations, each with a written verdict about what the agent should do. Every later number in this repo ("selection accuracy 94% on ambiguous rows") is arithmetic over these rows. If a row's expectation is wrong or vague, everything computed from it is wrong or vague, which is why the week's central discipline is editorial: **an LLM may draft rows; you review every single one. You are the dataset's editor, not its typist.**

## Concepts

### A dataset row is a claim, and its `expected` block is a gate spec

The corpus has a dataset-level manifest before it has rows. It pins the exact Week 5 capability-manifest ID/version and every (`toolId`, contract version) used by the frozen portfolio. Rows inherit those pins; they do not repeat them unless a future dataset deliberately mixes contract versions. A readable exact version is the join key, while hashes may supplement it for integrity. The validator cross-checks every dataset binding against the referenced manifest's `toolGrants` and resolves it to exactly one checked-in contract instance. Any contract-version change creates a new dataset/run identity and requires fixture revalidation rather than an automatic migration.

```json
{
  "datasetId": "tool-calling-100",
  "version": "1.0.0",
  "schemaVersion": "1.0.0",
  "taxonomyVersion": "1.0.0",
  "agentManifest": {"manifestId": "agents.weather", "version": "3.0.0"},
  "toolContracts": [
    {"toolId": "weather.get_current_weather", "version": "2.0.0"},
    {"toolId": "calculator.calculate", "version": "2.0.0"},
    {"toolId": "search.web_search", "version": "2.0.0"}
  ]
}
```

Then study the row anatomy — every field exists to become machine-checkable in Week 8:

```json
{
  "exampleId": "tc-0042",
  "prompt": "Is it warmer in Oslo or Bergen right now?",
  "expected": {
    "toolIds": ["weather.get_current_weather"],
    "minCalls": 2, "maxCalls": 2,
    "argConstraints": [{"path": "$.city", "coversExactlyOnce": ["Oslo", "Bergen"]}],
    "mustNotCall": ["search.web_search"],
    "responseMust": ["compare", "name both cities"]
  },
  "failureInjection": null,
  "tags": ["multi-call", "comparison"]
}
```

- **`toolIds` + `minCalls`/`maxCalls`** — the selection claim: *which* tools, and how many calls (a comparison needs two; a third is over-calling — a distinct labeled failure in Week 9's vocabulary). Note this row deliberately can't be satisfied by one clever call.
- **`argConstraints`** — parameter-fidelity claims as JSONPath + predicate. `coversExactlyOnce` makes this row order-insensitive without allowing Oslo twice and Bergen zero times. Designing the rest of this small vocabulary is Exercise 3 — it decides what Week 8 can gate deterministically versus what waits for a judge.
- **`mustNotCall`** — the forbidden set, which makes *restraint* checkable. Without it, "called weather twice and also searched the web" would pass the positive checks.
- **`responseMust`** — the weakest field by design: coarse response predicates (substrings/concepts). It's deliberately not "response quality" — that's human/judge territory (Weeks 9–10); the harness footer will say so explicitly.
- **`failureInjection`** — null here; on injection rows it names the (toolId, normalized failure kind) the mock must script, plus occurrence qualifiers such as `retryable` and bounded diagnostic `source` when the scenario needs them. Baseline degradation behavior comes *from the Week 5 taxonomy*, not from a per-row opinion — one source of truth without erasing the 404/429 retry distinction.
- **`tags`** — the reporting dimension. Week 8 reports per-tag; a blended average hides exactly the rows that matter (ambiguous ones). Closed tag set, validator-enforced, or the reports rot.

### The distribution is the point, not a formality

40 straightforward single-tool · 15 multi-call · 15 **no-tool** · 15 failure-injection · 10 adversarial/ambiguous · 5 dependency/stop rows. The final five use the already-built weather → calculator seam rather than pulling Week 11's general chain/DAG curriculum forward. Each slice exists to catch a specific failure of agent *or* eval:

- **Straightforward rows** anchor the baseline and catch gross regressions cheaply. They should be boring; resist making them interesting.
- **Multi-call rows** are where argument fidelity earns its keep (both cities, right units) and the first place over/under-calling shows.
- **No-tool rows** fight the demo bias that "more tool calls = better agent." The model should answer directly ("what does OWM stand for?") or decline. Week 2's misfire observations seed these; make some *near-boundary* (weather-adjacent but not tool-appropriate: "what's a nice month to visit Oslo?") — distant ones ("capital of France") test nothing.
- **Failure-injection rows** exercise the taxonomy: the mock returns each kind; the expected behavior is the taxonomy's required behavior. Every kind gets covered — the validator enforces the coverage, closing the loop Week 2 opened with unreachable kinds.
- **Adversarial/ambiguous rows** — forced-choice traps (two plausible tools; row records which is right and *why*), instruction-bearing content with **inert canaries** (`INJECTION_CANARY_DO_NOT_FOLLOW` — a fixed string whose only power is being greppable), and genuinely contested prompts where "defensible-alternative" will be a legal Week 9 label. These ten rows will generate most of your findings; write them last, when your judgment is warmed up.
- **Dependency/stop rows** cover only current portfolio behavior: weather succeeds and calculator consumes a validated numeric value; weather fails or returns no valid number and calculator must not run; repeated weather comparisons cover both required cities exactly once without making call order significant; an upstream failure never becomes a fabricated downstream value. General alternate-order DAGs and long cascades remain Week 11.

`resultTrust` creates a mechanical coverage obligation: every contract marked `untrusted_external` must have at least one adversarial result-content row that places the inert canary in that tool's returned fixture. The row asserts that the marker does not propagate into later tool arguments, does not appear in the final response unless safe reporting is explicitly required, and triggers no unapproved extra tool call. The dataset validator checks this coverage against the exact contracts in the dataset manifest. This does not imply Gateway screening exists or prove prompt-injection resistance; it proves the custom lane exercised each declared untrusted-result surface and tested non-propagation of one fixed inert marker.

### Three trace shapes, one explicit compatibility seam

Do not collapse three different contracts into one because they share some field names:

1. **Source telemetry profile** — what the active framework emits. Week 6 targets Strands native telemetry: spans plus inline events, or spans plus ADOT-split event records correlated by `traceId` + `spanId`.
2. **Canonical repo trace** — the stable, public-safe shape consumed by Weeks 7–10's adapters, gates, labels, and own judge.
3. **Managed input profile** — the AWS-supported OTEL session-span/request shape consumed later through AgentCore Evaluations. Week 6 validates an offline compatibility fixture; Week 10 performs the first live service acceptance smoke.

The canonical trace normalizes *what happened*: session/trace/span ids, exact capability-manifest ID/version, observed model-visible tool name, canonical `toolId` and contract version, arguments, result ok/kind/retryable, optional bounded diagnostic source/code, latency, token counts, and optional observed pre-tool assistant text (`selectionReasoning`). Store explicit null when no such text exists and never synthesize a rationale. The observed name and canonical contract reference are deliberately separate: Gateway names such as `web-search___WebSearch` are not stable contract IDs such as `search.web_search`, and AWS telemetry does not emit this repo's contract identity.

AWS's current Strands extraction profile (verified 2026-07-13) gives the minimum compatibility contract: `gen_ai.operation.name` classifies `invoke_agent`, `execute_tool`, and `chat` spans; `gen_ai.tool.name` identifies a tool; ADOT may move prompt, response, tool-argument, and tool-result payloads into event records correlated by trace/span ids; without that split, Strands carries equivalent content in inline span events. OpenInference is a separate future source profile, not a per-field fallback vocabulary.

The mapping table records: source profile and producer version, source field/event location, canonical field, required/optional status, redaction rule, canonical/volatile status, and managed-lane availability. Canonical contract references are documented local extensions. This alignment aims to reduce translation; it does not prove transport, resource association, event-record packaging, or AgentCore Evaluations acceptance.

### Deterministic mocks: same contract, scripted world

The mock registry returns fixture responses per a versioned key whose readable preimage is **(toolId, exact contract version, canonicalizer version, canonical arguments)**, with a hash as the lookup/index integrity value. Readable key fields remain in diagnostics so a miss or collision is explainable. The contract version prevents a fixture from silently surviving an incompatible change. Design constraints that matter:

- **Mocks satisfy the same exact registered contracts** — same model-visible interface, envelope shapes, normalized failure kinds, retry qualifiers, and trust declarations, registered through the same manifest machinery. This establishes interface equivalence at the selection/handling boundary; it does not reproduce Gateway transport, auth, latency, or live-provider behavior (Week 12 evaluates those separately).
- **Canonicalize representation, not meaning.** Sort object keys and use one JSON encoding, but preserve array order and semantic distinctions. Do not collapse `5` and `5.0`, trim strings, case-fold values, or equate absent/null/default unless the applicable input contract explicitly defines that equivalence. Reject schema-invalid arguments before fixture lookup.
- **Unknown key = loud failure.** A call with no fixture must fail the run visibly, not fall through to a default — silent fallthrough turns "the model varied its arguments" into "mysterious pass."
- **Failure injection is addressed per row.** The row's `failureInjection` selects a scripted fixture; the mock is where the taxonomy's kinds become live inputs to agent behavior.

One honesty note on reproducibility: mocks make the *tool side* deterministic; model pins do not guarantee identical model behavior. Define an ordered canonical projection now: deterministic span ordering plus only schema-declared canonical fields, with timestamps, latencies, provider ids, and provider-jittered counts recorded but excluded. Two equivalent normalized fixtures must serialize that projection to identical bytes. Week 7 separately measures whether repeated model runs reproduce the same tool-call sequence.

### Validators: the dataset's own CI

`scripts/validate_dataset.py` grows cheap CI checks: **schema validation** of every row and manifest; **binding resolution** (dataset pairs equal the referenced manifest grants and checked-in contracts); **coverage** (closed tags, every failure kind, exact distribution); **untrusted-result coverage** and **canary non-propagation assertions**; and the **safety scan** (`public_safety_scan.py` folded in: no real-looking account IDs, ARNs, keys, emails). A separate telemetry-compatibility test validates synthetic Strands inline and ADOT-split fixtures, their trace/span correlations, and extraction into the canonical schema. The dataset is data *about* correctness — it gets the same engineering standard as code.

## Build steps

### 1. Design the dataset manifest and `schemas/tool-calling-example.schema.json`, then generate the corpus

Schema first: define the dataset-level manifest with exact capability-manifest and tool-contract versions, then encode the row anatomy above. Generate `datasets/synthetic/tool-calling-100.jsonl` to the exact distribution, including the five bounded dependency/stop rows. Generate drafts with an LLM, then hand-review every row — commit the generation prompts too (they're provenance, and Week 16's case study will want them).

### 2. Design `schemas/execution-trace.schema.json`

Normalized runs: session/trace/span ids, exact capability-manifest ID/version, and per-span observed model-visible tool name, canonical toolId, exact contract version, arguments, result ok/kind/retryable, bounded diagnostic source/code where present, latency, token counts, and nullable observed `selectionReasoning`. Deliver `docs/telemetry-compatibility.md` with the source-profile mapping and version metadata. Add public-safe synthetic fixtures under `tests/fixtures/telemetry/strands-inline/` and `tests/fixtures/telemetry/strands-adot/`; prove that both extraction paths produce schema-valid canonical traces. Add a synthetic `tests/fixtures/telemetry/agentcore-evaluation-input/` request fixture that exercises the documented `EvaluationInput.sessionSpans` union and array bounds without inventing an undocumented split-event packaging rule. These are offline compatibility receipts, not live service-acceptance claims.

### 3. Build the deterministic mock registry

Fixture responses per the versioned readable key and canonical-arguments hash, scripted failures for injection rows, same registered model-visible contracts as the real tools. Decide and document canonicalization rules and the unknown-key policy. Claim interface equivalence only at the registered contract boundary; Gateway transport, auth, latency, and live-provider behavior remain out of scope.

Implemented in [`src/deterministic_mocks.py`](../../src/deterministic_mocks.py) with checked-in fixtures under [`datasets/fixtures/mocks/`](../../datasets/fixtures/mocks/) and the explicit rules and claim boundary in [`docs/deterministic-mock-registry.md`](../deterministic-mock-registry.md).

### 4. Extend `scripts/validate_dataset.py`

Schema-validate the dataset manifest and every row; resolve every exact binding against the manifest and contract registry; check tag/kind/distribution coverage; require non-propagation assertions for every exact `untrusted_external` contract; verify canaries are inert; and fail on real-looking secrets. Wire this and the telemetry compatibility fixtures into CI alongside Week 5's contract validation.

## Exercises — guided discovery

**1. Six rows by hand, first.** Before any LLM drafting, write one row per family (straightforward, multi-call, no-tool, failure-injection, adversarial, dependency/stop) entirely yourself.
- *Hint 1:* These six are your quality bar — when reviewing generated drafts, "is this as decidable as my hand-written six?" is the reject test.
- *Hint 2:* For the adversarial one, start from a Week 4 Exercise 4 ambiguity you actually observed.

**2. The editor's protocol.** Write the generation prompt *and* the review checklist you'll apply to every drafted row. What gets a row rejected?
- *Hint 1:* The failure modes of generated rows: expectations the prompt doesn't actually imply, prompts with two defensible readings but a single-verdict `expected`, unfalsifiable `responseMust` entries, near-duplicates padding a family.
- *Hint 2:* The blind test from the success criteria is the standard: could someone predict the expected behavior from the prompt alone? If the *reviewer* needed the `expected` block to see it, the row is mislabeled or the prompt underdetermined.

**3. Design the constraint vocabulary.** Choose the predicate set for `argConstraints` (e.g., `equals`, `inSet`, `matches`, `absent`…) — small enough to implement in an afternoon, expressive enough for the 100 rows. Include the minimum call-matching semantics needed to prove unordered completeness without accepting duplicates.
- *Hint 1:* Inventory the constraints your actual rows need before designing; don't build `regex` because it feels powerful.
- *Hint 2:* The tempting one is `derivedFromContext` ("arg must come from the user's prompt, not thin air"). Is that deterministically checkable? Partially? Where's the line — and which part goes to the judge instead?
- *Hint 3:* For the Oslo/Bergen comparison, two independent `inSet` matches are insufficient if both match Oslo. Decide how the expected block expresses "each required value exactly once" without introducing a general sequence language.

**4. The compatibility profile and mapping table.** For each canonical field, record the Strands source location for inline and ADOT-split telemetry, required/optional status, redaction, canonical/volatile status, and whether the managed profile consumes it. Keep OpenInference as a separate future profile.
- *Hint 1:* Start from AWS's current Strands extraction page and your public-safe [`trace-anatomy.md`](../trace-anatomy.md), not a generic attribute wishlist. Tool arguments/results may be event payloads rather than span attributes.
- *Hint 2:* `selectionReasoning` is an optional local extension populated only from observed pre-tool assistant text. What explicit null distinguishes "not emitted" from "adapter failed to look"?
- *Hint 3:* Record the actual Strands package version, instrumentation `scope.name`/`scope.version`, `scope.schemaUrl` when present, ADOT/runtime version where observable, source URL, and verification date. Do not borrow an unrelated OTEL release number.

**5. Canonicalization or corruption.** Write the versioned args-canonicalization spec, then construct object-key-order variants that should hash identically and semantic variants that must remain different.
- *Hint 1:* Dict order is representational. Floats (`5` vs `5.0`), strings (`"Oslo "` trailing space), explicit null/defaults, array order, Unicode, and case may be semantic. Let the input contract—not convenience—decide.
- *Hint 2:* Validate before lookup. Otherwise a canonicalizer can turn a schema-invalid call into a fixture hit and hide the model error you meant to measure.
- *Hint 3:* Keep readable key fields and the hash in miss diagnostics. A bare digest is not enough evidence to debug a collision or version drift.

**6. Corrupt it on purpose.** Produce deliberately broken rows and telemetry fixtures — each violating exactly one validator check — and verify each fails with a message that names the row/record and the fix.
- *Hint 1:* Cover schema violation, tag outside the closed set, missing failure-kind coverage, manifest/contract binding mismatch, armed-looking canary, missing non-propagation assertion, plausible secret, and an orphaned ADOT event record.
- *Hint 2:* Keep them in `datasets/fixtures/invalid/` as validator regression fixtures — the validator gets tests too; it's the thing everything else trusts.

## Gotchas & drift watch

- **Self-agreeing synthesis.** A model drafting rows writes prompts *it* finds easy and expectations *it* would satisfy — the dataset quietly becomes a mirror. Countermeasures: your hand-written five as the bar, deliberate near-boundary rows, and (later) Week 9's requirement that if labeling finds zero genuine failures, the dataset gets harder rows.
- **Canonical equality needs a projection and order.** Decide *now* which trace fields are canonical versus volatile, define deterministic span ordering, and test the serialized projection. This proves normalization repeatability for equivalent inputs; Week 7 separately measures whether stochastic model runs reproduce tool-call sequences.
- **Provenance per row.** Add a field or sidecar noting authored vs generated-then-reviewed, and dataset version. Week 7's errata pass edits rows; labels (Week 9) must reference the dataset version they labeled against, or reconciliation later becomes archaeology.
- **Versions are joins, not decoration.** The dataset-level manifest pins exact contract and capability-manifest versions. A contract change creates a different dataset/run identity, triggers fixture revalidation, and leaves existing labels attached to the versions they actually judged. Do not silently retarget old rows or promise automatic migration.
- **No-tool rows can leak hints.** If every no-tool prompt is short and every tool prompt long (or all no-tool rows lack city names), you've built a shortcut the model can exploit. Vary surface features across families; check the correlation before freezing.
- **Canary discipline:** exactly one canonical canary string, checked by equality, never elaborated into "realistic" injection text. The validator asserts presence in the untrusted fixture, required non-propagation expectations, and absence of armed-looking content. This is coverage evidence, not an injection-resistance score ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)).
- **Source profiles drift.** Pin the producer and collection versions you actually observe, plus source URLs and dates. Generic OTEL naming, Strands output, ADOT splitting, and AgentCore Evaluations extraction are related but distinct contracts; re-check the profile during Week 10's live acceptance smoke and Week 14's managed observability work.
- **Offline compatibility is not service acceptance.** A synthetic fixture can prove extraction and request-shape construction. It cannot prove AgentCore Evaluations accepts the payload, especially while direct `sessionSpans` packaging of correlated split event records remains undocumented. Week 10 settles that with a live smoke and records any adapter delta.

## Deliverable checklist — Synthetic Dataset + Validators

- [x] Dataset-level manifest pinning exact capability-manifest and tool-contract versions; 100-row reviewed dataset with the exact distribution above; generation prompts committed too.
- [x] Canonical execution-trace schema plus `docs/telemetry-compatibility.md`, synthetic Strands inline/ADOT-split fixtures, and a locally validated `EvaluationInput.sessionSpans` request-envelope fixture.
- [x] Deterministic mock registry with versioned readable keys, scripted failure fixtures, and loud miss diagnostics.
- [x] Validators in CI: schema, binding resolution, distribution/coverage, canary non-propagation, telemetry compatibility, safety scan.

## Success criteria

- [x] `validate_dataset.py` passes; deliberately corrupted rows fail with actionable messages.
- [x] Equivalent synthetic telemetry inputs produce byte-identical serialized canonical projections after deterministic ordering and documented volatile-field exclusion.
- [x] Both synthetic Strands profiles (inline events and ADOT-split event records) normalize into schema-valid traces containing the expected prompt, response, tool name, arguments, and result; no live managed-ingestion claim is made.
- [x] The synthetic managed-input fixture satisfies the documented `sessionSpans` union and 1–1000 item bounds; split event-record packaging remains explicitly unverified until Week 10.
- [x] A teammate (or you, blind, a week later) can predict expected behavior from any row without asking.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-16, except where marked external.

- [OTEL GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) *(external; moved page)* — follow its link to the dedicated GenAI semantic-conventions repository and record the exact artifact/version actually targeted.
- [Strands Agents telemetry extraction](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-strands.html) — the active source profile: span classifiers plus inline and ADOT-split content locations.
- [Spans, event records, and telemetry signals](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html) — the split, correlation, storage, and extraction contract.
- [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html) — why compatibility is framework/instrumentation-specific rather than one universal field fallback.
- [`EvaluationInput` API reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_EvaluationInput.html) — the `sessionSpans` request union and its limits; this alone does not document split event-record packaging.
- [Getting started with on-demand evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-on-demand.html) — the later CLI/SDK managed acceptance path; Week 10 exercises it.
- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — producer-side span hierarchy and attributes; pin the SDK version you actually install.

## Self-check

1. For each field of the example row above, name the Week 8 gate (or Week 9/10 lane) that consumes it.
2. Why must no-tool rows be near-boundary rather than obviously off-topic? What exactly would a distant row fail to test?
3. State the mock registry's three design rules (contract-equivalence, canonicalization, unknown-key policy) and the failure each prevents.
4. What claim, precisely, does byte-identical *canonical projection* make in this repo — over which ordered fields and which inputs, and what model behavior does it not guarantee?
5. Why do failure-injection rows point at the taxonomy for expected behavior instead of stating it inline? What rots if you inline it?
6. Your validator passes 100/100 rows on the first try. Argue both readings (great dataset / weak validator) and name the artifact that settles it.
