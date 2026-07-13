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

### Pinning, and the run manifest as the join key

A measurement you can't reproduce is an anecdote. The specimen pins every input that influences behavior — **model ID, system prompt, tool set (one), exact (`toolId`, contract version) references, exact capability-manifest ID/version, tool descriptions, mock fixture version, dataset version, temperature (low)** — and records them in a **run manifest** (`runId`, plus each pin, plus date). Readable canonical IDs and exact versions are the join keys; hashes supplement them for integrity and change detection. Two properties to design for:

1. **The manifest is the identity of the run.** Same manifest ⇒ comparable numbers; any pin differs ⇒ different experiment, different baseline. Week 8's "flip one word and watch gates move" and Week 13's "regression, not noise" both *are* manifest comparisons.
2. **The manifest is the join key for everything downstream.** Human labels (Week 9) label traces from a specific run; judge verdicts (Week 10) attach to the same; managed-lane scores (Weeks 10+) get manifest fields recorded alongside — including evaluator IDs and dates, per the plan's [managed-evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8). If a score can't name its manifest, it isn't evidence.

Subtle but important: the **prompt hash must cover the tool descriptions**, not just the system prompt. Week 2 established that descriptions steer selection; a manifest that lets a description change slip through unhashed will happily "reproduce" a different agent.

A contract or capability-manifest version change produces a different run identity. Revalidate the dataset and mock fixtures against the new exact versions; do not silently retarget old runs or migrate labels. Existing labels remain attached to the dataset, contract, and manifest versions they actually judged.

### Instrumentation: capture the declared source profile, normalize once, test the adapter

The pipeline is capture → normalize → store:

- **Capture** with the exact Strands telemetry profile pinned in the run manifest. Depending on collection, conversation and tool payloads may be inline span events or ADOT-split event records correlated to metadata spans; arguments/results are not assumed to be direct span attributes. For local runs, an in-memory exporter is the friction-free option — the Strands evals SDK ships telemetry setup for exactly this pattern, which Week 8 will lean on directly.
- **Normalize** in `src/adapters/`: a declared Week 6 Strands source profile in → `execution-trace.schema.json`-valid trace out. The adapter is boring, load-bearing code — it gets unit tests with the public-safe synthetic inline and split fixtures from Week 6 so an SDK upgrade changing raw shapes fails tests instead of silently corrupting normalized data.
- **Store** under `datasets/runs/<runId>/` — raw traces git-ignored, public-safe summaries committed. The billboard rule is at its most tempting to break here, because raw traces are so *useful*; the summary format you design this week is what makes the useful parts shareable.

Strands Evals also offers a convenience path: `@eval_task(TracedHandler())` clears the in-memory exporter per case, invokes a fresh agent, and maps finished spans into a Strands `Session`. Exercise it once as a **compatibility probe**, then compare it with the repo adapter on the same declared synthetic source profile. The convenience path does not replace the canonical trace, and a Strands `Session` is not a new storage contract. Any serialized Session receives the same treatment as a raw trace: private and git-ignored unless transformed into an explicitly reviewed synthetic fixture.

### `selectionReasoning`: optional observed text, not a causal explanation

If an assistant message contains text immediately preceding a `toolUse` block, store that observed text as `selectionReasoning` on the canonical tool-call span. Week 10's blind judge may use it as evidence about the stated justification; the decision remains judgeable from conversation state and available tools when it is absent.

Two honesty notes belong in the schema docs. First, **presence is provider-, prompt-, and telemetry-shape-dependent** — models often emit a tool call with no preceding prose; store explicit null, never an empty string or adapter-invented explanation, and measure the presence *rate* (Exercise 5). Second, **stated reasoning is evidence, not mechanism** — models can rationalize; the text tells you what the model *said*, not causally *why* it acted. The Week 3 trace did not expose a reliable rationale field, so failure to find observed pre-tool text is valid data rather than an adapter defect by default.

### The errata pass: fix the ruler before measuring people with it

Build step 4 has you hand-review ten traces end-to-end and fix dataset bugs *now*, with a changelog, before humans label against them. The discipline that makes this safe is a sharp line between two kinds of findings:

- **Dataset bugs** — the row's expectation is wrong or underdetermined (the prompt doesn't imply what `expected` claims). *Fix now*, changelog entry, dataset version bump. After Week 9, editing expectations means invalidating labels — this week is the last cheap window.
- **Agent bugs** — the expectation is right and the agent violates it. **Do not fix the agent.** Record it. The specimen is under measurement, not development; "fixing" it now would be tuning to the test set before the test exists. Agent failures found here are previews of Week 8–9 findings, and their persistence is what makes those findings real.

If you can't decide which kind a surprise is, that's usually a third finding: the *contract* is ambiguous (Week 5 artifact bug). Route it there.

## Build steps

### 1. Configure the specimen

