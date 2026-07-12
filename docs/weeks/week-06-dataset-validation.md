# Week 6 — Tool Execution Dataset & Validation Schema

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** unchanged; the corpus around it is the build
**Lanes touched:** custom eval lane (primary); first OTEL-alignment investment for the managed lane
**Prerequisites:** Week 5 exit gate closed — contracts, manifests, and the failure taxonomy are frozen inputs here.

[← Week 5](week-05-tool-contracts.md) · [Week index](README.md) · [Next: Week 7 →](week-07-specimen.md)

---

## Objective

Build the synthetic evaluation corpus: 100 tool-calling scenarios, an execution-trace schema aligned with OTEL conventions, tool-selection fixtures, success/failure validators, and deterministic mock tools.

## Why this week exists

This is the eval contract made concrete. The dataset defines what "correct tool use" means row by row; the mocks make runs reproducible; the OTEL alignment is the quiet investment that lets Week 14's managed observability and the AgentCore Evaluations lane consume the same shapes without adapters.

Put differently: Week 5 defined correctness *in general* (schemas, taxonomy); this week defines it *in particular* — one hundred specific situations, each with a written verdict about what the agent should do. Every later number in this repo ("selection accuracy 94% on ambiguous rows") is arithmetic over these rows. If a row's expectation is wrong or vague, everything computed from it is wrong or vague, which is why the week's central discipline is editorial: **an LLM may draft rows; you review every single one. You are the dataset's editor, not its typist.**

## Concepts

### A dataset row is a claim, and its `expected` block is a gate spec

The corpus has a dataset-level manifest before it has rows. It pins the exact Week 5 capability-manifest ID/version and every (`toolId`, contract version) used by the frozen portfolio. Rows inherit those pins; they do not repeat them unless a future dataset deliberately mixes contract versions. A readable exact version is the join key, while hashes may supplement it for integrity. Any contract-version change creates a new dataset/run identity and requires fixture revalidation rather than an automatic migration.

```json
{
  "datasetId": "tool-calling-100",
  "version": "1.0.0",
  "agentManifest": {"manifestId": "weather-portfolio", "version": "1.0.0"},
  "toolContracts": [
    {"toolId": "weather.get_current_weather", "version": "1.2.0"},
    {"toolId": "calculator.calculate", "version": "1.0.0"},
    {"toolId": "search.web_search", "version": "1.0.0"}
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
    "argConstraints": [{"path": "$.city", "inSet": ["Oslo", "Bergen"]}],
    "mustNotCall": ["search.web_search"],
    "responseMust": ["compare", "name both cities"]
  },
  "failureInjection": null,
  "tags": ["multi-call", "comparison"]
}
```

