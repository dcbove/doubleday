resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project}-${var.environment}-api"
  description = "Doubleday REST API (${var.environment})"
}

# Lambda authorizer
resource "aws_api_gateway_authorizer" "cognito" {
  name                   = "${var.project}-${var.environment}-cognito"
  rest_api_id            = aws_api_gateway_rest_api.main.id
  type                   = "TOKEN"
  authorizer_uri         = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.authorizer_invocation.arn
  authorizer_result_ttl_in_seconds = 300
}

resource "aws_iam_role" "authorizer_invocation" {
  name = "${var.project}-${var.environment}-api-auth-invocation"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "authorizer_invocation" {
  name = "${var.project}-${var.environment}-api-auth-invocation"
  role = aws_iam_role.authorizer_invocation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.authorizer.arn
      }
    ]
  })
}

# Deployment and stage
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.pitchers,
      aws_api_gateway_resource.pitcher,
      aws_api_gateway_resource.pitches,
      aws_api_gateway_method.get_pitches,
      aws_api_gateway_integration.get_pitches,
      aws_api_gateway_method.options_pitches,
      aws_api_gateway_integration.options_pitches,
      aws_api_gateway_resource.catalogs,
      aws_api_gateway_resource.catalog_role,
      aws_api_gateway_method.get_catalog,
      aws_api_gateway_integration.get_catalog,
      aws_api_gateway_method.options_catalog,
      aws_api_gateway_integration.options_catalog,
      aws_api_gateway_resource.neighbors,
      aws_api_gateway_method.get_neighbors,
      aws_api_gateway_integration.get_neighbors,
      aws_api_gateway_method.options_neighbors,
      aws_api_gateway_integration.options_neighbors,
      aws_api_gateway_authorizer.cognito,
      aws_api_gateway_resource.subscriptions,
      aws_api_gateway_resource.subscriptions_checkout,
      aws_api_gateway_method.post_checkout,
      aws_api_gateway_integration.post_checkout,
      aws_api_gateway_method.options_checkout,
      aws_api_gateway_integration.options_checkout,
      aws_api_gateway_resource.subscriptions_portal,
      aws_api_gateway_method.post_portal,
      aws_api_gateway_integration.post_portal,
      aws_api_gateway_method.options_portal,
      aws_api_gateway_integration.options_portal,
      aws_api_gateway_resource.subscriptions_status,
      aws_api_gateway_method.get_subscription_status,
      aws_api_gateway_integration.get_subscription_status,
      aws_api_gateway_method.options_subscription_status,
      aws_api_gateway_integration.options_subscription_status,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment
}

# Usage plan and API key for rate limiting
resource "aws_api_gateway_usage_plan" "main" {
  name = "${var.project}-${var.environment}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.main.stage_name
  }

  throttle_settings {
    burst_limit = var.burst_limit
    rate_limit  = var.rate_limit
  }
}

resource "aws_api_gateway_api_key" "main" {
  name    = "${var.project}-${var.environment}-api-key"
  enabled = true
}

resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.main.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main.id
}