Weather agent, weather tool only (mock registry from Week 6 behind it), pinned model ID, pinned system prompt, temperature pinned low. Record all pins in a run manifest (`runId`, model, prompt hash, exact (`toolId`, contract version) references, exact capability-manifest ID/version, dataset version, mock fixture version, date). Design the manifest schema first (Exercise 1) — it's a schema like any other, with fixtures.

### 2. Instrument and normalize

Use Strands hooks/callbacks + telemetry export to capture the loop; write the adapter (`src/adapters/`) that normalizes the pinned Week 6 Strands source profile into `execution-trace.schema.json`. Support the profile actually emitted by this run (inline or ADOT-split), fail loudly on orphaned correlations, and store observed pre-tool assistant text or explicit null as `selectionReasoning`. Ship the adapter with tests: synthetic source fixture in → schema-valid trace out.

Run one synthetic case through `@eval_task(TracedHandler())` as a bounded cross-check. Compare its mapped Session with the repo-normalized trace for tool name, arguments, result status, and correlation identifiers; document fields present in only one representation and fail if either path silently drops a canonical required fact. Record the exact `strands-agents-evals` version and capture path in the run manifest.

### 3. Run the full 100-row dataset

Store normalized traces under `datasets/runs/<runId>/` (git-ignored raw, committed public-safe summaries). This is your first full-corpus run — expect mock-registry misses (canonicalization gaps) and adapter edge cases; fixing *those* is this week's real debugging.

### 4. Hand-review ten traces end-to-end

Annotate surprises. Mislabeled expectations in the dataset get fixed *now*, with a changelog entry, before humans label against them. Agent misbehavior gets recorded, not fixed.

## Exercises — guided discovery

**1. Design the run-manifest schema.** Decide every field, and for each: is it a *pin* (input you fixed) or a *record* (output you observed)?
- *Hint 1:* Candidate pins: model ID, prompt hash, exact (`toolId`, contract version) references, exact capability-manifest ID/version, tool-description hashes, dataset version, mock fixture version, temperature, SDK versions. Which of these actually change behavior? (All of them. Which did you almost leave out?)
- *Hint 2:* What does the prompt hash hash, exactly — and does a whitespace-only edit to a docstring change your agent's behavior? Should it change the hash?
- *Hint 3:* Why keep readable versions when hashes already detect changes? Which downstream human or artifact needs to join without reverse-engineering a hash?

**2. Adapter edge cases first.** Before writing the happy path, list the source-profile shapes that could break normalization, and write failing tests for them.
- *Hint 1:* Multiple tool calls in one assistant message; an ADOT event record with no matching span; a tool result with no matching call visible; a run that ends mid-loop; a `toolUse` with no preceding text (null reasoning).
- *Hint 2:* What should the adapter do with a shape it doesn't recognize — best-effort or refuse? Which failure mode do you want six months from now, and what does your Week 5 fail-loudly precedent suggest?

**3. Measure repeatability, then break it.** Run the dataset twice under one manifest; compare tool-call sequences and the Week 6 ordered canonical projections separately. Then change exactly one pin (temperature up, or one docstring word) and diff again.
- *Hint 1:* The Week 6 fixture test already proved normalization determinism for equivalent inputs. A same-manifest model rerun can still differ because of sampling. Separate model variation, mock-key misses, and adapter/projection bugs rather than calling all three nondeterminism.
- *Hint 2:* The one-pin experiment is Week 8's sensitivity check in miniature; save both run directories as its raw material.

**4. The errata protocol.** For your ten-trace review, write the triage rule before reviewing: what evidence classifies a surprise as dataset bug vs agent bug vs contract ambiguity?
- *Hint 1:* Test each surprise against the blind-prediction standard: given only the prompt and the contracts, what *should* happen? If reasonable readers disagree, which artifact failed?
- *Hint 2:* Changelog entry shape: row id, old → new expectation, why, dataset version bump. Where does the version live so Week 9's labels can cite it?

**5. Reasoning presence audit.** Across the 100-row run, measure: on what fraction of tool-call spans is `selectionReasoning` non-null? Does presence correlate with row family (ambiguous vs straightforward)?
- *Hint 1:* If presence is low, what could raise it — and is that intervention (prompting for explanations) *changing the specimen*? What does the manifest say about that?
- *Hint 2:* Whatever the rate is, write it in the run summary; Week 10's judge design must plan for the null case rather than discover it.

**6. Cross-check the native Evals mapping.** Run one public-safe synthetic case through `@eval_task(TracedHandler())`, inspect the resulting Strands `Session`, and compare it with the repo adapter's canonical trace for the same declared source profile.
- *Hint 1:* The two shapes do not need to serialize identically. Observed tool name, arguments, result status, and correlation identifiers must agree; the canonical `toolId`/contract binding remains a repo-owned extension that the checked mapping must recover explicitly.
- *Hint 2:* Plant one source field that the canonical schema requires. A comparison that still passes after either adapter drops it is a tautology, not a compatibility test.
- *Hint 3:* `TracedHandler` manages exporter clearing per case, but cache/report identity still depends on unique case and session identifiers. Where are those pins recorded?

