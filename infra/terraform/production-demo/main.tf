data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  gateway_name               = "production-weather"
  target_name                = "openweather"
  current_weather_action     = "${local.target_name}___get_current_weather"
  forecast_action            = "${local.target_name}___get_forecast"
  workload_identity_base_arn = "arn:${data.aws_partition.current.partition}:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default"
  token_vault_base_arn       = "arn:${data.aws_partition.current.partition}:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:token-vault/default"
}

data "aws_iam_policy_document" "gateway_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name               = "production-weather-gateway"
  assume_role_policy = data.aws_iam_policy_document.gateway_assume_role.json
}

resource "aws_bedrockagentcore_api_key_credential_provider" "openweather" {
  name               = "production_weather_openweather"
  api_key_wo         = var.openweather_api_key
  api_key_wo_version = var.openweather_api_key_version
}

resource "aws_iam_role_policy" "gateway" {
  name = "production-weather-gateway"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetGatewayWorkloadAccessToken"
        Effect = "Allow"
        Action = "bedrock-agentcore:GetWorkloadAccessToken"
        Resource = [
          local.workload_identity_base_arn,
          "${local.workload_identity_base_arn}/workload-identity/${local.gateway_name}-*",
        ]
      },
      {
        Sid    = "ReadInjectedOpenWeatherKey"
        Effect = "Allow"
        Action = "bedrock-agentcore:GetResourceApiKey"
        Resource = [
          local.workload_identity_base_arn,
          "${local.workload_identity_base_arn}/workload-identity/${local.gateway_name}-*",
          local.token_vault_base_arn,
          "${local.token_vault_base_arn}/api-key/${aws_bedrockagentcore_api_key_credential_provider.openweather.name}",
          aws_bedrockagentcore_api_key_credential_provider.openweather.credential_provider_arn,
        ]
      },
      {
        Sid      = "ReadIdentityManagedSecret"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_bedrockagentcore_api_key_credential_provider.openweather.api_key_secret_arn[0].secret_arn
      },
      {
        Sid      = "ReadAttachedPolicyEngine"
        Effect   = "Allow"
        Action   = "bedrock-agentcore:GetPolicyEngine"
        Resource = aws_bedrockagentcore_policy_engine.weather.policy_engine_arn
      },
      {
        Sid    = "AuthorizeGatewayPolicy"
        Effect = "Allow"
        Action = ["bedrock-agentcore:AuthorizeAction", "bedrock-agentcore:PartiallyAuthorizeActions"]
        Resource = [
          aws_bedrockagentcore_policy_engine.weather.policy_engine_arn,
          "arn:${data.aws_partition.current.partition}:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:gateway/*",
        ]
      },

    ]
  })
}

resource "aws_bedrockagentcore_policy_engine" "weather" {
  name        = "production_weather"
  description = "Policy engine for the production current-weather boundary."
}

resource "aws_bedrockagentcore_gateway" "weather" {
  name            = local.gateway_name
  description     = "Governed current-weather boundary."
  authorizer_type = "AWS_IAM"
  protocol_type   = "MCP"
  role_arn        = aws_iam_role.gateway.arn

  policy_engine_configuration {
    arn  = aws_bedrockagentcore_policy_engine.weather.policy_engine_arn
    mode = "ENFORCE"
  }
}

resource "aws_bedrockagentcore_gateway_target" "openweather" {
  name               = local.target_name
  description        = "OpenWeather target. Only the Runtime wrapper selects current weather."
  gateway_identifier = aws_bedrockagentcore_gateway.weather.gateway_id
  depends_on         = [aws_iam_role_policy.gateway]

  credential_provider_configuration {
    api_key {
      provider_arn              = aws_bedrockagentcore_api_key_credential_provider.openweather.credential_provider_arn
      credential_location       = "QUERY_PARAMETER"
      credential_parameter_name = "appid"
    }
  }

  target_configuration {
    mcp {
      open_api_schema {
        inline_payload {
          payload = file("${path.module}/../../../schemas/openweather-gateway.openapi.yaml")
        }
      }
    }
  }
}

resource "aws_bedrockagentcore_policy" "permit_current_weather" {
  name             = "permit_current_weather"
  policy_engine_id = aws_bedrockagentcore_policy_engine.weather.policy_engine_id
  description      = "Permit only the current-weather operation."
  # The intentionally unconditional operation allow-list is schema-valid but
  # triggers AgentCore's expected semantic "allow all" finding.
  validation_mode = "IGNORE_ALL_FINDINGS"

  definition {
    cedar {
      statement = <<-CEDAR
        permit(
          principal,
          action == AgentCore::Action::"${local.current_weather_action}",
          resource == AgentCore::Gateway::"${aws_bedrockagentcore_gateway.weather.gateway_arn}"
        );
      CEDAR
    }
  }
}

resource "aws_bedrockagentcore_policy" "deny_forecast" {
  name             = "deny_forecast"
  policy_engine_id = aws_bedrockagentcore_policy_engine.weather.policy_engine_id
  description      = "Deny the controlled forecast probe and preserve default deny elsewhere."
  # The intentionally unconditional forecast denial is schema-valid but
  # triggers AgentCore's expected semantic "deny all" finding.
  validation_mode = "IGNORE_ALL_FINDINGS"

  definition {
    cedar {
      statement = <<-CEDAR
        forbid(
          principal,
          action == AgentCore::Action::"${local.forecast_action}",
          resource == AgentCore::Gateway::"${aws_bedrockagentcore_gateway.weather.gateway_arn}"
        );
      CEDAR
    }
  }
}
