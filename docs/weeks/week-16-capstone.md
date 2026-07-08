# Week 16 — Production Agent Architecture Reference

**Phase:** Production & orchestration (Weeks 14–16) · **Specimen:** the whole system, drawn as it actually is
**Lanes touched:** all five converge — this is the week they were converging toward
**Prerequisites:** Week 15 exit gate closed — coordination measured, boundaries probed, receipts filed.

[← Week 15](week-15-multi-agent-safety.md) · [Week index](README.md)

---

## Objective

Close the loop: the complete deployed system with public demo, documented metrics, an eval-driven improvement pipeline — including the managed performance loop run under holdout discipline — and the LinkedIn-ready case study.

## Why this week exists

The capstone claim is deliberately narrow and therefore credible: *a tool-calling agent system whose selection accuracy, reliability, and safety boundaries are continuously measured, with receipts.* The previous plan ended by rejecting a managed optimizer that failed its holdout; this one ends by giving AgentCore's optimization loop the same fair trial.

Narrowness is the strategy, so guard it this week especially. Sixteen weeks of artifacts create pressure to claim more — "production-ready," "safe," "state of the art." Every one of those words is a check the evidence can't cash, and one inflated sentence discredits sixty honest ones. The honest sentence is always available: **"measured X on Y under Z"** ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)). The audience that matters — a hiring engineer reading skeptically — is more impressed by a scoped claim with receipts than by an unscoped claim with vibes; the entire portfolio bet of this repo rides on that asymmetry.

## Concepts

### Draw the architecture as it is, not as intended

The reference diagram is generated *from evidence* — configs and traces, not aspiration: what `agentcore status` reports deployed, what the CDK/config files declare, what Policy engines attach to which gateways, where traces actually flow. One Mermaid diagram, one page of honest annotations — including the load-bearing distinction between **demo-grade** (works, demonstrated once, would need hardening) and **production-grade** (gated, monitored, receipt-backed) for each component. That annotation column is the credibility mechanism: a diagram where everything is presented as equally solid reads as marketing; one that says "the notify path is demo-grade — idempotent but single-region, no DLQ" reads as engineering.

### The performance loop, on your terms

AgentCore optimization (verified 2026-07-08) closes the managed loop this plan has been circling since Week 10. Its verified shape:

- **Insights** (failure / intent / trajectory — preview) mine production traces across sessions: recurring failure patterns with root-cause explanations ranked by user impact; requests clustered by actual intent; trajectory patterns and outliers.
- **Recommendations** generate improved system prompts / tool descriptions from your traces and a *target evaluator*, with rationale tied to observed failures. Every recommendation requires approval — nothing self-applies.
- **Configuration bundles** — versioned, immutable snapshots of agent configuration (system prompt, model ID, tool descriptions) that change deployed behavior *without redeployment*. Optional; a separate runtime endpoint is the alternative.
- **A/B testing** splits traffic between variants through Gateway, scores each side with online evaluation, and reports statistical significance before you commit.

