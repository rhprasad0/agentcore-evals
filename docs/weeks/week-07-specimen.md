# Week 7 — Minimal Tool-Calling Specimen

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** weather agent, weather tool only, everything pinned
**Lanes touched:** custom eval lane; local only — no cloud calls in the measurement path
**Prerequisites:** Week 6 exit gate closed — dataset, trace schema, mock registry, validators in CI.

[← Week 6](week-06-dataset-validation.md) · [Week index](README.md) · [Next: Week 8 →](week-08-local-harness.md)

---

## Objective

Reduce to a single-tool agent specimen with a pinned Strands telemetry profile, normalized execution traces, optional observed pre-tool assistant text, and stubbed externals with controlled responses.

## Why this week exists

Weeks 8–10 need an agent whose every run produces a complete normalized record against a controlled tool world. One tool means tool-*selection* questions reduce to "call it or not, with what args" — unambiguous for human labelers. The normalization is deterministic for equivalent telemetry inputs; the model may still vary across runs. Complexity returns in Week 11, under contract.

The move deserves a name: you are building a **scientific instrument**, and instruments get calibrated on the simplest system that exhibits the phenomenon. With three tools, a labeler must weigh "was search defensible here?"; with one, the label space collapses to decisions a human can make consistently at row 60 of a session — called when it shouldn't, didn't when it should, called with wrong args, mishandled a failure. Every piece of machinery (harness, labels, judges) gets debugged against this legible specimen *before* the Week 11 portfolio makes verdicts genuinely contestable. Shrinking the agent is not a retreat; it's how you make the next three weeks' findings attributable.

## Concepts

### Pinning, experiment identity, and execution identity

A measurement you can't reproduce is an anecdote. The specimen pins every input that influences behavior — **model ID, exact system-prompt bytes, tool set (one), exact (`toolId`, contract version) references, exact capability-manifest ID/version, final model-visible tool-description bytes, mock fixture version, dataset version, exact temperature and every supplied sampling control, SDK versions, and source profile** — and records them in a **run manifest**. Classify each field before designing the schema: a behavior *pin* fixed before execution, an environment *record* observed at execution, or an output.

The manifest has two identities with different jobs:

1. **`experimentId` identifies comparable behavior pins.** Derive it as SHA-256 over a canonical pin projection serialized as UTF-8 JSON with recursively sorted object keys, compact separators, Unicode preserved, and no environment records or outputs. Same `experimentId` means the declared behavioral inputs are comparable; a changed pin means a different experiment and baseline.
2. **`runId` identifies one execution.** Generate a UUID4 for each run, reject collisions within the run store, and record `executedAt` as an observed timestamp outside the `experimentId` projection. Repeated executions share an `experimentId` but have distinct `runId`s, so agreement rates never overwrite their provenance.

Both identities are downstream joins: human labels and judge verdicts attach to the exact `runId`, while comparisons group runs by `experimentId`. Managed-lane scores also record evaluator IDs and dates, per the plan's [managed-evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8). If a score can't name both the execution and its pin projection, it isn't evidence.

Subtle but important: hash the **exact UTF-8 model-visible bytes** after final agent/tool registration, including the system prompt and tool descriptions. Do not trim or normalize whitespace: it can change tokenization and behavior. Canonical JSON applies to the structured pin projection, not to the prompt bytes it references. Keep readable exact versions beside hashes so humans and artifacts can join without reverse-engineering digests.

A contract or capability-manifest version change produces a different `experimentId`. Revalidate the dataset and mock fixtures against the new exact versions; do not silently retarget old runs or migrate labels. Existing labels remain attached to the dataset, contract, experiment, and run versions they actually judged.

Week 7 therefore uses the source-derived `weather-only-62@1.0.0` projection rather than retargeting the reviewed Week 6 portfolio corpus. It preserves 62 source rows byte-for-byte under the narrowed `agents.weather@4.0.0` capability: every row whose required and failure-injection tools are weather-only, except `tc-0068` and `tc-0069`, whose response expectations explicitly name the absent calculator capability. The original 100-row corpus and `agents.weather@3.0.0` remain the portfolio baseline for later expansion.