## Gotchas & drift watch

- **Temperature low ≠ deterministic.** Provider-side sampling, batching, and numerical nondeterminism can vary output at temperature 0. Week 6 proves byte identity only for ordered canonical projections of equivalent telemetry inputs. This week measures repeated model runs separately through tool-call sequence agreement.
- **Versions and hashes answer different questions.** Exact contract/manifest versions say which reviewed promises governed the run; hashes prove the actual prompt/spec bytes did not drift. Keep both. A changed version creates a new run identity and triggers dataset/mock revalidation; no automatic migration is promised.
- **Hooks/telemetry APIs are the fastest-moving part of Strands.** Some hook and telemetry interfaces live in experimental namespaces; verify current names in the docs before wiring, and pin SDK versions in the manifest so an upgrade is a *decision*, not ambient drift.
- **Convenience mapping can become accidental architecture.** `TracedHandler` is useful plumbing, but custom gates still consume the repo's canonical trace through a tested adapter. If an SDK Session gains or loses a field, the compatibility test should fail before the evidence model changes.
- **Keep committed source fixtures synthetic.** The adapter's test fixtures preserve raw Strands-shaped structure, but their values are authored placeholders—not captured Runtime payloads. Run the safety scan over `tests/` as well as `datasets/`; live raw telemetry remains private.
- **Errata cutoff is real.** After Week 9's labels exist, dataset expectation edits invalidate the affected labels (and any calibration built on them). Date the errata window's close in the changelog; late-found bugs get logged and batch-fixed with explicit relabeling, not quietly patched.
- **Summaries are the public artifact — design them, don't dump them.** Counts, rates, kinds, verdict distributions, manifest fields: yes. Prompt texts wholesale, tool arguments verbatim, model prose: only what review confirms billboard-safe. The summary generator is repo code (`scripts/summarize_run.py` is coming in Week 8 — seed it now if convenient).
- **Ten reviews take longer than you think.** A real end-to-end trace review is 10–15 minutes each. Schedule the two hours; a skimmed review that misses a dataset bug costs a relabeling session later.

## Deliverable checklist — Instrumented Agent Specimen

- [ ] Specimen config + run manifest schema; everything pinned and recorded.
- [ ] Trace normalization adapter with tests (pinned synthetic Strands source profile in → schema-valid trace out).
- [ ] One public-safe synthetic compatibility test comparing the repo adapter with Strands Evals' `TracedHandler`/Session mapping on the same declared source profile.
- [ ] Full-dataset run: 100 normalized traces + a public-safe summary report.
- [ ] Dataset errata changelog from the hand review.

## Success criteria

- [ ] 100/100 traces validate against the trace schema.
- [ ] Repeated same-manifest runs are compared with an exact tool-call-sequence comparator; the agreement rate and every difference are reported rather than converted into a model-determinism claim.
- [ ] Every trace answers, mechanically: which tool, what args, what result kind, what the agent said, and whether observed pre-tool assistant text was present or explicitly null; no causal rationale is inferred.
- [ ] The native Strands Evals mapping and repo adapter agree on required tool-call facts for the synthetic compatibility case; shape differences are documented and no byte-identical-schema claim is made.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07.

- [Strands traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/) — the span hierarchy you're capturing and its attribute names; the adapter's input format lives here.
- [Strands observability overview](https://strandsagents.com/docs/user-guide/observability-evaluation/observability/) — how traces/metrics/logs relate in the SDK; links out to the per-primitive pages including hooks-level instrumentation.
- [Strands Evals quickstart](https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/) — the telemetry setup (in-memory exporter, session mapping) this specimen's capture can reuse directly, easing the Week 8 handoff.
- [Strands Evals task decorator](https://strandsagents.com/docs/user-guide/evals-sdk/how-to/eval_task/) — `@eval_task(TracedHandler())`, exporter clearing, and Session mapping used by the bounded compatibility probe; verify against the exact package version recorded in the manifest.

## Self-check

1. Recite your manifest's pins from memory. Which pin would most people forget, and what silent failure does forgetting it cause?
2. Why must the specimen's misbehavior survive this week unfixed? Name the methodological sin the rule prevents.
3. A trace shows `selectionReasoning: null`. Give two different valid explanations, and say what each implies for Week 10's judge.
4. Your two "identical" runs differ in one span's latency field and nothing else. Pass or fail on reproducibility? Cite the artifact that decides.
5. What's the difference between a dataset bug, an agent bug, and a contract ambiguity — and what's the destination artifact for each?
