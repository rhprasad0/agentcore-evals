# Cost Guardrails

Week 1 cost guardrails for the AgentCore eval learning plan.

## Budget alarm

A dedicated monthly AWS Budgets cost budget is active for this learning project and managed by Terraform in `infra/terraform/budget/`:

- Budget name: `agentcore-learning-monthly-budget`
- Budget type: monthly cost budget
- Limit: `$100 USD`
- Notifications:
  - actual spend greater than 50%
  - actual spend greater than 80%
  - forecasted spend greater than 100%
- Delivery: direct AWS Budgets email notification, supplied through an ignored Terraform tfvars file.

No account IDs, ARNs, email addresses, SNS topic ARNs, or raw AWS outputs belong in this repo.

The old SNS-backed billing-alert topic was removed after AWS Budgets reported publish failures. Future alarm changes should go through the Terraform budget stack rather than manual console edits.

## Teardown habits

For deployed AgentCore weeks, treat teardown as part of the exercise, not cleanup theater.

- Before deploying, write down what will be created and what command removes it.
- After each deployed-lane session, remove idle test resources unless the week explicitly needs them to stay up.
- Prefer small pinned datasets and short smoke runs over broad repeated managed evaluation runs.
- Keep raw traces, managed eval outputs, and AWS console receipts private unless they are explicitly scrubbed.
- If a future week uses AgentCore CLI deployment, start with the current CLI help and use the matching teardown command from the installed version rather than trusting stale docs.

## Current Week 1 status

The Week 1 budget-alarm success criterion is satisfied. The remaining cost habit is procedural: keep teardown notes next to each future deployed artifact.
