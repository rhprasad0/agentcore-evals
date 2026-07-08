# Budget Terraform

Terraform for the AgentCore learning-plan cost alarm.

## What it manages

- `agentcore-learning-monthly-budget`
- Monthly cost limit: `$100 USD`
- Direct AWS Budgets email notifications at:
  - actual spend > 50%
  - actual spend > 80%
  - forecasted spend > 100%

The notification email is intentionally supplied through an ignored `*.tfvars.json` file. Do not commit email addresses, account IDs, ARNs, SNS topics, Terraform state, or Terraform plans.

## Typical commands

```bash
cd infra/terraform/budget
terraform init
terraform plan
terraform apply
```

If this budget already exists from a manual setup, import it before the first apply:

```bash
terraform import aws_budgets_budget.agentcore_learning <AWS_ACCOUNT_ID>:agentcore-learning-monthly-budget
```

Use the real account ID only in the terminal command, not in committed docs.
