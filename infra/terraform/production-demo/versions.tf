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

variable "openweather_api_key" {
  description = "OpenWeather API key supplied only to AgentCore Identity's write-only field."
  type        = string
  sensitive   = true
  ephemeral   = true
  nullable    = false
}

variable "openweather_api_key_version" {
  description = "Non-secret version incremented whenever the write-only API key rotates."
  type        = number
  default     = 1
}

provider "aws" {
  region = var.aws_region
}
