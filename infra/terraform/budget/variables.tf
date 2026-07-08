variable "aws_region" {
  description = "AWS Region used for provider API calls. AWS Budgets is account-scoped, but us-east-1 is the standard billing-control region for this repo."
  type        = string
  default     = "us-east-1"
}

variable "budget_name" {
  description = "Name of the monthly AWS Budgets cost budget for this learning project."
  type        = string
  default     = "agentcore-learning-monthly-budget"
}

variable "monthly_limit_usd" {
  description = "Monthly budget limit in USD."
  type        = string
  default     = "100.0"
}

variable "notification_email" {
  description = "Email address for AWS Budgets direct email notifications. Store this in an ignored tfvars file, not in git."
  type        = string
  sensitive   = true
}
