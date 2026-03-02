# --- API Gateway resource tree ---

# /catalogs
resource "aws_api_gateway_resource" "catalogs" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "catalogs"
}

# /catalogs/{role}
resource "aws_api_gateway_resource" "catalog_role" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.catalogs.id
  path_part   = "{role}"
}

# --- GET /catalogs/{role} ---

resource "aws_api_gateway_method" "get_catalog" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.catalog_role.id
  http_method      = "GET"
  authorization    = "CUSTOM"
  authorizer_id    = aws_api_gateway_authorizer.cognito.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "get_catalog" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.catalog_role.id
  http_method             = aws_api_gateway_method.get_catalog.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.catalog.invoke_arn
}

# --- OPTIONS /catalogs/{role} (CORS preflight) ---

resource "aws_api_gateway_method" "options_catalog" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.catalog_role.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_catalog" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.catalog_role.id
  http_method = aws_api_gateway_method.options_catalog.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_catalog" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.catalog_role.id
  http_method = aws_api_gateway_method.options_catalog.http_method
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

resource "aws_api_gateway_integration_response" "options_catalog" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.catalog_role.id
  http_method = aws_api_gateway_method.options_catalog.http_method
  status_code = aws_api_gateway_method_response.options_catalog.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- Lambda function ---

resource "aws_iam_role" "catalog" {
  name = "${var.project}-${var.environment}-api-catalog"

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

resource "aws_iam_role_policy" "catalog" {
  name = "${var.project}-${var.environment}-api-catalog"
  role = aws_iam_role.catalog.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = var.serving_table_arn
      },
      {
        Effect   = "Allow"
        Action   = "cloudwatch:PutMetricData"
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

resource "aws_lambda_function" "catalog" {
  function_name    = "${var.project}-${var.environment}-api-catalog"
  role             = aws_iam_role.catalog.arn
  handler          = "doubleday.api.catalog.handler.handler"
  runtime          = "python3.12"
  timeout          = 10
  memory_size      = 128
  filename         = var.lambda_package_path
  source_code_hash = var.lambda_package_hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      SERVING_TABLE_NAME           = var.serving_table_name
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_catalog"
    }
  }
}

resource "aws_lambda_permission" "catalog" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.catalog.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}
