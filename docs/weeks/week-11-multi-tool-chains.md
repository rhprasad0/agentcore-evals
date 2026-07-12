# Week 11 — Multi-Tool Integration Complexity

**Phase:** Complexity under contract (Weeks 11–13) · **Specimen:** 5-tool dependency-chain agent
**Lanes touched:** agent build (portfolio grows), custom eval lane (sequencing/state/cascade gates), first Memory touch
**Prerequisites:** Week 10 exit gate closed — calibrated judges and a trust policy; complexity is only allowed back in because the machinery to measure it now exists.

[← Week 10](week-10-judge-calibration.md) · [Week index](README.md) · [Next: Week 12 →](week-12-reliability-gates.md)

---

## Objective

Scale to a 5-tool agent with dependency chains (search → fetch → summarize → convert → notify), and extend the eval contract to sequencing, intermediate-state handling, and cascade-failure behavior.

## Why this week exists

Chains are where agents actually break: a defensible step-2 choice after a bad step-1 result, stale intermediate state, or a failure at step 4 that the user hears about as a cheerful success. Each new tool arrives *with* its contract, dataset rows, and gates — complexity under contract, not complexity then panic.

Unpack the three failure classes, because they're the design brief for everything this week builds:

1. **Defensible-locally, wrong-globally.** Step 2 (fetch) picks a reasonable URL *from step 1's bad search results*. Judged in isolation, step 2 is fine — which is why per-call gates can't catch it and sequence-level evaluation (DAG gates, trajectory judging) has to exist.
2. **Stale or hallucinated intermediate state.** Step 3 summarizes "the fetched page" — but is its input step 2's *actual* output, or the model's memory of what such a page probably says? This is fabrication at the hand-off layer, invisible unless you check step-N inputs against step-N−1 outputs mechanically.
3. **Silent cascade failure.** Step 4 times out; the model, four steps deep and eager to finish, papers over it. The user gets a confident answer built on a hole. The taxonomy's rule — *a failed step must surface* — becomes a gate this week, and "zero silent cascade failures" is a success criterion, not a hope.

## Concepts

### Five tools, five deliberately different risk profiles

The portfolio expansion isn't arbitrary — each addition exercises a distinct seam under the Week 5 contract discipline:

- **`search.web_search`** — already present from Week 4; now the chain's entry point and the primary source of *upstream badness* for class-1 failures.
- **`fetch.get_url`** — new risk: it takes a URL *the model chose* and retrieves arbitrary content. Two consequences: the tool defends itself with an **allowlisted domain set** (enforced inside the tool — agents reason, tools defend), and fetched content is **untrusted input to the model** — the prompt-injection surface widens from tool descriptions to tool *results*. Extend the canary rows accordingly.
- **`text.summarize`** — a second, cheaper model behind a tool boundary: the **agent-as-tool seam**, done deliberately small. Strands supports the pattern natively (pass an agent in `tools`, or wrap with `.as_tool()` / `@tool` for naming control — verified 2026-07-07). Note what this does to your manifest of pins: there are now *two* models in the system, both recorded in the run manifest.
- **`convert.units`** — pure function, no external calls: the control tool. When something breaks chains, the step that *can't* fail upstream is diagnostic gold.
- **`notify.send`** — **stub sink only.** Its contract says `sideEffects: write_external`, and the Week 5 ceiling rule holds: write actions stay stubbed until Week 12's reliability gates exist. The stub must still be *observable* (an assertable sink — a file, a queue, a log — not `/dev/null`), because "notify was called with the right payload" is a gate this week even though nothing real gets sent.

Update the capability manifest for all five; the agent's ceiling stays `read_external` — the stubbed notify is registered as its stub contract, and the loud-startup-failure test from Week 5 gets a new case proving the *real* notify can't sneak in.

### Chain scenarios: four row families

`datasets/synthetic/chain-scenarios.jsonl` (~40 rows) extends the Week 6 anatomy with chain semantics:

- **Full-chain tasks** — legitimately need all/most steps ("find today's temperature in the city hosting the next Olympics, convert to °F, and notify me").
- **Partial-chain tasks** — the agent *should skip* unneeded steps. Over-orchestration is a failure mode: running the full pipeline for a question that needed two steps is the chain-level version of over-calling, and these rows make it measurable.
- **Mid-chain failure injections** — fetch 403s, summarizer timeout: the mock registry's scripted failures now target a *step*, and the expected behavior (from the taxonomy) includes what the *final* response must disclose.
- **State-handoff traps** — rows engineered so hallucinated intermediate state is *detectable*: the mock's outputs carry fixture-unique sentinel values that could not be guessed. If step 3's input (or the final answer) carries the sentinel, state flowed; if it carries plausible-but-different content, you've caught fabrication mechanically.

Extend the trace schema with `parentSpanId` / `stepIndex` if Week 6's shape didn't already cover it — that's a schema version bump, with adapter and validator updates and a changelog entry, exactly like any contract change.

