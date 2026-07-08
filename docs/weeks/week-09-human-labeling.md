# Week 9 — Human Tool-Selection Labeling

**Phase:** Eval contract (Weeks 5–10) · **Specimen:** Week 7's traces, now under human judgment
**Lanes touched:** custom eval lane — the ground-truth layer everything else calibrates against
**Prerequisites:** Week 8 exit gate closed — harness baselined, per-tag reports exist, gate verdicts recorded (and hidden from you shortly).

[← Week 8](week-08-local-harness.md) · [Week index](README.md) · [Next: Week 10 →](week-10-judge-calibration.md)

---

## Objective

A browser-based labeling workflow and a reviewed 64-row human-labeled fixture covering tool-selection correctness, execution quality, and error-recovery behavior — labeled blind.

## Why this week exists

Human labels are the only ground truth this repo recognizes. Every judge — yours in Week 10, AWS's built-ins, the Week 16 optimization loop — gets measured against this fixture. Sixty-four careful rows beat six hundred careless ones; the previous plan's 48-row fixture caught real failures precisely because every row was actually reviewed.

Notice what this week is *not*: it is not "have opinions about traces." It is measurement design — writing label definitions crisp enough that the same trace gets the same label twice, proving that with test–retest numbers, and treating every label-vs-gate disagreement as a finding about one of five artifacts (gate, dataset, contract, agent, or label spec). The fixture's authority comes entirely from this rigor. A judge calibrated against sloppy labels is calibrated garbage — and Week 10 is calibration week.

## Concepts

### The label schema is a measurement instrument

Each field of `schemas/human-label.schema.json` is a deliberate design choice:

