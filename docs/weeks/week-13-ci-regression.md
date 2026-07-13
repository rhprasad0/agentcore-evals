# Week 13 — Production Agent CI Regression

**Phase:** Complexity under contract (Weeks 11–13) · **Specimen:** the deployed chain agent, now guarded by CI
**Lanes touched:** platform & CI (primary), managed eval lane (batch evaluation enters the pipeline)
**Prerequisites:** Week 12 exit gate closed — resilience gates green, real APIs wired, write action idempotent.

[← Week 12](week-12-reliability-gates.md) · [Week index](README.md) · [Next: Week 14 →](week-14-observability.md)

---

## Objective

A deployed chain agent with a two-lane CI regression pipeline — fast deterministic fixtures on every PR, managed batch evaluation against the deployed agent on merge/nightly — and a preserved red-gate receipt of a caught tool-selection regression.

## Why this week exists

The previous plan's most persuasive artifact was a screenshot of CI failing for the right reason. Same move, bigger claim: changes to prompts, tool descriptions, or the portfolio cannot silently regress tool selection, because committed fixtures and score thresholds stand in the way.

The philosophy underneath: **a gate that has never fired is decoration.** Anyone can add a green checkmark to a repo; the credible artifact is evidence the checkmark *turns red when it should* — which is why this week deliberately seeds a regression and preserves the receipt. A regression pipeline is a claim about counterfactuals ("bad changes get caught"), and counterfactual claims need at least one demonstrated instance to be believed. You are building the gate *and* the proof the gate is alive.

## Concepts

### Two lanes, two questions, two cost profiles

The pipeline splits along the line Week 8 drew (stage A/B), now formalized:

| | **Lane 1 — every PR** | **Lane 2 — merge to main / nightly** |
| --- | --- | --- |
| Question | "Did this change break known-good behavior *mechanically*?" | "Does the *deployed* agent still score above calibrated thresholds?" |
| Runs | Repo dataset validation → safety scan → unit tests → Strands Experiment validation → custom gates over committed public-safe regression traces through an offline task → report | Invoke deployed agent over pinned prompts → normalize traces → batch evaluation (managed + own judge) → threshold check |
| Time / cost | Minutes, free (no cloud calls) | Tens of minutes, real money (invocations + judge tokens) |
| Threshold | **100%** on regression rows | Calibration-derived score floors (see below) |
| Failure meaning | A specific pinned behavior changed — the evidence payload names it | Deployed quality drifted — triage begins (agent? evaluator? environment?) |

The asymmetry is deliberate. Lane 1 must be fast enough that you *never* skip it (the success criterion says < ~5 minutes; slow gates get skipped, then deleted). Lane 2 is allowed to be slow and metered because it runs on merges and schedules, not on every keystroke.

### Regression fixtures: memorials to caught bugs

The ~30 rows in `datasets/fixtures/regression/` are not a random dataset sample. Selection criteria, in priority order:

1. **Rows that have already caught something** — the Week 8 sensitivity check, Week 9's genuine agent failure, Week 11's regression investigation. A regression test is a memorial to a real bug; rows with a track record have proven they discriminate.
2. **Stability on mocks** — lane 1's threshold is 100% *because* these rows must not flake. A row that passes 49 of 50 runs is a good eval row and a terrible regression fixture; if one flakes, fix or replace the row — never lower the threshold.
3. **Coverage span** — single-tool, chain, no-tool, and failure-injection all represented, so the gate guards every behavior family the plan has certified, with pinned expected behavior per row.

Commit the selection rationale next to the fixtures. "Why these 30" is the difference between a curated gate and a cargo-culted one.

### Thresholds trace to Week 10, not to round numbers

