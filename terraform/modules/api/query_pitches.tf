# --- API Gateway resource tree ---

# /pitchers
resource "aws_api_gateway_resource" "pitchers" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "pitchers"
}

# /pitchers/{pitcher_id}
resource "aws_api_gateway_resource" "pitcher" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.pitchers.id
  path_part   = "{pitcher_id}"
}

# /pitchers/{pitcher_id}/pitches
resource "aws_api_gateway_resource" "pitches" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.pitcher.id
  path_part   = "pitches"
}

# --- GET /pitchers/{pitcher_id}/pitches ---

resource "aws_api_gateway_method" "get_pitches" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.pitches.id
  http_method      = "GET"
  authorization    = "CUSTOM"
  authorizer_id    = aws_api_gateway_authorizer.cognito.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "get_pitches" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.pitches.id
  http_method             = aws_api_gateway_method.get_pitches.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query_pitches.invoke_arn
}

# --- OPTIONS /pitchers/{pitcher_id}/pitches (CORS preflight) ---

resource "aws_api_gateway_method" "options_pitches" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.pitches.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_pitches" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pitches.id
  http_method = aws_api_gateway_method.options_pitches.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_pitches" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pitches.id
  http_method = aws_api_gateway_method.options_pitches.http_method
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

resource "aws_api_gateway_integration_response" "options_pitches" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.pitches.id
  http_method = aws_api_gateway_method.options_pitches.http_method
  status_code = aws_api_gateway_method_response.options_pitches.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- Lambda function ---

resource "aws_iam_role" "query_pitches" {
  name = "${var.project}-${var.environment}-api-query-pitches"

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

resource "aws_iam_role_policy" "query_pitches" {
  name = "${var.project}-${var.environment}-api-query-pitches"
  role = aws_iam_role.query_pitches.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
        ]
        Resource = var.serving_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
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

resource "aws_lambda_function" "query_pitches" {
  function_name    = "${var.project}-${var.environment}-api-query-pitches"
  role             = aws_iam_role.query_pitches.arn
  handler          = "doubleday.api.query_pitches.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_packages["query_pitches"].path
  source_code_hash = var.lambda_packages["query_pitches"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      SERVING_TABLE_NAME           = var.serving_table_name
      ENTITLEMENTS_TABLE_NAME      = aws_dynamodb_table.entitlements.name
      REQUIRE_SUBSCRIPTION         = tostring(var.enable_stripe)
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_query_pitches"
    }
  }
}

resource "aws_lambda_permission" "query_pitches" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query_pitches.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}