### Instrumentation: capture the declared source profile, normalize once, test the adapter

The pipeline is capture → normalize → store:

- **Capture** with the exact Strands telemetry profile pinned in the run manifest. `strands-inline` and `strands-adot-split` are separate versioned source profiles, not two best-effort shapes under one name. Implement the profile the specimen actually emits; keep Week 6's pair as the cross-profile compatibility receipt. For local runs, an in-memory exporter is the friction-free option — the Strands evals SDK ships telemetry setup for exactly this pattern, which Week 8 will lean on directly.
- **Normalize** in `src/adapters/`: one declared Week 6 source profile in → `execution-trace.schema.json`-valid trace out. Inherit the exact [span-identification and correlation contract](../telemetry-compatibility.md#span-identification-and-correlation): join split records by `(traceId, spanId)`, require exactly one per supported span, reject duplicate/missing/orphan records, and order spans by `(startTimeUnixNano, endTimeUnixNano, spanId)`. Arguments/results are not assumed to be direct span attributes. Unit tests use the public-safe synthetic fixtures so SDK shape drift fails instead of silently corrupting normalized data.
- **Store** under `datasets/runs/<runId>/` — raw traces git-ignored, public-safe summaries committed. The billboard rule is at its most tempting to break here, because raw traces are so *useful*; the summary format you design this week is what makes the useful parts shareable.

Strands Evals also offers a convenience path: `@eval_task(TracedHandler())` clears the in-memory exporter per case, invokes a fresh agent, and maps finished spans into a Strands `Session`. Exercise it once as a **compatibility probe**, then compare it with the repo adapter on the same declared synthetic source profile. The convenience path does not replace the canonical trace, and a Strands `Session` is not a new storage contract. Any serialized Session receives the same treatment as a raw trace: private and git-ignored unless transformed into an explicitly reviewed synthetic fixture.

### `selectionReasoning`: optional observed text, not a causal explanation

For each `toolUse`, define `selectionReasoning` as the ordered concatenation of the contiguous assistant-text content blocks immediately preceding that block **within the same assistant message**. Stop at the previous non-text content block or message boundary. Never include system/user/tool-result content, cross-message prose, or text emitted after the call. For multiple calls in one assistant message, evaluate each call independently rather than copying one explanation onto every call. If the source profile cannot preserve block-level association, store null and record the limitation instead of guessing. Week 10's blind judge may use present text as evidence about stated justification; the decision remains judgeable from conversation state and available tools when it is absent.

Two honesty notes belong in the schema docs. First, **presence is provider-, prompt-, and telemetry-shape-dependent** — models often emit a tool call with no preceding prose; store explicit null, never an empty string or adapter-invented explanation, and measure the presence *rate* (Exercise 5). Second, **stated reasoning is evidence, not mechanism** — models can rationalize; the text tells you what the model *said*, not causally *why* it acted. The Week 3 trace did not expose a reliable rationale field, so failure to find observed pre-tool text is valid data rather than an adapter defect by default.

### The errata pass: fix the ruler before measuring people with it

Build step 4 has you hand-review ten traces end-to-end and fix dataset bugs *now*, with a changelog, before humans label against them. Before inspecting Stage A output, predeclare ten row IDs with a deterministic, family-stratified rule; record the IDs, selection rule, dataset version, and dataset checksum in the changelog, and do not replace rows after seeing failures. The discipline that makes this safe is a sharp line between two kinds of findings:

- **Dataset bugs** — the row's expectation is wrong or underdetermined (the prompt doesn't imply what `expected` claims). *Fix now*, changelog entry, dataset version bump. After Week 9, editing expectations means invalidating labels — this week is the last cheap window.
- **Agent bugs** — the expectation is right and the agent violates it. **Do not fix the agent.** Record it. The specimen is under measurement, not development; "fixing" it now would be tuning to the test set before the test exists. Agent failures found here are previews of Week 8–9 findings, and their persistence is what makes those findings real.

If you can't decide which kind a surprise is, that's usually a third finding: the *contract* is ambiguous (Week 5 artifact bug). Route it there.