- **`toolSelection`: correct / incorrect / defensible-alternative.** The third value is the load-bearing one. Ambiguous rows exist (you wrote ten on purpose); forcing them into a binary would either corrupt the metric (defensible choices counted wrong) or corrupt the labels (you'd quietly grade "what I'd have done" instead of "was this justified"). `defensible-alternative` lets the metric stay honest — and its *rate* becomes a signal of its own (see Gotchas for its failure mode).
- **`parameterQuality`: correct / wrong-value / fabricated.** Two failure values because they are different *dangers*: `wrong-value` is a mistake (Oslo when Bergen was asked); `fabricated` is a value with no source in the conversation at all — the parameter-level cousin of hallucination, the thing `Builtin.ToolParameterAccuracy` claims to detect, and the class you most need ground truth for.
- **`executionQuality`: pass / fail + tags** (`ignored-tool-failure`, `hallucinated-tool-output`, `over-called`, `under-called`). The tags turn a verdict into a diagnosis; they are also the vocabulary Week 10's judge-error analysis will be conducted in.
- **`errorRecovery`: compliant / non-compliant** — failure-injection rows only, judged *against the Week 5 taxonomy's required behavior*, not against taste. If you find yourself judging taste, the taxonomy has a gap; file it.
- **Free-text rationale, required on every fail.** Three consumers: reconciliation (pass 2 vs pass 1), Week 10's disagreement casebook (human rationale vs judge reasoning), and future-you deciding whether a label was right. A fail without a rationale is a mood.

### Blindness is the whole protocol

The workbench hides the dataset's `expected` block and all harness verdicts. You label what the agent *did*, not whether it matched your own spec — divergences between labels and gates are findings, not annoyances.

Why so strict, when you wrote both the spec and the labels? Anchoring. Shown "gate: FAIL," a labeler — any labeler, including the gate's author, *especially* the gate's author — drifts toward agreement; the fixture would become an echo of the harness, and Week 10's "judge vs human" comparison would secretly be "judge vs gate," which the gates could have told you for free. Blindness is what makes the human lane *independent* — and independence is what makes agreement between lanes evidence rather than incest. (Same logic, one level up: pass 2 must also be blind to pass 1 — the workbench hides your own earlier labels too.)

### Selecting 64 rows is stratified sampling, not favorites

The fixture must support the questions Week 10 will ask of it, so composition is deliberate: **every tag represented** (per-tag judge agreement needs per-tag rows), **all failure kinds covered** (errorRecovery labels need each kind), **every harness-gate disagreement candidate included** (rows where gates surprised you are where labels earn most), **plus a random fill** (so the fixture isn't purely curated toward interestingness — random rows keep base rates honest). Document the strata and counts; "how was the fixture chosen" is the first methods question any reviewer asks, and "deliberately, here's the table" is the portfolio-grade answer.

### Reliability: agreement is a property of the definitions

You are (probably) one labeler, so the plan substitutes **test–retest self-agreement**: label all 64 twice, on different days, and compute per-field agreement — plus **Cohen's κ on a 16-row overlap with a second labeler** if you can recruit one (κ corrects raw agreement for chance; report both).

The interpretive rule is the important part: **if `toolSelection` self-agreement lands below 0.85, the label definitions are the bug** — not your attention span. Disagreement with yourself across days means the definition let two readings coexist; the fix is sharper definitions (and relabeling), not trying harder. This reframe is what makes the reliability number an engineering signal instead of a self-esteem exercise.

### Disagreements are the yield

When labels and gate verdicts diverge, exactly one of five things is true: the **gate** is buggy (fix Week 8 code), the **dataset row** was wrong (post-errata: log for batch fix + relabel), the **contract/taxonomy** is ambiguous (fix Week 5 artifact), the **agent** genuinely failed in a way gates can't see (a real finding — the success criteria demand at least one), or the **label** is wrong (adjudicate, document). The findings report that sorts every divergence into one of these buckets is the week's most valuable deliverable — it is the first time three independent layers of this repo (spec, mechanism, judgment) get held against each other.

## Build steps

### 1. Build the labeling workbench

Extend the previous plan's `label_workbench.py` pattern: a local browser UI showing one trace at a time — prompt, tool calls with args, results, final response — collecting labels against `schemas/human-label.schema.json` (fields above). Keep it boring: keyboard-first, append-only JSONL persistence, resumable sessions. This is plumbing in service of measurement (per [AGENTS.md](../../AGENTS.md), scaffolding like this is fine to just build) — but the label *definitions* it presents are design work, and they're yours.

### 2. Enforce the blind protocol in the tool, not in willpower

The workbench hides the `expected` block, all harness verdicts, and — on pass 2 — your pass-1 labels. If the data isn't rendered, you can't be anchored by it. Randomize row order between passes for the same reason.

### 3. Select 64 traces deliberately; label in two passes

Strata as above (every tag, all failure kinds, all gate-disagreement candidates, random fill). Two passes on different days; compute per-field test–retest agreement as your inter-rater proxy — and recruit a second labeler for a 16-row overlap subset if you can (report Cohen's κ).

### 4. Reconcile, export, and file the findings

Where pass 2 disagrees with pass 1, adjudicate with written rationale. Export the reviewed fixture to `datasets/fixtures/human-labels-64.jsonl` (schema-valid, with dataset-version and run-manifest references — the join keys). File dataset/harness bugs the labels exposed; write the findings report.

## Exercises — guided discovery

**1. Write the labeling guide first.** Before labeling row one: for every field value, a one-sentence definition plus two worked examples (one obvious, one borderline).
- *Hint 1:* The borderline examples are the guide's actual content — "correct vs defensible-alternative" is decided by your worked example, not by the adjective.
- *Hint 2:* Steal the discipline from your Week 5 taxonomy: every definition must be *decidable from the trace alone* (blind protocol — no peeking at `expected` to decide what "correct" means).

**2. Design the workbench screen.** Sketch (on paper) exactly what a labeler sees per trace, in what order, and what's hidden.
- *Hint 1:* Presentation order is a bias decision: seeing the final response before the tool calls anchors execution-quality; which order matches how you *defined* the fields?
- *Hint 2:* Where does the rationale box appear — always, or only on fail? (What does "required on every fail" imply about the UI's validation?)

**3. Build the selection matrix.** A table: stratum × target count × actual rows chosen, summing to 64, with one-line rationale per stratum.
- *Hint 1:* Start from Week 10's questions ("judge agreement on ambiguous rows") and work backward to minimum viable counts per stratum. What's too few to say anything? 
- *Hint 2:* Gate-disagreement candidates: which Week 8 report artifact lists them? If none does, that's a report gap to fix first.

**4. Compute agreement like you mean it.** Per field: raw test–retest agreement, plus κ on the overlap subset if you have a second labeler. Then interpret: which field is lowest, and what *specifically* about its definition permitted two readings?
- *Hint 1:* Expect `executionQuality` tags to be the messiest — multi-select tags have more ways to half-agree. Decide the agreement rule for tag sets before computing (exact match? per-tag?).
- *Hint 2:* If a field sits at 1.0, is the definition crisp — or is the field not discriminating anything on this fixture? (Check its value distribution before celebrating.)

**5. Sort the divergences.** For every label-vs-gate disagreement: one paragraph classifying it into the five buckets, with the evidence.
- *Hint 1:* The tell for a gate bug: the label is defensible *and* the gate's evidence payload misdescribes the trace. The tell for a label error: rereading the trace blind, you'd label differently.
- *Hint 2:* Zero genuine agent failures across 64 rows triggers the success-criteria clause: the dataset is too easy — which strata get harder rows, and what makes a row *hard* rather than merely obscure?

**6. Pre-register the fixture's limits.** Write the honest paragraph that will accompany the fixture: what these 64 rows can and cannot support.
- *Hint 1:* n per stratum bounds the per-stratum claims; single-labeler bounds the objectivity claim (test–retest ≠ inter-rater); specimen-pinned bounds generalization (labels are about *this* agent under *this* manifest).
- *Hint 2:* This paragraph gets quoted in Week 10's calibration doc — writing it now prevents over-claiming later, when the agreement numbers look exciting.

## Gotchas & drift watch

- **Fatigue is a labeling artifact.** Verdicts drift lenient (or cranky) over a long session. Fixed-size batches with breaks, and randomized order between passes, spread any drift instead of correlating it with row families.
- **`defensible-alternative` is one bad week from becoming an escape hatch.** It must mean "a reasonable agent could justify this choice on this conversation" — with the justification named in the rationale — not "I don't want to think." Watch its rate: if it exceeds the dataset's designed ambiguity share (~10–15%), suspect the definition (or the labeler's energy) before suspecting the agent.
- **Two passes need real separation.** "Different days" is the minimum; labeling pass 2 an hour later measures your short-term memory, not the definitions. Memory of *interesting* rows is the leak — another argument for randomized order.
- **Small-n humility in reporting.** 64 rows total, strata of 5–15, κ on 16: report counts alongside every percentage and resist decimal places ("14/16" carries more truth than "87.5%"). The fixture's power is its care, not its size — say so rather than dressing it up.
- **Rationales are committed text.** They ride to git with the fixture — placeholder discipline applies inside free text too (no pasting raw args/results wholesale; reference span ids and describe).
- **Budget the hours honestly.** 64 rows × 2 passes × 3–5 minutes of *actual* reading is 6–10 hours plus reconciliation. Scheduled as two half-days plus an evening, it happens; left vague, pass 2 gets skimmed and the reliability number lies.
- **Version everything the labels touch.** Fixture rows carry: dataset version, run manifest id, label-schema version, guide version, pass timestamps. Week 10 joins on these; missing keys turn calibration into guesswork.

## Deliverable checklist — Human Labeling Workflow

- [ ] Browser labeling workbench (screenshot in docs) + label schema with fixtures.
- [ ] Reviewed 64-row blind-labeled fixture with rationales.
- [ ] Reliability metrics: test–retest agreement per field (and κ on the overlap subset if second labeler).
- [ ] Findings report: label-vs-gate disagreements and what they revealed.

## Success criteria

- [ ] 64/64 rows schema-valid with rationales on every fail label.
- [ ] Test–retest agreement ≥ 0.85 on `toolSelection` (if lower, the label definitions are the bug — fix and relabel).
- [ ] At least one genuine agent failure documented from labeling (if zero, the dataset is too easy — add harder rows and say so).

## Docs to consult

This week runs on your own artifacts — the schemas are the docs.

- Your Week 5 taxonomy (`docs/tool-contract-spec.md`) — the normative source for every `errorRecovery` verdict.
- Your Week 6 schemas (`schemas/human-label.schema.json` is designed against `execution-trace.schema.json`) — labels reference traces; keep the join keys aligned.
- The previous repo's labeling workflow ([aws-ai-evals](https://github.com/rhprasad0/aws-ai-evals)) — the `label_workbench.py` pattern, blind protocol, and reconciliation format you're extending; port the lessons, not necessarily the code.
- Cohen's κ *(external, any standard statistics reference)* — understand what it corrects for before reporting it; explaining κ in one sentence is a fair interview question this repo should prepare you for.

## Self-check

1. Why does this repo refuse to let gates or judges define ground truth? State the circularity each would introduce.
2. Defend `defensible-alternative` against the charge that it makes the metric squishy — then state the monitoring rule that keeps the defense honest.
3. What, precisely, does test–retest agreement measure that a single careful pass doesn't? And what does it *fail* to measure that a second labeler would?
4. A label disagrees with a gate. Walk the five-bucket triage in order, naming the evidence that settles each branch.
5. Why must pass 2 hide pass 1's labels, when both passes are you?
6. Your κ on the 16-row overlap comes back at 0.55 while your self-agreement is 0.93. What are the two leading explanations, and which artifact does each indict?