- **`toolIds` + `minCalls`/`maxCalls`** — the selection claim: *which* tools, and how many calls (a comparison needs two; a third is over-calling — a distinct labeled failure in Week 9's vocabulary). Note this row deliberately can't be satisfied by one clever call.
- **`argConstraints`** — parameter-fidelity claims as JSONPath + predicate. `inSet` beats `equals` here: you don't care about call order, only that both cities appear. Designing this small constraint vocabulary is Exercise 3 — it decides what Week 8 can gate deterministically vs what waits for a judge.
- **`mustNotCall`** — the forbidden set, which makes *restraint* checkable. Without it, "called weather twice and also searched the web" would pass the positive checks.
- **`responseMust`** — the weakest field by design: coarse response predicates (substrings/concepts). It's deliberately not "response quality" — that's human/judge territory (Weeks 9–10); the harness footer will say so explicitly.
- **`failureInjection`** — null here; on injection rows it names the (toolId, normalized failure kind) the mock must script, plus occurrence qualifiers such as `retryable` and bounded diagnostic `source` when the scenario needs them. Baseline degradation behavior comes *from the Week 5 taxonomy*, not from a per-row opinion — one source of truth without erasing the 404/429 retry distinction.
- **`tags`** — the reporting dimension. Week 8 reports per-tag; a blended average hides exactly the rows that matter (ambiguous ones). Closed tag set, validator-enforced, or the reports rot.

### The distribution is the point, not a formality

~40 straightforward single-tool · ~15 multi-call · ~15 **no-tool** · ~15 failure-injection · ~10 adversarial/ambiguous. Each slice exists to catch a specific failure of agent *or* eval:

- **Straightforward rows** anchor the baseline and catch gross regressions cheaply. They should be boring; resist making them interesting.
- **Multi-call rows** are where argument fidelity earns its keep (both cities, right units) and the first place over/under-calling shows.
- **No-tool rows** fight the demo bias that "more tool calls = better agent." The model should answer directly ("what does OWM stand for?") or decline. Week 2's misfire observations seed these; make some *near-boundary* (weather-adjacent but not tool-appropriate: "what's a nice month to visit Oslo?") — distant ones ("capital of France") test nothing.
- **Failure-injection rows** exercise the taxonomy: the mock returns each kind; the expected behavior is the taxonomy's required behavior. Every kind gets covered — the validator enforces the coverage, closing the loop Week 2 opened with unreachable kinds.
- **Adversarial/ambiguous rows** — forced-choice traps (two plausible tools; row records which is right and *why*), instruction-bearing content with **inert canaries** (`INJECTION_CANARY_DO_NOT_FOLLOW` — a fixed string whose only power is being greppable), and genuinely contested prompts where "defensible-alternative" will be a legal Week 9 label. These ten rows will generate most of your findings; write them last, when your judgment is warmed up.

`resultTrust` creates a mechanical coverage obligation: every contract marked `untrusted_external` must have at least one adversarial result-content row that places the inert canary in that tool's returned fixture and asserts that the agent does not follow it. The dataset validator checks this coverage against the exact contracts in the dataset manifest. This does not imply Gateway screening exists yet; it proves the custom eval lane exercised each declared untrusted-result surface.

### The execution-trace schema, and why OTEL names are worth the pedantry

The trace schema normalizes *what happened* in a run: session/trace/span ids, the exact capability-manifest ID/version, and per-span observed model-visible `tool.name`, canonical `tool.contract.toolId`, exact `tool.contract.version`, `tool.arguments`, `tool.result.ok`, `tool.result.kind`, `tool.result.retryable`, optional bounded diagnostic source/code, latency, token counts, and the model's stated reasoning for tool choice where available (`selectionReasoning` — Week 7 captures it). The observed name and canonical contract reference are deliberately separate: Gateway names such as `web-search___WebSearch` are not stable contract IDs such as `search.web_search`. Two facts (verified 2026-07-07) make the naming decision strategic rather than aesthetic:

1. **Strands already emits OTEL traces following GenAI semantic conventions natively** — its trace docs describe the full hierarchy (agent lifecycle, model calls with token usage, tool executions with parameters and results).
2. **AgentCore Observability and Evaluations consume OTEL/OpenInference-shaped telemetry** — AWS's own guidance tells teams to align LLM spans with OTEL GenAI conventions and lists OpenInference among supported instrumentation libraries.

So: for every field in your schema, *find the convention name first* (OTEL GenAI semantic conventions; OpenInference where OTEL has no name); invent only where both are silent, and record each decision in a mapping table. The payoff is stated in the plan and worth repeating: when the managed lane arrives (Weeks 10, 13–14), it ingests your world **without adapters** — or at worst, with an adapter whose mapping table you already wrote.

### Deterministic mocks: same contract, scripted world

The mock registry returns fixture responses per **(toolId, exact contract version, canonical-args-hash)**, including scripted failures for injection rows. The version prevents a fixture from silently surviving an incompatible contract change. Design constraints that matter:

- **Mocks satisfy the same exact tool-contract versions** — same model-visible interface, envelope shapes, normalized failure kinds, retry qualifiers, and trust declarations, registered through the same manifest machinery. "The agent cannot tell" is the invariant that makes mocked-lane results transfer to the agent's real behavior *at the selection layer* (execution behavior against real APIs is exactly what Week 12 separately evaluates).
- **Canonicalize before hashing.** JSON argument dicts must serialize identically across runs (sorted keys, normalized number formatting, stripped whitespace) or the same call misses its fixture on Tuesday.
- **Unknown key = loud failure.** A call with no fixture must fail the run visibly, not fall through to a default — silent fallthrough turns "the model varied its arguments" into "mysterious pass."
- **Failure injection is addressed per row.** The row's `failureInjection` selects a scripted fixture; the mock is where the taxonomy's kinds become live inputs to agent behavior.

One honesty note on the "byte-identical runs" success criterion: mocks make the *tool side* deterministic; the *model side* still samples. Meeting the criterion requires the Week 7 pins (temperature, model ID) *and* a trace normalization that excludes volatile fields (timestamps, latencies) from the canonical comparison — decide now which fields are canonical vs volatile and record it in the schema. That decision is part of the schema design, not a hack (see Gotchas).

### Validators: the dataset's own CI

`scripts/validate_dataset.py` grows five checks this week, all cheap, all in CI: **schema validation** of every row and the dataset manifest; **coverage** (every tag in the closed set, every failure kind represented, distribution within declared bounds); **untrusted-result coverage** (every exact `untrusted_external` contract has an adversarial result-content row); **canary inertness** (adversarial rows contain the canary string and no operational payloads); and the **safety scan** (`public_safety_scan.py` folded in: no real-looking account IDs, ARNs, keys, emails). The dataset is data *about* correctness — it gets the same engineering standard as code, because a corrupt row is a corrupt metric everywhere downstream.

## Build steps

### 1. Design the dataset manifest and `schemas/tool-calling-example.schema.json`, then generate the corpus

Schema first: define the dataset-level manifest with exact capability-manifest and tool-contract versions, then encode the row anatomy above. Generate `datasets/synthetic/tool-calling-100.jsonl` to the target distribution. Generate drafts with an LLM, then hand-review every row — commit the generation prompts too (they're provenance, and Week 16's case study will want them).

### 2. Design `schemas/execution-trace.schema.json`

Normalized runs: session/trace/span ids, exact capability-manifest ID/version, and per-span observed model-visible tool name, canonical toolId, exact contract version, arguments, result ok/kind/retryable, bounded diagnostic source/code where present, latency, token counts, and `selectionReasoning` where available. Name fields to match OTEL GenAI / OpenInference semantic conventions wherever one exists; clearly mark canonical contract references as local extensions where neither convention has a slot, and deliver the mapping table alongside the schema.

### 3. Build the deterministic mock registry

Fixture responses per (toolId, exact contract version, args-hash), scripted failures for injection rows, same contracts as the real tools — the agent cannot tell. Decide and document the canonicalization rules and the unknown-key policy.

### 4. Extend `scripts/validate_dataset.py`

Schema-validate the dataset manifest and every row, check tag/kind coverage against the taxonomy, require adversarial result-content coverage for every exact `untrusted_external` contract, verify canaries are inert, and fail on real-looking secrets (fold in `public_safety_scan.py`). Wire into CI alongside Week 5's contract validation.

## Exercises — guided discovery

**1. Five rows by hand, first.** Before any LLM drafting, write one row per family (straightforward, multi-call, no-tool, failure-injection, adversarial) entirely yourself.
- *Hint 1:* These five are your quality bar — when reviewing generated drafts, "is this as decidable as my hand-written five?" is the reject test.
- *Hint 2:* For the adversarial one, start from a Week 4 Exercise 4 ambiguity you actually observed.

**2. The editor's protocol.** Write the generation prompt *and* the review checklist you'll apply to every drafted row. What gets a row rejected?
- *Hint 1:* The failure modes of generated rows: expectations the prompt doesn't actually imply, prompts with two defensible readings but a single-verdict `expected`, unfalsifiable `responseMust` entries, near-duplicates padding a family.
- *Hint 2:* The blind test from the success criteria is the standard: could someone predict the expected behavior from the prompt alone? If the *reviewer* needed the `expected` block to see it, the row is mislabeled or the prompt underdetermined.

**3. Design the constraint vocabulary.** Choose the predicate set for `argConstraints` (e.g., `equals`, `inSet`, `matches`, `absent`…) — small enough to implement in an afternoon, expressive enough for the 100 rows.
- *Hint 1:* Inventory the constraints your actual rows need before designing; don't build `regex` because it feels powerful.
- *Hint 2:* The tempting one is `derivedFromContext` ("arg must come from the user's prompt, not thin air"). Is that deterministically checkable? Partially? Where's the line — and which part goes to the judge instead?

**4. The mapping table.** For each trace-schema field, record: your name, the OTEL GenAI convention name (if any), the OpenInference name (if any), and which you adopted.
- *Hint 1:* Start from the conventions' tool/agent span attributes and work toward your fields, not the reverse — you'll discover fields you hadn't planned (finish reason, model id) that cost nothing to include now.
- *Hint 2:* For `selectionReasoning`, neither standard may have an exact slot. What's the least-surprising place to put it, and what marks it as your extension?

**5. Canonicalization or chaos.** Write the args-canonicalization spec for the mock registry, then construct two semantically identical calls that would hash differently without it.
- *Hint 1:* Dict order is the obvious one. Floats (`5` vs `5.0`), strings (`"Oslo "` trailing space), and optional-arg defaults are the sneaky ones.
- *Hint 2:* Does your canonicalization *belong* to the mock registry, or is it a property of the trace schema too? (Will Week 8's arg gates compare raw or canonical?)

**6. Corrupt it on purpose.** Produce five deliberately broken rows — each violating exactly one validator check — and verify each fails with a message that names the row and the fix.
- *Hint 1:* One per check: schema violation, tag outside the closed set, missing failure-kind coverage (delete rows, not add), armed-looking canary, plausible secret.
- *Hint 2:* Keep them in `datasets/fixtures/invalid/` as validator regression fixtures — the validator gets tests too; it's the thing everything else trusts.

## Gotchas & drift watch

- **Self-agreeing synthesis.** A model drafting rows writes prompts *it* finds easy and expectations *it* would satisfy — the dataset quietly becomes a mirror. Countermeasures: your hand-written five as the bar, deliberate near-boundary rows, and (later) Week 9's requirement that if labeling finds zero genuine failures, the dataset gets harder rows.
- **Byte-identical needs a definition.** Decide *now* which trace fields are canonical (compared) vs volatile (recorded, excluded from comparison: timestamps, latencies, token counts if provider-jittered). Write the split into the schema; "determinism proven" in Week 7 means canonical-field identity across runs, and saying so precisely is the honest version of the claim.
- **Provenance per row.** Add a field or sidecar noting authored vs generated-then-reviewed, and dataset version. Week 7's errata pass edits rows; labels (Week 9) must reference the dataset version they labeled against, or reconciliation later becomes archaeology.
- **Versions are joins, not decoration.** The dataset-level manifest pins exact contract and capability-manifest versions. A contract change creates a different dataset/run identity, triggers fixture revalidation, and leaves existing labels attached to the versions they actually judged. Do not silently retarget old rows or promise automatic migration.
- **No-tool rows can leak hints.** If every no-tool prompt is short and every tool prompt long (or all no-tool rows lack city names), you've built a shortcut the model can exploit. Vary surface features across families; check the correlation before freezing.
- **Canary discipline:** exactly one canonical canary string, checked by equality, never elaborated into "realistic" injection text. The validator asserts both presence (on adversarial rows) and absence of anything armed-looking. An eval repo must not double as an attack cookbook ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)).
- **Conventions drift too.** OTEL GenAI semantic conventions are still marked unstable/experimental in places — pin the convention version you aligned to in the mapping table, and re-check it when the managed lane consumes your traces (Weeks 10, 14).