Dataset or contract defects may be corrected through versioned errata. The measured agent's prompt, final tool description, model, and sampling pins stay frozen throughout review; changing one starts a new `experimentId`. The ten-row pass calibrates the instrument, not the agent, and does not pretend to be a new holdout split.

## Build steps

### 1. Configure the specimen

Weather agent, weather tool only (mock registry from Week 6 behind it), pinned model ID, exact system-prompt and final registered tool-description hashes, exact temperature, and every supplied provider sampling control (`top_p`, `top_k`, seed, stop controls, or explicit null/not-set where unsupported or omitted). Design the run-manifest schema first (Exercise 1), with `experimentId`, UUID4 `runId`, collision check, `executedAt`, readable exact bindings, SDK/source-profile versions, and valid/invalid fixtures.

The selected task model is the US geographic Amazon Nova Micro inference profile, `us.amazon.nova-micro-v1:0`. The exact profile ID is a behavior pin: changing to the in-region model ID or another model creates a new `experimentId` rather than retargeting existing runs.

The inherited mock registry is stateless after construction: outcomes are row-scoped exact fixtures and returned values are deep copies. Prove that mutating one returned result or changing call order cannot affect a later call or a newly constructed registry. Do not add seed/reset machinery unless the implementation introduces mutable or stochastic mock behavior.

### 2. Instrument and normalize

Use Strands hooks/callbacks + telemetry export to capture the loop; write the adapter (`src/adapters/`) that normalizes the one pinned Week 6 source profile into `execution-trace.schema.json`. Apply the inherited correlation/ordering rules, fail loudly on unknown shapes, and apply the block-local pre-tool-text rule or explicit null. Ship table-driven fixtures for text→call, call-only, text→call→text→call, adjacent call→call, and message-boundary separation, plus shuffled span/event input that must preserve the canonical projection.

Run one synthetic case through `@eval_task(TracedHandler())` as a bounded cross-check. Plant independently distinctive observed tool name, canonical tool ID/version, non-default argument, result status/failure kind, and trace/span or call correlation identity. Compare those facts with the repo-normalized trace, document representation-only fields, and add one mutation/drop/swap test per fact that fails with a field-specific message. This guards against a tautological comparator but remains adapter-compatibility evidence, not independent proof of Strands correctness or managed ingestion. Record the exact `strands-agents-evals` version and capture path in the run manifest.

### 3. Run the complete weather-only projection

Run all 62 rows in `weather-only-62@1.0.0` and store normalized traces under `datasets/runs/<runId>/` (git-ignored raw, committed public-safe summaries). Before accepting the projection, require both schema validation and semantic invariants: observed tool name resolves to one granted exact contract; canonical tool reference matches that resolution; arguments/results satisfy the exact contract schemas; sequences are unique/contiguous; parent/correlation references satisfy the pinned profile; and success/failure fields are internally consistent. Unknown mock fixtures and adapter errors are instrument errors, never agent verdicts.

### 4. Hand-review ten traces end-to-end

Apply the predeclared ten-row sample and annotate surprises. Mislabeled expectations get versioned errata before humans label; agent misbehavior gets recorded, not fixed. Do not change sample membership or behavior pins after inspecting results.

## Exercises — guided discovery

**1. Design the run-manifest schema.** Classify every field as behavior pin, environment record, or output. Derive `experimentId` only from the pin projection; give each execution its own collision-checked UUID4 `runId` and observed `executedAt`.
- *Hint 1:* Candidate pins: model ID, exact prompt/tool-description hashes, exact (`toolId`, contract version) references, capability-manifest ID/version, dataset/mock versions, exact sampling controls, SDK versions, and source profile. Which did you almost leave out?
- *Hint 2:* Hash exact final model-visible UTF-8 bytes. Why would trimming a whitespace-only docstring edit hide a potentially behavior-relevant change?
- *Hint 3:* Why keep readable versions when hashes detect changes? Which artifacts join on `runId`, and which comparisons group by `experimentId`?

