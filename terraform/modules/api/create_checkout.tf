# --- API Gateway resource tree ---

# /subscriptions (shared parent for subscription endpoints — always present)
resource "aws_api_gateway_resource" "subscriptions" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "subscriptions"
}

# /subscriptions/checkout
resource "aws_api_gateway_resource" "subscriptions_checkout" {
  count       = var.enable_stripe ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.subscriptions.id
  path_part   = "checkout"
}

# --- POST /subscriptions/checkout ---

resource "aws_api_gateway_method" "post_checkout" {
  count            = var.enable_stripe ? 1 : 0
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method      = "POST"
  authorization    = "CUSTOM"
  authorizer_id    = aws_api_gateway_authorizer.cognito.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "post_checkout" {
  count                   = var.enable_stripe ? 1 : 0
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method             = aws_api_gateway_method.post_checkout[0].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.create_checkout[0].invoke_arn
}

# --- OPTIONS /subscriptions/checkout (CORS preflight) ---

resource "aws_api_gateway_method" "options_checkout" {
  count         = var.enable_stripe ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_checkout" {
  count       = var.enable_stripe ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method = aws_api_gateway_method.options_checkout[0].http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_checkout" {
  count       = var.enable_stripe ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method = aws_api_gateway_method.options_checkout[0].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "options_checkout" {
  count       = var.enable_stripe ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.subscriptions_checkout[0].id
  http_method = aws_api_gateway_method.options_checkout[0].http_method
  status_code = aws_api_gateway_method_response.options_checkout[0].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- Lambda function ---

resource "aws_iam_role" "create_checkout" {
  count = var.enable_stripe ? 1 : 0
  name  = "${var.project}-${var.environment}-api-create-checkout"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "create_checkout" {
  count = var.enable_stripe ? 1 : 0
  name  = "${var.project}-${var.environment}-api-create-checkout"
  role  = aws_iam_role.create_checkout[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
        ]
        Resource = aws_dynamodb_table.entitlements.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
    ]
  })
}

resource "aws_lambda_function" "create_checkout" {
  count            = var.enable_stripe ? 1 : 0
  function_name    = "${var.project}-${var.environment}-api-create-checkout"
  role             = aws_iam_role.create_checkout[0].arn
  handler          = "doubleday.api.create_checkout.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_packages["create_checkout"].path
  source_code_hash = var.lambda_packages["create_checkout"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY            = var.stripe_secret_key
      STRIPE_PRICE_ID              = var.stripe_price_id
      ENTITLEMENTS_TABLE_NAME      = aws_dynamodb_table.entitlements.name
      FRONTEND_URL                 = var.frontend_url
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_create_checkout"
    }
  }
}

resource "aws_lambda_permission" "create_checkout" {
  count         = var.enable_stripe ? 1 : 0
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_checkout[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}
