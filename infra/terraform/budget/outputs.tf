output "budget_name" {
  description = "Managed AWS Budgets budget name."
  value       = aws_budgets_budget.agentcore_learning.name
}

output "budget_limit" {
  description = "Managed monthly budget limit."
  value       = "${aws_budgets_budget.agentcore_learning.limit_amount} ${aws_budgets_budget.agentcore_learning.limit_unit}"
}