**2. Adapter edge cases first.** Before writing the happy path, list the source-profile shapes that could break normalization, and write failing tests for them.
- *Hint 1:* Multiple tool calls in one assistant message; text→call→text→call; adjacent calls; message boundaries; a result with no call; a run ending mid-loop; and null pre-tool text.
- *Hint 2:* For split telemetry, shuffle span and event-record arrays and require the same projection; then independently test duplicate, missing, and orphan `(traceId, spanId)` pairs. Arrival order is not a second correlation rule.
- *Hint 3:* What should the adapter do with a shape it doesn't recognize — best-effort or refuse? Which failure mode does the Week 5 fail-loudly precedent require?

**3. Measure repeatability, then break it.** Run the dataset twice under one manifest; compare tool-call sequences and the Week 6 ordered canonical projections separately. Then change exactly one pin (temperature up, or one docstring word) and diff again.
- *Hint 1:* The Week 6 fixture test already proved normalization determinism for equivalent inputs. A same-manifest model rerun can still differ because of sampling. Separate model variation, mock-key misses, and adapter/projection bugs rather than calling all three nondeterminism.
- *Hint 2:* The one-pin experiment is Week 8's sensitivity check in miniature; save both run directories as its raw material.

**4. The errata protocol.** Before Stage A output exists, write the family-stratified selection rule and freeze ten row IDs, dataset version, and checksum. Then write the triage rule: what evidence classifies a surprise as dataset bug vs agent bug vs contract ambiguity?
- *Hint 1:* Test each surprise against the blind-prediction standard: given only the prompt and the contracts, what *should* happen? If reasonable readers disagree, which artifact failed?
- *Hint 2:* Changelog entry shape: row id, old → new expectation, why, dataset version bump. Where does the version live so Week 9's labels can cite it?

**5. Reasoning presence audit.** Across the 62-row projection run, measure: on what fraction of tool-call spans is `selectionReasoning` non-null? Does presence correlate with row family (ambiguous vs straightforward)?
- *Hint 1:* If presence is low, what could raise it — and is that intervention (prompting for explanations) *changing the specimen*? What does the manifest say about that?
- *Hint 2:* Whatever the rate is, write it in the run summary; Week 10's judge design must plan for the null case rather than discover it.

**6. Cross-check the native Evals mapping.** Run one public-safe synthetic case through `@eval_task(TracedHandler())`, inspect the resulting Strands `Session`, and compare it with the repo adapter's canonical trace for the same declared source profile.
- *Hint 1:* Plant distinct tool name, canonical reference, non-default argument, failure status, and correlation identity. The shapes may differ, but each fact must agree or have a documented repo-owned recovery rule.
- *Hint 2:* Mutate/drop/swap each fact independently and require a field-specific failure. An all-fields equality check that never proves each field participates is a tautology.
- *Hint 3:* `TracedHandler` manages exporter clearing per case, but cache/report identity still depends on unique case/session IDs. Where do `experimentId` and `runId` join those records?

## Gotchas & drift watch

- **Exact sampling pins ≠ deterministic generation.** Provider-side sampling, batching, and numerical nondeterminism can vary output even at the minimum temperature. Record every supported sampling control exactly and explicit null/not-set otherwise. Week 6 proves byte identity only for ordered canonical projections of equivalent telemetry inputs; this week measures model reruns separately.
- **Versions and hashes answer different questions.** Exact versions say which reviewed promises governed the run; exact-byte hashes detect model-visible drift; `experimentId` fingerprints their structured pin projection; `runId` identifies one execution. Do not collapse those jobs or normalize away prompt whitespace.
- **Schema-valid can still be semantically wrong.** A result attached to the wrong call can satisfy JSON Schema. Run the semantic invariant validator before counting a trace as instrument-valid; only then may agent gates consume it.
- **Hooks/telemetry APIs are the fastest-moving part of Strands.** Some hook and telemetry interfaces live in experimental namespaces; verify current names in the docs before wiring, and pin SDK versions in the manifest so an upgrade is a *decision*, not ambient drift.
- **Convenience mapping can become accidental architecture.** `TracedHandler` is useful plumbing, but custom gates still consume the repo's canonical trace through a tested adapter. If an SDK Session gains or loses a field, the compatibility test should fail before the evidence model changes.
- **Keep committed source fixtures synthetic.** The adapter's test fixtures preserve raw Strands-shaped structure, but their values are authored placeholders—not captured Runtime payloads. Run the safety scan over `tests/` as well as `datasets/`; live raw telemetry remains private.
- **Errata cutoff is real.** Freeze the ten-row sample before seeing output. After Week 9's labels exist, dataset expectation edits invalidate affected labels and calibration. Date the cutoff; late bugs get explicit relabeling, not quiet patches.
- **Summaries are the public artifact — design them, don't dump them.** Counts, rates, kinds, verdict distributions, manifest fields: yes. Prompt texts wholesale, tool arguments verbatim, model prose: only what review confirms billboard-safe. The summary generator is repo code (`scripts/summarize_run.py` is coming in Week 8 — seed it now if convenient).
- **Ten reviews take longer than you think.** A real end-to-end trace review is 10–15 minutes each. Schedule the two hours; a skimmed review that misses a dataset bug costs a relabeling session later.