Lane 2 fails the workflow if scores drop below floors — but *which* floors? The plan's rule: thresholds derive from Week 10's calibration, not from air. The reasoning chain you should be able to recite: your judge (and each built-in) has a measured agreement and flip rate against the human fixture; that variance defines the noise band around any score; a threshold is defensible when a breach is *distinguishable from judge noise* at your sample size. A worked example of the shape (numbers are yours to derive): if `Builtin.ToolSelectionAccuracy` scored ~0.9 on your calibrated baseline with a per-run spread you measured, a floor one full noise-band below baseline catches real regressions without paging you for weather. Write the derivation memo; Exercise 3 holds you to it.

### The managed lane's mechanics (verified 2026-07-08)

Batch evaluation, like on-demand, **discovers sessions from CloudWatch Logs** — it scores what the deployed agent actually did. The working shapes:

```bash
agentcore run batch-evaluation \
  --runtime weather-chain-agent \
  --evaluator Builtin.ToolSelectionAccuracy Builtin.ToolParameterAccuracy Builtin.GoalSuccessRate \
  -n nightly_regression --wait --json
```

`--wait` blocks to a terminal state and prints per-evaluator averages; `--json` emits machine-readable results (including `batchEvaluationId` and per-evaluator `averageScore`) — that JSON is what your threshold step parses. History and inspection: `agentcore batch-evaluations history`, `agentcore view batch-evaluation <id>`. The boto3 path (`bedrock-agentcore` client: `start_batch_evaluation` / `get_batch_evaluation`, statuses `COMPLETED` / `COMPLETED_WITH_ERRORS` / `FAILED` / `STOPPED`, results under `evaluationResults.evaluatorSummaries[].statistics`) is the CI-friendly alternative if the workflow needs finer control.

Sequencing consequence for lane 2: **invoke first, then wait, then evaluate.** The pinned prompt set runs against the deployed agent; spans must land in CloudWatch and sessions must be *complete* before batch evaluation can discover them — build in the propagation delay rather than debugging phantom "0 sessions found" failures at 2 a.m. And record evaluator IDs + dates in the run manifest, as always: lane 2's runbook must handle "the evaluator changed underneath us."

### CI auth: OIDC, or you've committed a key with extra steps

