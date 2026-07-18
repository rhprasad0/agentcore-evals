# Week 14 — Same-Evidence Managed Evaluation and CI

**Prerequisite:** One immutable Runtime version has passed STAGING and been explicitly promoted to PROD; Week 9 human gold and Week 10's custom-judge contract remain frozen.

[← Week 13](week-13-runtime-operations.md) · [Week index](README.md) · [Next: Week 15 →](week-15-hosted-demo.md)

## Concept

A fair comparison holds evidence constant. Collect the six behavior-eligible STAGING traces once, then make the frozen custom judge and AgentCore's two tool-level built-ins evaluate those exact spans. The two infrastructure-denial rows stay in the joined report as `not_eligible` and never enter tool-accuracy denominators.

CI has two sharply separated jobs: a cloud-free pull-request gate over committed evidence, and one manual, spend-confirmed GitHub OIDC job for the metered same-evidence comparison. The manual job cannot deploy, mutate AgentCore, read the Identity key, or run on a schedule.

## Build

### 1. Capture the six final Runtime traces once

Run `slice-01` through `slice-06` against the Week 13 STAGING endpoint pinned to the exact immutable version promoted to PROD. For each case, record:

- human-gold case ID;
- Runtime and artifact version;
- session and trace IDs;
- target tool span IDs; and
- normalized selection, parameters, and intermediate-value evidence.

Validate exact case-set equality and uniqueness. These captured spans are the sole evidence for both automated lanes; do not regenerate between judges or substitute anonymous PROD traffic.

### 2. Define one same-evidence orchestration command

Create `scripts/run_agentcore_managed_eval.py`. It loads exactly the six captured references, invokes the frozen `judge_weather_calculator.py` contract once, then sends the corresponding tool span IDs to AgentCore Evaluations with:

- `Builtin.ToolSelectionAccuracy`
- `Builtin.ToolParameterAccuracy`

Keep `slice-07` and `slice-08` in the output with human boundary verdicts and explicit custom/managed `not_eligible` values. The joined report has one row per case and shows evaluation kind, eligibility, human/boundary verdict, custom verdict, both managed results, and compact disagreement notes.

Do not execute this model-backed path from a developer shell. Dry validation may prove joins and render requests; the one metered execution belongs to the manual job.

### 3. Add one offline workflow and one manual OIDC job

Create `.github/workflows/eval-demo.yml`. On pull requests, run only:

1. the Week 8 fixture-backed Stage B command;
2. deterministic replay of six behavioral cases plus eligibility/receipt checks for two denials; and
3. exactly the three Week 12 reliability tests.

The pull-request job has no AWS/model path.

Add a separate `workflow_dispatch` job with `permissions: id-token: write`, an explicit managed-spend confirmation input, and no stored AWS keys. Manage its least-privilege role in `github_oidc.tf`; reuse the account's GitHub OIDC provider as external data if it already exists. Restrict trust to this repository and approved environment/ref.

The job accepts exactly six unique case/trace/span references, runs the custom and managed lanes once, and uploads only the sanitized joined report. Its role may read those named STAGING spans and invoke only the selected judge/evaluation APIs. The workflow never runs Terraform apply.

### 4. Execute once and report honestly

After reviewing expected spend, run the manual job once. Create `docs/reports/week-14-managed-evaluation.md` with eight rows, counts over the six eligible rows, every human/custom/managed disagreement, evaluator IDs/dates, Runtime identity, and transport details.

Do not infer calibration, stability, or false rates from six examples. A perfect six-of-six result still means only that the lanes agreed on this worked example.

### 5. Prove the pull-request gate is alive

Temporarily introduce one model-visible or expected-sequence defect. Capture the failed job and named gate, restore only that defect, and capture green. Keep `docs/reports/week-14-red-gate.md` and `docs/assets/week-14-red-gate.png`; do not retain a broken branch or build a new test framework.

## Deliverable

One same-evidence/CI artifact group:

- `scripts/run_agentcore_managed_eval.py`
- `.github/workflows/eval-demo.yml`
- `infra/terraform/production-demo/github_oidc.tf`
- `docs/reports/week-14-managed-evaluation.md`
- red/green gate receipt

There is no nightly managed lane, custom managed evaluator, broad threshold tuning, or extra test file.

## Success check

The frozen custom judge and both AgentCore built-ins evaluate the same six Runtime spans exactly once; the joined report compares every result with human gold and exposes every disagreement; the offline pull-request workflow is red for one seeded defect and green after restoration; and the manual job authenticates through repository-scoped OIDC with no long-lived GitHub secret.

## Read

- [AgentCore on-demand evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-on-demand.html)
- [AgentCore dataset evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations-on-demand.html)
- [Built-in evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-evaluators-overview.html)
- [GitHub OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Managed evaluation boundaries](../../LEARNING_PLAN.md#managed-evaluation-boundaries-read-before-week-8)