### Sequencing gates: DAG membership, not a golden path

The wrong gate design: "the correct sequence is [search, fetch, summarize, convert, notify]" — it fails every defensible reordering and skip. The right design: each scenario declares a **valid-sequence set** (a DAG whose paths are all legal), and the gate checks membership. "Defensible alternative order" is thereby a *legal verdict*, encoded in data rather than adjudicated per-run — the chain-level analogue of Week 9's `defensible-alternative` label.

Alongside membership, two more deterministic gate families:

- **Intermediate-state fidelity** — mechanically check step-N inputs for step-N−1 outputs (the sentinel trick makes this a substring/equality check, not NLP).
- **Cascade rules** — on any injected mid-chain failure, the final response must surface it (taxonomy-required disclosure), and downstream steps that logically depended on the failed step must not have run as if it succeeded.

### Trajectory evaluation: the judged complement, under Week 10's rules

Deterministic sequence gates can't assess "was this ordering *sensible* for this task" on genuinely open rows. `strands-evals`' **TrajectoryEvaluator** (verified: LLM-based, with built-in exact / in-order / any-order match scorers exposed as tools to the judge, plus a custom rubric) fills that gap — but it is a *judge*, and Week 10's posture applies with no exceptions: it gets calibrated before it's trusted. Run it first on rows where the DAG gates already produce verdicts; its agreement with the deterministic lane on decidable rows is your evidence for believing it on the undecidable ones. A trajectory judge adopted without that check is exactly the "random-number generator with good vibes" [Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails) warns about.

### The regression clause: growth must not cost you Week 8

Adding four tools changes the selection surface for *every* prompt, including the original 100. Baseline the chain agent on the Week 6 dataset: single-tool selection accuracy must hold within noise of the Week 8 baseline, or the regression gets investigated in writing. This is the plan's core discipline in miniature — **additions pay for themselves through the harness** — and the number goes in the report either way. (It's also a preview: Week 13 turns exactly this check into CI.)

## Build steps

### 1. Add the tools under Week 5 contract discipline

`search.web_search`, `fetch.get_url` (allowlisted domains), `text.summarize` (second model behind a tool boundary), `convert.units`, `notify.send` (stub sink; `sideEffects: write_external` stays gated until Week 12). Contracts, mocks, and manifest updates land *with* each tool — a tool without its contract doesn't merge.

### 2. Author `datasets/synthetic/chain-scenarios.jsonl` (~40 rows)

Four families as above; sentinel-bearing mock fixtures for the handoff traps; trace schema extended with `parentSpanId`/`stepIndex` if needed (version bump + changelog).

### 3. Extend the harness gates

Valid-sequence DAG membership per scenario, intermediate-state fidelity checks (grep step-N inputs for step-N−1 outputs), and cascade rules from the taxonomy (a failed step must surface, not vanish). Add `strands-evals` trajectory evaluation as the LLM-judged complement, using Week 10's calibration posture.

### 4. Visualize and re-baseline

Generate a Mermaid execution-flow diagram *from trace data* per scenario (a `scripts/` renderer); commit diagrams for 3+ interesting runs. Baseline the chain agent on the original 100-row dataset — the single-tool regression number goes in the report.

## Exercises — guided discovery

**1. Contracts before wiring.** Write all five tool contracts first, then rank the five by risk and defend the ranking.
- *Hint 1:* Risk axes you already own: `sideEffects` level, input trustworthiness (who controls the URL fetch retrieves?), output trustworthiness (whose text enters the context?), and failure blast radius mid-chain.
- *Hint 2:* Two candidates for riskiest have different *kinds* of danger (fetch: what comes in; notify: what goes out). Which does your current gate coverage handle worse? That's your answer.

**2. Engineer a handoff trap.** Design one state-handoff row end to end: the prompt, the sentinel-bearing mock fixtures, and the fidelity gate's exact check.
- *Hint 1:* The sentinel must be unguessable-but-plausible (a specific fake number in the fetched page, not `XYZZY` — the model might refuse to repeat obvious nonsense, which would mask the check).
- *Hint 2:* Decide where fidelity must hold: step 3's *input*, the final response, or both? What different failure does each location catch?

**3. Draw the DAG, then implement membership.** For one full-chain scenario, enumerate every legal path (skips included), express it as a DAG, and write the gate.
- *Hint 1:* Is `convert` skippable when the user asked in the source unit? Is `search` skippable when the prompt embeds the URL? Legality lives in the row, not the gate code.
- *Hint 2:* Watch the gate's failure evidence: "observed [search, summarize], no legal path visits summarize before fetch" beats "sequence invalid."

**4. Specify the cascade gate.** For a fetch-403 injection at step 2 of a 5-step scenario: enumerate what the final response must contain, must not contain, and what downstream spans must show.
- *Hint 1:* Your Week 5 taxonomy already answers the response-content half (`upstream_4xx` with `retryable: false` for this 403 → which baseline degradation behavior?). The span half is new: what does "summarize must not have run *as if* fetch succeeded" look like in trace terms?
- *Hint 2:* "Zero silent cascade failures" is the success criterion — write the gate so *silence* is the thing it detects (failure mentioned nowhere in the final response), not some specific wording.