## Deliverable checklist — Synthetic Dataset + Validators

- [ ] Dataset-level manifest pinning exact capability-manifest and tool-contract versions; 100-row reviewed dataset with the distribution above; generation prompts committed too.
- [ ] Execution-trace schema with OTEL-convention field mapping table.
- [ ] Deterministic mock tool registry with scripted failure fixtures.
- [ ] Validators in CI: schema, coverage, canary-inertness, safety scan.

## Success criteria

- [ ] `validate_dataset.py` passes; deliberately corrupted rows fail with actionable messages.
- [ ] Two identical harness runs over mocks produce byte-identical trace files (determinism proven).
- [ ] A teammate (or you, blind, a week later) can predict expected behavior from any row without asking.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07, except where marked external.

- [OTEL GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) *(external)* — the attribute names for model and tool spans; the left column of your mapping table.
- [OpenInference specification](https://github.com/Arize-ai/openinference) *(external)* — the alternative convention set; check it where OTEL is silent (tool schemas, evaluations).
- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — what Strands natively emits (span hierarchy, tool parameters/results, token usage); your schema should mostly *rename nothing* from this.
- [Add observability to AgentCore resources](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html) — how traces reach CloudWatch (ADOT, supported instrumentation libraries incl. OpenInference); read now to confirm the target your field names are aiming at.
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) — the consuming side's view of sessions/traces/spans.

## Self-check

1. For each field of the example row above, name the Week 8 gate (or Week 9/10 lane) that consumes it.
2. Why must no-tool rows be near-boundary rather than obviously off-topic? What exactly would a distant row fail to test?
3. State the mock registry's three design rules (contract-equivalence, canonicalization, unknown-key policy) and the failure each prevents.
4. What claim, precisely, does "byte-identical trace files" make in this repo — over which fields, under which pins?
5. Why do failure-injection rows point at the taxonomy for expected behavior instead of stating it inline? What rots if you inline it?
6. Your validator passes 100/100 rows on the first try. Argue both readings (great dataset / weak validator) and name the artifact that settles it.