Now the posture this repo brings to it: **the managed loop is an optimizer, and optimizers face holdouts** ([Appendix C](../../LEARNING_PLAN.md#appendix-c--guardrails)). The service validates its own recommendations with batch evaluation — good — but against *whose* rows? If the validation set overlaps the traces the recommendation was mined from, or the rows you tuned judges and fixtures against all plan long, the validation is partially circular. Your experiment design:

1. **Freeze a holdout split first** — rows never used for tuning anything: not judge-prompt iteration (Week 10), not regression-fixture selection (Week 13), not the traces recommendations mine. Auditing that "never" is Exercise 2, and it's harder than it sounds after fifteen weeks of reuse.
2. **Take one proposed change** — a recommended system prompt or tool description. One, so the result is attributable.
3. **Evaluate it twice** — managed batch evaluation *and* your own harness, on the holdout.
4. **Adopt only if** it beats baseline on holdout *without regressing safety/no-tool rows* — the regression clause matters because optimizers chase the target evaluator, and "more helpful" changes have historically bought their gains by tool-calling more eagerly. Your no-tool rows are the canary for exactly that trade.
5. **Publish the decision with numbers either way.** A documented rejection is as portfolio-worthy as an adoption — the previous plan's rejection was its most-cited artifact. The deliverable is the *decision quality*, not the adoption.

One integrity note to handle in writing: **configuration bundles change deployed behavior without a git commit**, which strains this repo's "the repo is the source of truth" principle (Week 3). Reconcile explicitly — bundle versions recorded in run manifests and a repo-committed registry of active bundle versions — or decline bundles and deploy variants to separate endpoints. Either is defensible; silence isn't.

### The public demo: thin by design

A thin, rate-limited, prompt-scoped web front end on the deployed agent. Each adjective is a decision:

- **Thin** — the front end holds no logic worth attacking; it forwards scoped prompts and renders responses. The agent, Policy, and Gateway do the real enforcement (Week 15's boundaries are now internet-facing and will be probed by strangers — that's what they're for).
- **Rate-limited** — per-IP/session caps, plus the Week 1 budget alarm and a documented kill switch. The demo runs while you sleep; its worst day must be a bounded-cost day.
- **Prompt-scoped** — the agent's manifest and out-of-scope declarations (Week 5) already say what it won't do; the demo UI should say so too, so refusals read as design rather than failure.

The Week 12 degradation story is your outage insurance: when OpenWeatherMap has a bad day during someone's visit, the agent saying "weather data is currently unavailable; here's what still works" *is the demo* — the success criterion literally requires surviving an induced outage in public without fabricating data.

And the **metrics page** ships the receipts: tool-selection accuracy (harness + online), parameter accuracy, execution success rate, judge-agreement summary, red-gate history — each number generated from committed artifacts (no hand-typed numbers; a stale hand-typed metric is a small lie waiting to age) and linked to its receipt within two clicks, per the success criteria.

### The case study writes itself — because you already wrote it

The eval-first arc (contract → dataset → harness → labels → judges → gates → production loop), three failures the process caught *with receipts*, the judge trust policy, and what you'd do differently. Your `docs/reports/` history is the draft: the Week 8 sensitivity note, Week 9's findings, Week 10's disagreement casebook, Week 13's red-gate incident, Week 15's probe report, this week's adopt/reject memo. The writing task is selection and narrative, not recollection — which is exactly why the plan made you file reports weekly. Post it; pin the repo; the "what I'd do differently" section is the one hiring managers read twice, so write it with real regrets, not humble-brags.

## Build steps

### 1. Assemble the reference architecture and draw it as it is

From configs and traces, not aspiration: Strands agents on Runtime, tools via Gateway with Policy + guardrails, Identity-managed credentials, Memory where used, OTEL → CloudWatch with online evals, two-lane CI, and the custom eval stack around it all. One Mermaid diagram, one page of honest annotations, including what's demo-grade vs production-grade.

### 2. Run the managed performance loop as a gated experiment

Enable insights/recommendations over accumulated production traces; take one proposed change (system prompt or tool description); evaluate with batch evaluation *and* your harness on the frozen holdout split; adopt only if it beats baseline on holdout without regressing safety/no-tool rows. Publish the accept/reject decision with numbers either way.

### 3. Ship the public demo and metrics page

Thin, rate-limited, prompt-scoped front end on the deployed agent (the Week 12 degradation story is your outage insurance), plus a metrics page sourced from real eval receipts: tool-selection accuracy (harness + online), parameter accuracy, execution success rate, judge-agreement summary, and the red-gate history.

### 4. Write and publish the case study

The eval-first arc, three failures the process caught with receipts, the judge trust policy, and what you'd do differently. Post it; pin the repo; update the README front page to capstone state.

## Exercises — guided discovery

**1. Generate the component inventory before drawing.** From `agentcore status`, the CDK/config files, Policy configs, and CI workflows: a machine-derived list of everything deployed and every connection. Then draw the diagram *from the list* and diff against what you believed.
- *Hint 1:* Anything in the diagram but not the inventory is aspiration; anything in the inventory but not your mental model is drift. Both are findings.
- *Hint 2:* The demo-grade/production-grade annotation: for each component, what's the *one* missing thing that keeps it from the higher grade? Naming it precisely is the annotation.

**2. Audit the holdout's virginity.** Before freezing the split, trace each candidate row's usage history across Weeks 8–15.
- *Hint 1:* The contamination paths, in rough order of sneakiness: regression-fixture membership (W13), judge-prompt iteration exposure (W10 — did you eyeball this row while tuning?), errata edits driven by agent behavior (W7), and now: will the recommendation engine mine traces that *include* holdout-row replays?
- *Hint 2:* Your run manifests and fixture rationale tables are the audit trail — this exercise is the payoff for keeping them. Rows you can't clear, you don't use; document the survivor count honestly.

**3. Pre-register the optimizer trial.** Before generating any recommendation: the target evaluator, the holdout metrics that decide, the adoption threshold, and the regression clauses (safety/no-tool floors).
- *Hint 1:* Pre-registration is what makes the eventual memo unimpeachable — the decision rule existed before the candidate did. Where does the pre-registration get committed?
- *Hint 2:* What does the recommendation *optimize for* (your chosen target evaluator) vs what do you *care about*? Any daylight between them is exactly where the regression clauses must sit.

**4. Threat-model the demo for one hour.** Rate limits, prompt scope, injection attempts, cost bombs, content the front end might render unsafely.
- *Hint 1:* Which Week 15 boundary handles each: off-manifest tool requests (Policy), injection in user input (Guardrails + your canary experience), runaway sessions (loop budgets, rate limits)? The demo mostly *routes to* existing defenses — the new surface is the front end itself.
- *Hint 2:* The kill switch: what exactly does it disable, how fast, and how do you test it without taking the demo down? (Pause the online-eval config too — Week 14's faucet discipline.)

**5. Wire the metrics page to receipts.** For each published number: the generating artifact, the link path, and the regeneration command.
- *Hint 1:* "Two clicks from claim to receipt" is the success criterion — walk it as a stranger: metric → report → committed artifact. Where does the chain break?
- *Hint 2:* Numbers that regenerate on CI stay honest; numbers pasted into HTML rot. Which of your metrics can't currently be regenerated by a command — and is that fixable this week or disclosed as a limitation?

**6. Draft the case study's failure gallery.** Choose the three failures the process caught, each with: what happened, which layer caught it, the receipt link, and what changed because of it.
- *Hint 1:* Strongest gallery spans layers: one caught by deterministic gates, one by human labels or judge disagreement, one by CI/policy in something like production. Your candidates: the Week 9 genuine failure, the Week 13 red gate, a Week 15 denial — but check your reports for better ones.
- *Hint 2:* The narrative discipline: each failure story ends with the *system* change (a gate, a row, a policy), not the *fix*. The process improving is the thesis; the bug was just the occasion.

## Gotchas & drift watch

- **Feature availability is split (verified 2026-07-08):** batch evaluations, recommendations, and A/B tests are GA; failure/intent/trajectory *insights* are preview, in fewer Regions. Confirm what's enabled in `us-east-1` for your account before scheduling the loop experiment — preview features also change shape without much notice.
- **A/B significance needs traffic you may not have.** Statistical significance over split live traffic assumes session volume a portfolio demo won't generate. Honest options: run the A/B over scripted traffic and say so, or report the power limitation and lean on the batch-eval + holdout verdict. An underpowered A/B presented as significant would be the one dishonest number on your metrics page — don't.
- **Config bundles vs repo-as-truth** — resolve the tension explicitly (bundle-version registry in git, or no bundles). A behavior change nobody can find in history is this repo's cardinal sin, even when a managed service does it politely.
- **The optimizer's gains have a known failure mode:** target-evaluator improvements bought by regressing restraint (no-tool rows) or safety behavior. Your regression clauses exist because of this pattern — if the recommendation wins the target and loses restraint, the memo's rejection paragraph is already half-written.
- **Demo teardown has a new meaning now.** Weeks 3–15 tore down after sessions; a public demo *stays up*, which makes the budget alarm, rate limits, and kill switch the teardown-equivalents. Decide the demo's planned lifetime and end-of-life procedure now, in writing — "quietly rots for a year, then embarrasses you" is the default you're overriding.
- **Don't retune anything this week.** The capstone measures the system as Weeks 1–15 left it (plus at most one adopted recommendation). Late tweaks invalidate baselines and can't be re-receipted in time; the improvement backlog goes in "what I'd do differently," where it earns interview conversation instead of costing credibility.

## Deliverable checklist — Production Reference Architecture

- [ ] Reference architecture doc + diagram matching deployed reality.
- [ ] Performance-loop experiment report: proposal, holdout design, verdict with numbers.
- [ ] Public demo (scoped, rate-limited) + metrics page fed by real eval artifacts.
- [ ] LinkedIn case study published; README front page updated to capstone state.

## Success criteria

- [ ] Fresh-clone reader reaches any claimed metric's receipt within two clicks.
- [ ] The optimization adopt/reject decision is defensible from published holdout numbers alone.
- [ ] The demo survives an induced tool outage in public without fabricating data.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-08.

- [AgentCore optimization: recommendations and A/B tests](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html) — the loop's verified mechanics: recommendations, configuration bundles, A/B testing, insights; the source for build step 2's invocation shapes.
- [Getting started with batch evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-getting-started.html) — re-used from Week 13 for the holdout validation runs.
- [Optimization capabilities announcement (2026-06)](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-bedrock-agentcore-new-optimization-capabilities/) — the GA/preview split and Region counts; check against your account.
- [AgentCore FAQs — optimization](https://aws.amazon.com/bedrock/agentcore/faqs/) — the capability boundaries in AWS's own words (useful when scoping what you claim the managed loop did).
- Your entire `docs/reports/` history — the case study is mostly already written; this is the week that cashes fifteen weeks of receipt discipline.

## Self-check

1. Recite the capstone claim in one sentence, then list three adjacent claims it deliberately does *not* make.
2. Why must the holdout predate the recommendation? Name the two circularities it breaks — one about the optimizer, one about your own fixtures.
3. The recommendation improves goal success by 6 points on holdout and no-tool compliance drops 8. Write the decision memo's verdict sentence.
4. How do configuration bundles threaten this repo's provenance discipline, and what's your chosen reconciliation?
5. What makes a documented rejection portfolio-worthy? Who is the audience that values it, and what does it prove that an adoption wouldn't?
6. A stranger challenges your metrics page: "how do I know these numbers are real?" Walk their two clicks for tool-selection accuracy.
7. Sixteen weeks later: state the difference between what this system *is* and what it *proves* — in the plan's own vocabulary.