**5. Calibrate the trajectory judge before believing it.** Run TrajectoryEvaluator over all rows where DAG gates produced verdicts; compute agreement; then — only then — read its verdicts on the open rows.
- *Hint 1:* Which scorer (exact / in-order / any-order) corresponds to your DAG semantics? A mismatch here manufactures fake disagreement.
- *Hint 2:* Where the trajectory judge and the DAG gate disagree, Week 9's five-bucket triage applies — with a new bucket possible: the *DAG row* is wrong (a legal path you didn't enumerate). How do you tell that bucket from judge error?

**6. Render the flow from data.** Build the Mermaid renderer over normalized traces and pick your three committed runs.
- *Hint 1:* `parentSpanId`/`stepIndex` give you the edges; what marks an *injected-failure* step visually so the diagram tells the cascade story at a glance?
- *Hint 2:* "Interesting" runs: one clean full-chain, one legal skip, one failure-surfaced cascade. What does each demonstrate to a portfolio reader?

## Gotchas & drift watch

- **Chain runs multiply model calls and cost.** 40 scenarios × up to 5 steps × (agent model + summarizer model) — budget tokens before the first full run, and iterate on a 5-row slice, not the corpus.
- **Legal variance vs flakiness.** Chains give the model *more* legitimate choices, so run-to-run sequence variation is expected — the DAG-set design absorbs it. If a scenario's verdict flips across runs, first ask whether the DAG is missing a legal path, not whether the model "got worse."
- **Two models, two pins.** The summarizer's model ID, prompt, and version join the run manifest. A summarizer swap is a manifest change — Week 8's identity rule extends to every model in the system.
- **Fetched content is attacker-shaped.** The injection canary rows must now include *fetched-page payloads* (inert, greppable, per Appendix C) — a page that "instructs" the agent. What the agent does with instructions inside tool *results* is a new eval question your Week 15 boundary work will lean on; collect the observations now.
- **Allowlist enforcement belongs to the tool.** `fetch.get_url`'s domain allowlist is validated inside the tool (with `bad_input` refusals for off-list URLs), not delegated to the model's judgment. Test the refusal path explicitly — it's a failure-injection row, not just a unit test.
- **The notify stub is a contract instance too.** Same envelope, same failure kinds, an assertable sink, and an explicit marker in its contract that it is the stub variant — Week 12's un-stubbing is then a contract version change, visible in diffs, not a quiet swap.
- **Schema extensions are breaking changes.** `parentSpanId`/`stepIndex` touch the adapter, validators, gates, and any tooling that reads traces. Version bump, changelog, and re-validate the Week 7 fixtures still pass — the old traces remain schema-valid under the new version or the version wasn't handled correctly.

## Deliverable checklist — Multi-Tool Chain Agent

- [ ] 5-tool agent with contracts, manifest, and stub-gated write action.
- [ ] Chain scenario dataset + sequencing/state/cascade gates with tests.
- [ ] Trace-derived execution flow visualizations (committed for 3+ interesting runs).
- [ ] Regression note: single-tool metrics before vs after the portfolio grew.

## Success criteria

- [ ] Sequencing accuracy ≥ target you set *before* running (state it in the report either way).
- [ ] Every mid-chain failure injection surfaces in the final response (zero silent cascade failures).
- [ ] Single-tool selection accuracy within noise of the Week 8 baseline — or the regression is investigated in writing.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-07.

- [Strands: agents as tools](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/) — the three implementation styles (direct in `tools`, `.as_tool()`, `@tool` wrapper); the summarizer seam is this page.
- [Strands Evals: TrajectoryEvaluator](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/trajectory_evaluator/) — rubric design and the exact/in-order/any-order scorers; read before Exercise 5 chooses a scorer.
- [Strands Evals: evaluators overview](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/) — where trajectory evaluation sits among the SDK's evaluator families.
- Your own Week 5–6 artifacts — the contract schema, taxonomy, and dataset anatomy are the normative docs this week extends; when in doubt, the discipline is "what would Week 5 require," not "what would be quickest."

## Self-check

1. Recite the three chain failure classes and, for each, the specific gate (or judge) this week builds to catch it.
2. Why is over-orchestration a failure, and which row family plus which metric make it visible?
3. Explain the sentinel technique: what property must the sentinel have, and what does its absence in step-3 input prove — and *not* prove?
4. Why does the trajectory judge need calibration when the DAG gates already exist? What can it see that they can't, and what's the cost of believing it uncalibrated?
5. The chain agent's single-tool accuracy dropped four points from the Week 8 baseline. Name three candidate causes in order of likelihood, and the diagnostic that separates them.
6. What makes the notify stub eval-grade rather than a placeholder? List the properties it must have this week, before it ever sends anything real.
