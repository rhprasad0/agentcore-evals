terraform {
  required_version = ">= 1.11"

  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.53, < 7.0"
    }
  }
}

variable "aws_region" {
  description = "AWS Region for the final production-demo resources."
  type        = string
  default     = "us-east-1"
}

provider "aws" {
  region = var.aws_region
}
