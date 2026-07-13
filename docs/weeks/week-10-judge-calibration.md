# Week 10 — Tool Selection Judge Calibration

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** the 64 labeled traces — now the measuring stick for two judges
**Lanes touched:** custom eval lane (your judge) meets the managed eval lane (AgentCore Evaluations) for the first time
**Prerequisites:** Week 9 exit gate closed — reviewed fixture with reliability numbers. Re-read the plan's [managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8) before starting.

[← Week 9](week-09-human-labeling.md) · [Week index](README.md) · [Next: Week 11 →](week-11-multi-tool-chains.md)

---

## Objective

Build a blind LLM judge that predicts tool-selection correctness and execution quality, calibrate it against the human fixture, and run identity-matched eligible telemetry through managed AgentCore Evaluations built-ins — a three-way agreement analysis whose methods state whether the managed lane saw trace-identical or replayed behavior.

## Why this week exists

This is the flagship week. Anyone can call an LLM a judge; the portfolio-grade move is publishing agreement numbers, false-pass/false-fail analysis, and a decision about *which* judge to trust *for what* — including the managed one AWS would sell you. Judges only earn scaling rights (labeling rows 65–10,000) after they match humans on rows 1–64.

The economics explain the structure: humans are the only ground truth but cost minutes per verdict; judges cost cents and scale to production sampling — *if* they agree with humans. Calibration is the purchase of that "if." And it's symmetric: `Builtin.ToolSelectionAccuracy` asks a judge model whether an action was justified — a defensible rubric, but still a model's opinion, and this week measures how often that opinion matches humans *for this agent*. The deliverable isn't a score; it's a **trust policy** — a written statement of which judge is believed for which question, at what threshold, with disagreements routed where.

## Concepts

### The separation rule: judge the decision, not the outcome

The tool-selection judge sees **the conversation up to the tool call and the available-tools list — never actual tool outputs**. A separate execution-quality judge sees the full trace. This isn't fussiness; it's the difference between two questions:

- *Was calling the weather tool with these args justified, given what the model knew?* — a decision-quality question. Showing the judge the result contaminates it with hindsight (a lucky success launders a bad decision; an unlucky failure taints a good one).
- *Given everything that happened, was the final behavior right?* — an outcome question, where results are exactly the evidence needed.

Blindness here must be enforced the same way Week 9 enforced it for humans: **in the plumbing, not in the prompt.** The judge-input builder renders only the permitted fields, and a unit test asserts the rendered prompt contains no result data (Exercise 1). "The prompt tells the judge to ignore outcomes" is not blindness; it's a request.

For comparison, know what AWS's judge sees — the built-in prompt templates (verified 2026-07-07) define tool-level evaluator placeholders as: `available_tools` (tool IDs, parameters, descriptions), `context` (prior turns' prompts, tool call details, assistant responses, plus the current turn up to the call under evaluation), and `tool_turn` (the call being judged). Read the actual templates this week — knowing precisely where the managed judge's evidence differs from yours turns "the judges disagree" from a shrug into an analyzable fact.

### The judge is a program: structured output, versioned prompts, measured variance

Build the judge (`src/judges/`) as Claude on Bedrock via the **Converse API**, with a structured-output contract mirroring the built-ins' shape — `{reasoning, score}` JSON. The reliable way to get schema-conforming output from Converse is the **tool-use pattern**: define a "record_verdict" tool whose input schema *is* your verdict schema, and force the model to call it — schema conformance comes from the tool contract rather than from asking nicely.

Engineering rules that make the judge a measurement instrument rather than a vibe:

- **Prompts are versioned like code** — judge prompt changes get diffs, versions, and re-calibration; an unversioned judge prompt is an uncontrolled variable in every number downstream.
- **Verdict variance is measured, not assumed away** — run the fixture ×3 and compute the **flip rate** per field ([Appendix B](../../LEARNING_PLAN.md#appendix-b--metrics-glossary)). Above ~5%, do temperature/prompt work before any scaling: an unstable judge can *agree* with humans on average while being useless per-row.
- **The judge inherits Week 7's null problem** — some spans have no `selectionReasoning`; the judge's input builder and rubric must handle absence explicitly (judging the decision from conversation state alone), not crash or silently treat null as guilt.

### Agreement is not one number: the analysis frame

For each judge lane, against the human fixture, per field:

- **Agreement** (raw; κ if you want chance-correction — you learned it last week).
- **False-pass rate** — judge says fine, human said fail. *The dangerous direction*: false passes scale silently when the judge starts labeling rows 65+.
- **False-fail rate** — judge flags what humans passed. Costs triage time; erodes trust in red gates.
- **A confusion matrix per judge** — the two rates above are its off-diagonal, but seeing the full matrix (including the `defensible-alternative` column) exposes *where* a judge is confused, not just how often.
- **Cost per verdict** — measured, all three lanes (human minutes, your judge's Bedrock tokens, the managed lane's billed tokens). This column is what turns the calibration table into a routing policy.

Then the part that doesn't automate: **analyze every disagreement by hand.** Some will be judge errors (report them as the judge's failure modes — "over-trusts scoped descriptions", "penalizes defensible alternatives"); some will be *your* label errors (route back through Week 9's adjudication with a versioned relabel). Both belong in the report — a calibration that never indicts a label is suspicious.

### The managed lane: same rubric names, three supported plumbing choices

Mechanics verified 2026-07-13: built-in evaluators are addressed as `Builtin.EvaluatorName` (this week uses `Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, and `Builtin.GoalSuccessRate`), and their models and prompt templates are fixed and unmodifiable. Do not reduce on-demand evaluation to one CloudWatch-only path:

1. **CLI/starter-toolkit session retrieval:** `agentcore run eval` (or the starter toolkit) locates a Runtime session and downloads its telemetry from CloudWatch before evaluation. This is the easiest operational path for deployed sessions.
2. **Direct `Evaluate` API:** `EvaluationInput.sessionSpans` accepts an array of OpenTelemetry JSON values for a session. This is the cleanest candidate for evaluating the same supported telemetry humans labeled, but current API reference text alone does not settle how ADOT-split correlated event records must be packaged.
3. **Service-side online/batch sources:** online configurations select a Runtime endpoint or CloudWatch log groups; batch jobs discover and collect matching sessions from CloudWatch. These are later operational lanes, not the default for this calibration fixture.

The 64 labeled traces are local canonical artifacts, not automatically any of those managed inputs. Three honest strategies follow:

- **Replay-and-relabel-aware:** replay rows through a deployed specimen, evaluate the resulting Runtime sessions, and acknowledge that labels transfer only where the observed behavior still matches the labeled trace.
- **Direct supported-telemetry submission:** use the Week 6 source-profile mapping to construct `sessionSpans`, then prove acceptance with one small live `Evaluate` smoke before running the fixture. If split event-record packaging is still undocumented or rejected, record that boundary and adapter delta rather than improvising a hidden format.
- **CloudWatch export/source:** emit supported telemetry to the expected CloudWatch locations and let the selected managed mode reconstruct sessions from spans plus correlated event records.

Choose deliberately and document trace identity, transport, and label-transfer rules. The live smoke is the first service-acceptance receipt for Week 6's offline compatibility work; a local schema pass was never that receipt. Record **evaluator IDs and dates in the run manifest** because built-ins are moving dependencies ([managed boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)).

Score semantics also differ across lanes: built-ins return numeric `value` plus `label`; your judge emits your schema; humans labeled a ternary. Define the mapping into a common verdict space *before* computing agreement — a threshold choice hidden inside the comparison code is a thumb on the scale.

### The trust policy is the deliverable

The week ends in a written policy with teeth — e.g.: *own judge for PR-time selection checks (cheap, calibrated, blind); managed built-ins for production sampling (no infra to run); disagreements between lanes route to human review; neither judge trusted yet for parameter-fabrication verdicts pending more labels.* Every clause cites a number from the calibration table, including the costs. "Not trusted for X yet" clauses are required — a policy with no exclusions wasn't calibrated, it was rubber-stamped.

## Build steps

### 1. Build the blind judge and the execution judge

`src/judges/`: Claude on Bedrock via Converse, structured `{reasoning, score}` output (tool-use pattern for schema conformance), versioned prompts. Separation rule enforced in the input builder: the selection judge's world ends at the tool call; the execution judge sees the full trace.

### 2. Run the judges over the 64 labeled traces ×3

Compute per-field: agreement, false-pass rate, false-fail rate, flip rate across repeats, and where judge confidence diverges from human rationale. Analyze every disagreement by hand — judge errors and label errors both go in the report.

### 3. Prove managed acceptance, then run the managed lane

Choose replay, direct `EvaluationInput.sessionSpans`, or CloudWatch sourcing using the identity rules above. First submit one billboard-safe sample session and verify that AgentCore Evaluations reconstructs the expected invoke-agent and tool-call evidence; record the accepted source profile and any event-record packaging requirement in `docs/telemetry-compatibility.md`. Then run `Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, and `Builtin.GoalSuccessRate` over the eligible fixture sessions. Export scores via a small adapter into the same comparison frame, keyed to exact run/trace identities.

### 4. Publish `docs/judge-calibration.md`

The three-way table, a confusion matrix per judge, cost-per-verdict for each lane, the disagreement casebook, and the written trust policy.

## Exercises — guided discovery

**1. Prove the judge is blind.** Write the test that fails if tool outputs leak into the selection judge's rendered prompt.
- *Hint 1:* What marker can you plant in a fixture trace's tool *result* that must never appear in the rendered judge input? (You have a canary habit already.)
- *Hint 2:* Test the builder over every fixture row, not one — the leak will be in an edge shape (multi-call trace, failure envelope), not the happy path.

**2. Read AWS's rubrics before comparing against them.** From the prompt-templates doc, summarize in your own words what `Builtin.ToolSelectionAccuracy` actually asks its judge, and diff it against your judge prompt: evidence available, question asked, scale returned.
- *Hint 1:* Does the built-in's `context` include information your separation rule forbids? If so, predict the disagreement pattern *before* seeing the data — hindsight-contaminated judges should be systematically more forgiving of failed-but-reasonable calls, or harsher on succeeded-but-unjustified ones. Which?
- *Hint 2:* Write the prediction down. Checking it against the actual three-way table is the most interesting paragraph your calibration doc can contain.

**3. Design the common verdict space.** Humans labeled ternary (`correct/incorrect/defensible-alternative`); your judge emits `{reasoning, score}`; built-ins return `value` + `label`. Define the mapping that makes them comparable, and defend every threshold.
- *Hint 1:* Where does `defensible-alternative` go — merged with correct? Its own column? The answer changes both judges' apparent accuracy; compute the table both ways once and see.
- *Hint 2:* Whatever you choose, the choice lives in the report's methods section, not in a code comment.

**4. Beat the baseline, honestly.** Compute the majority-class baseline for `toolSelection` on the fixture and state your judge's margin over it.
- *Hint 1:* If 80% of fixture rows are `correct`, a judge that always says correct scores 80% agreement. What does your judge add — and on which strata does it actually earn its keep? (Per-stratum agreement, not overall, answers this.)
- *Hint 2:* You iterated the judge prompt against these same 64 rows. What does that do to the number's meaning, and what split (dev rows for iteration / held rows for the reported figure) would firm it up? Decide, do it, and say what you did in the report.

**5. The flip-rate experiment.** Three repeat runs, fixed inputs. Per field: how many rows changed verdict at least once? Where do flips concentrate?
- *Hint 1:* If flips cluster on rows humans called `defensible-alternative`, what does that tell you about the construct itself — is the judge unstable, or is the row genuinely bistable?
- *Hint 2:* The >5% rule is a gate on *scaling*, not on existing. Which uses in your draft trust policy survive a 7% flip rate, and which don't?

**6. Cost the three lanes.** Per verdict: your judge (tokens × Bedrock price), managed (billed evaluation tokens — pricing verified: built-ins charge by tokens processed, model usage included), human (your Week 9 minutes, priced honestly).
- *Hint 1:* Costs differ per *field* too — the execution judge reads full traces (more tokens) than the selection judge. Which verdicts are expensive enough to route selectively?
- *Hint 2:* The trust policy's routing table is this cost table joined with the agreement table. Draft it as literally that join.

## Gotchas & drift watch

- **Telemetry identity and packaging are the hidden prerequisites.** The CLI session path retrieves Runtime telemetry from CloudWatch; the direct API accepts `sessionSpans`; online/batch modes have service-side sources. None makes the repo's canonical JSON an ingestion format. Budget real time for one live acceptance smoke, especially the span/event-record split, and record every adapter surprise in `docs/telemetry-compatibility.md` before scaling.
- **Built-ins are moving dependencies.** Their models and templates can change without your consent and cannot be modified (verified). Every managed score in the comparison frame carries evaluator ID + run date; a future re-baseline (Week 13's runbook) starts from those fields.
- **Cross-Region inference:** built-in evaluators may execute their judge models via cross-Region inference — check the current docs' note if data-locality matters to what you send, and confirm evaluator availability in `us-east-1` before scheduling the week.
- **Don't let the judge grade its own homework.** Your judge and your specimen may share a model family (Claude judging Claude). That's acceptable — and industry-common — but name it in the report as a limitation with the known risk (self-preference bias), rather than letting a reviewer discover it.
- **Fixture leakage into prompt iteration** (Exercise 4's trap): iterate-on-all-64-report-on-all-64 measures fit, not judgment. Whatever split you adopt, adopt it *before* looking at per-row results, and freeze it.
- **Token bills are real this week.** 64 traces × 2 judges × 3 repeats × (plus managed runs) is the priciest eval week so far — still small dollars, but run the arithmetic first (cost guardrails in [Working assumptions](../../LEARNING_PLAN.md#working-assumptions)), batch small, and don't casually re-run the world after every prompt tweak. Pinned datasets, deliberate runs.

## Deliverable checklist — Automated Judge System

- [ ] Blind judge + execution judge with versioned prompts, structured output schema, repeat-run variance stats.
- [ ] Live managed acceptance smoke plus a managed evaluation run over identity-matched eligible traces, with an explicit transport/adapter record.
- [ ] `docs/judge-calibration.md`: three-way agreement, FP/FN analysis, per-verdict cost, trust policy.
- [ ] Disagreement casebook (every human-vs-judge conflict adjudicated in writing).

## Success criteria

- [ ] Your judge's agreement with humans on `toolSelection` beats a majority-class baseline by a margin you state — and you can name its failure modes.
- [ ] Verdict flip rate across repeats measured and reported (if >5%, temperature/prompt work before any scaling).
- [ ] A sample supported-telemetry session is accepted and reconstructed by AgentCore Evaluations; the receipt names the source profile, invocation path, and any split event-record requirement without exposing raw content.
- [ ] The trust policy names concrete uses for each judge lane, including "not trusted for X yet."

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-13.

- [Built-in evaluators overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-evaluators-overview.html) — the `Builtin.Name` ID contract and the immutability note that makes version-recording mandatory.
- [Built-in evaluator prompt templates](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/prompt-templates-builtin.html) — read the *actual rubrics* you're comparing against, especially both tool-level templates and their placeholder definitions (Exercise 2's source).
- [Getting started with on-demand evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-on-demand.html) — `agentcore run eval` and the starter-toolkit `Evaluation` client; the invocation shapes for build step 3.
- [`EvaluationInput` API reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_EvaluationInput.html) — the direct `sessionSpans` union used by the acceptance smoke.
- [Strands Agents telemetry extraction](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-strands.html) — how Evaluations classifies Strands spans and reads inline versus split content.
- [Spans, event records, and telemetry signals](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html) — why spans alone may be insufficient after ADOT extraction and how correlation works.
- [AgentCore Evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html) — the service overview tying evaluators, data sources, and result destinations together.
- [AgentCore pricing — Evaluations section](https://aws.amazon.com/bedrock/agentcore/pricing/) — how built-in vs custom evaluator billing works; Exercise 6's source.
- [Structured output via Converse tool use](https://aws.amazon.com/blogs/machine-learning/structured-data-response-with-amazon-bedrock-prompt-engineering-and-tool-use/) — the pattern for schema-conforming judge verdicts (define the verdict schema as a tool's input schema).

## Self-check

1. State the separation rule and the specific bias each half prevents. Where is it enforced, and what proves the enforcement?
2. Why is false-pass the dangerous direction for a judge that will scale? Trace the harm through rows 65–10,000.
3. Your judge agrees with humans at 88%; majority-class is 81%; flip rate is 8%. Write the honest one-sentence summary — and say what the trust policy licenses this judge to do today.
4. What exactly do you record about a managed evaluator per run, and which future event makes each field load-bearing?
5. Explain the replay vs direct `sessionSpans` vs CloudWatch-source choice and what each path does to the claim "AWS's judge was measured against the same traces as humans."
6. A reviewer asks: "Claude judging Claude — isn't that circular?" Give the two-part honest answer (why it's still informative; what limitation you disclose).