## Deliverable checklist — Instrumented Agent Specimen

- [x] Specimen config + run-manifest schema with content-derived `experimentId`, UUID4 `runId`, exact behavior pins, environment records, and fixtures.
- [x] Trace normalization adapter with block-local reasoning, inherited correlation/ordering, schema checks, semantic invariants, and edge-case tests.
- [x] Stateless mock-isolation regression test plus one public-safe Strands Evals compatibility probe with orthogonal planted facts and per-field mutation failures. See [`../reports/week-07-telemetry-compatibility.md`](../reports/week-07-telemetry-compatibility.md).
- [ ] Full-projection run: 62 normalized traces + a public-safe summary report.
- [ ] Dataset errata changelog containing the predeclared ten-row sample, selection rule, version/checksum, findings, and cutoff date.

## Success criteria

- [ ] 62/62 projected traces pass both JSON Schema validation and the documented semantic invariants; instrument errors never become agent verdicts.
- [ ] Repeated runs sharing one `experimentId` have distinct `runId`s and are compared with an exact tool-call-sequence comparator; agreement and every difference are reported rather than converted into a determinism claim.
- [ ] Every tool call answers mechanically which tool, arguments, result kind, and exact block-local pre-tool text or null; no cross-message text or causal rationale is inferred.
- [ ] The native Strands Evals mapping and repo adapter agree on every orthogonal planted fact; each per-field mutation fails, shape differences are documented, and no byte-identical-schema or managed-ingestion claim is made.

## Docs to consult

Verified via the AWS docs MCP server, Strands documentation, and Context7 `/strands-agents/evals`, 2026-07-16. Verify API signatures against the exact installed package before implementation; installed source wins if generated documentation differs.

- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — the span hierarchy you're capturing and its attribute names; the adapter's input format lives here.
- [Strands observability overview](https://strandsagents.com/docs/user-guide/observability-evaluation/observability/) — how traces/metrics/logs relate in the SDK; links out to the per-primitive pages including hooks-level instrumentation.
- [Strands Evals quickstart](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/) — the telemetry setup (in-memory exporter, session mapping) this specimen's capture can reuse directly, easing the Week 8 handoff.
- [Strands Evals task decorator](https://strandsagents.com/docs/user-guide/evals-sdk/how-to/eval_task/) — `@eval_task(TracedHandler())`, exporter clearing, and Session mapping used by the bounded compatibility probe; verify against the exact package version recorded in the manifest.

## Self-check

1. Explain `experimentId` versus `runId`. Which fields enter the pin projection, and why is `executedAt` excluded?
2. Why must the specimen's misbehavior survive this week unfixed? Name the methodological sin the rule prevents.
3. A trace shows `selectionReasoning: null`. Give two different valid explanations, and say what each implies for Week 10's judge.
4. Your two "identical" runs differ in one span's latency field and nothing else. Pass or fail on reproducibility? Cite the artifact that decides.
5. Why must exact prompt bytes preserve whitespace while the structured pin projection uses canonical JSON?
6. What's the difference between a dataset bug, an agent bug, and a contract ambiguity — and what's the destination artifact for each?