Lane 2 needs AWS access from GitHub Actions. The only acceptable pattern here is **OIDC federation** — the workflow assumes a scoped IAM role via GitHub's OIDC provider; no long-lived access keys in repository secrets. The role's policy is another Week 5-style least-privilege exercise: invoke the runtime, start/read batch evaluations, read the results log groups — and nothing else. (Your public repo's CI config will be read by strangers; it should demonstrate the discipline the README claims.)

### The seeded regression: prove the gate fires

Build step 4 is the week's signature move. Open a PR that *plausibly innocently* breaks tool selection — the plan's example: "improve" the weather tool description to also claim forecasts (a one-line docstring edit any well-meaning contributor might ship — and precisely the description-is-behavior lesson from Weeks 2 and 5). Then: watch the pipeline go red, screenshot the failure *with its evidence payload visible*, revert, and write the incident up in `docs/reports/`. The receipt must show the gate caught it — not you eyeballing the diff. If the seeded change *passes*, that's a more important finding: your fixtures don't guard the behavior you thought, and the fix (better rows) happens now, cheaply, instead of after a real regression ships.

## Build steps

### 1. Deploy and freeze the fixtures

Deploy the Week 12 agent via `agentcore deploy` (config in repo; observability enabled). Freeze `datasets/fixtures/regression/`: ~30 rows spanning single-tool, chain, no-tool, and failure-injection cases, each with pinned expected behavior — chosen from rows that have *already caught something*, with the selection rationale committed.

### 2. Build lane 1 (`ci.yml`, every PR)

Repo dataset/contract validation → safety scan → unit tests → validate the derived Strands Experiment → run custom evaluators over committed public-safe regression traces through a fixture-loading `--task` → render/upload the flattened report → thresholds (tool-selection gate pass rate = 100% on regression rows; they're regression rows *because* they must not flake). Use `--fail-on any`. Do **not** use `--agent` in the PR lane: it would invoke the model, violating the lane's cloud-free contract. Do not depend on a developer-local task-result cache; CI fixtures are reviewed, pinned artifacts.

### 3. Build lane 2 (merge to main / nightly)

Invoke the *deployed* agent over the pinned prompt set, normalize fresh traces, then run AgentCore batch evaluation over them with the calibrated evaluator set (`Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, goal success) plus your own judge; fail the workflow if scores drop below the Week 10-informed thresholds. Post the score table as a job summary.

### 4. Prove the gate is alive

The seeded-regression PR: innocent-looking description edit → red gate → screenshot → revert → incident report in `docs/reports/`. Preserve everything; this receipt is a capstone artifact.

## Exercises — guided discovery

**1. Curate the thirty.** Build the fixture set with a rationale table: row id, family, what it caught (or why it's here), stability evidence.
- *Hint 1:* Mine your own history: the Week 8 sensitivity note, Week 9's findings report, Week 11's regression investigation — each names candidate rows.
- *Hint 2:* Run the candidates 10× on mocks before freezing. Any row that isn't 10/10 identical is auditioning for the dataset, not the regression gate.

**2. Stand up OIDC with a role you'd defend.** GitHub OIDC provider → scoped role for lane 2.
- *Hint 1:* Which repo/branch conditions go in the trust policy so a fork's workflow can't assume your role?
- *Hint 2:* Enumerate lane 2's actual AWS calls (invoke, start/get batch evaluation, read result logs) and write the policy from the enumeration — the Week 5 denial-receipt pattern applies: prove one out-of-scope action is denied.

**3. Write the threshold memo.** From Week 10's calibration numbers to lane 2's floors, with the arithmetic shown.
- *Hint 1:* What's the observed run-to-run spread of each evaluator on your fixed baseline? A floor inside that band pages you for noise; how far outside is far enough at n≈30 sessions?
- *Hint 2:* Averages dilute: one catastrophic session in thirty moves the mean ~3 points. Does your floor catch "one row went badly wrong," or do you need a per-session minimum too? Decide and justify.

**4. Design the seeded regression before running it.** Predict, in writing: which lane fires, which gate within it, and what the evidence payload will say.
- *Hint 1:* A forecast-claiming description should change selection on which fixture rows — the forecast-adjacent no-tool rows? Trace the causal path from docstring to gate verdict.
- *Hint 2:* If your prediction is "lane 2 catches it but lane 1 doesn't," what fixture row is missing from lane 1? Add it *before* the experiment and see if the prediction changes.

**5. Make the job summary answer the reviewer's question.** Render lane 2's score table (and lane 1's gate results) as a GitHub Actions job summary.
- *Hint 1:* The reviewer's question is "safe to merge?" — what three numbers answer it, and what belongs behind a details-fold instead?
- *Hint 2:* Include the manifest fields (evaluator IDs, dataset version, deployed agent version) — a score table without provenance can't be compared to last week's.

**6. Drill the runbook.** Write `docs/` runbook entries for each failure mode, then dry-run the hardest one: "managed evaluator changed underneath us."
- *Hint 1:* What observable distinguishes "our agent regressed" from "AWS's judge changed"? (Your own judge scored the same traces — what does *its* trend say? This is why lane 2 runs both.)
- *Hint 2:* The re-baseline procedure: which artifacts get re-run, which thresholds get re-derived, and what gets a dated entry where?

## Gotchas & drift watch

- **Lane 2 is metered — schedule accordingly.** Nightly + on-merge, never per-PR; pinned prompt set, not the full corpus. The cost guardrails ([Working assumptions](../../LEARNING_PLAN.md#working-assumptions)) treat batch evals as "pinned small datasets, not everything-always."
- **Strands CLI failures have different meanings.** Preserve exit code `1` (evaluation threshold/failure), `2` (bad input, experiment, or custom-evaluator registration), and `3` (unexpected runtime error) in the runbook and job summary. Only code `1` is evidence that the agent violated a gate.
- **No raw Evals cache uploads.** `--data-store` is disabled in the PR lane or points to ephemeral storage that is never uploaded. The flattened report must pass the public-safety scan before artifact upload; full cached `EvaluationData` remains private.
- **Span propagation is the phantom failure.** Between `agentcore invoke` and batch evaluation discovering the session, spans must reach CloudWatch and the session must close. Poll or sleep deliberately; document the observed delay in the runbook the first time it bites.
- **Deploy freshness:** lane 2 must test what merged. Either lane 2 deploys before invoking, or it verifies the deployed version matches `main` (manifest/version check) — a nightly lane silently testing last Tuesday's deploy produces confident nonsense either way.
- **Two judges disagreeing in lane 2 is signal, not breakage.** Your judge and the built-ins were calibrated with known disagreement patterns (Week 10's casebook). The runbook's triage uses that: both drop → believe it; only the built-in drops → suspect evaluator drift; only yours drops → suspect your judge's sensitivity. Write this into the runbook now, while the reasoning is fresh.
- **Don't let the seeded PR merge.** Obvious, but: do the experiment on a branch, label the PR clearly (`[seeded-regression-experiment]`), revert cleanly, and make the incident report link the PR. A stranger reading the history should understand it was a drill.
- **CLI surface for batch evals verified 2026-07-08** (`run batch-evaluation`, `batch-evaluations history`, `view batch-evaluation`, `stop batch-evaluation`; `--wait`, `--json`, `-n`). This corner is new; re-check `--help` when wiring and prefer the boto3 path in CI if flags drift.

## Deliverable checklist — CI/CD Regression Pipeline

- [ ] Deployed agent + committed regression fixtures with selection rationale.
- [ ] `ci.yml`: PR lane + deployed/batch-eval lane with thresholds and score-table summaries.
- [ ] **Red-gate receipt:** screenshot + written incident report of the caught regression.
- [ ] Runbook: what to do when each lane fails (including "the managed evaluator changed underneath us").

## Success criteria

- [ ] PR lane completes fast enough that you never skip it (< ~5 min).
- [ ] The seeded regression was caught by the pipeline, not by you eyeballing (receipt proves which gate fired).
- [ ] Batch-eval thresholds trace to Week 10 calibration, not round numbers pulled from air.

## Docs to consult

Verified via the AWS docs MCP server, 2026-07-08, except where marked external.

- [Getting started with batch evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-getting-started.html) — CLI and boto3 invocation shapes, session discovery from CloudWatch, result formats; lane 2's spine.
- [Strands Evals CLI](https://strandsagents.com/docs/user-guide/evals-sdk/cli/) — lane 1's offline `--task` entry point, custom evaluator registration, `--fail-on` policy, report JSON, and exit-code contract; verify flags against the exact pinned version.
- [Get batch evaluation results](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-get.html) — polling, terminal states, `evaluatorSummaries` result structure; what your threshold step parses.
- [AgentCore pricing — Evaluations](https://aws.amazon.com/bedrock/agentcore/pricing/) — what lane 2 costs per run; the input to your scheduling decision.
- [GitHub Actions: OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) *(external)* — the keyless auth pattern for lane 2; pair with your Week 5 least-privilege discipline.
- [Get started with the AgentCore CLI (Runtime path)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) — `agentcore invoke` scripting for the pinned prompt battery.

## Self-check

1. State each lane's question, cost profile, and threshold philosophy — and why lane 1's threshold is 100% while lane 2's isn't.
2. Why must regression fixtures be chosen from rows that already caught something? What's wrong with sampling 30 random dataset rows?
3. Walk the causal chain of the seeded regression: docstring edit → what changes in the model's world → which behavior shifts → which gate's evidence payload names it.
4. Lane 2 fails tonight: `Builtin.ToolSelectionAccuracy` dropped 6 points, your own judge's score is flat. Triage out loud.
5. Why does lane 2 invoke-then-wait-then-evaluate, and what failure mode does skipping the wait produce?
6. What, verbatim-ish, does your threshold memo say a 4-point average drop *means* at your sample size — signal or noise, and by what arithmetic?
