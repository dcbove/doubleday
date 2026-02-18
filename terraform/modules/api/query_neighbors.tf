# --- API Gateway resource tree ---

# /pitchers/{pitcher_id}/neighbors
resource "aws_api_gateway_resource" "neighbors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.pitcher.id
  path_part   = "neighbors"
}

# --- GET /pitchers/{pitcher_id}/neighbors ---

resource "aws_api_gateway_method" "get_neighbors" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.neighbors.id
  http_method      = "GET"
  authorization    = "CUSTOM"
  authorizer_id    = aws_api_gateway_authorizer.cognito.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "get_neighbors" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.neighbors.id
  http_method             = aws_api_gateway_method.get_neighbors.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query_neighbors.invoke_arn
}

# --- OPTIONS /pitchers/{pitcher_id}/neighbors (CORS preflight) ---

resource "aws_api_gateway_method" "options_neighbors" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.neighbors.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_neighbors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.neighbors.id
  http_method = aws_api_gateway_method.options_neighbors.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_neighbors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.neighbors.id
  http_method = aws_api_gateway_method.options_neighbors.http_method
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

resource "aws_api_gateway_integration_response" "options_neighbors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.neighbors.id
  http_method = aws_api_gateway_method.options_neighbors.http_method
  status_code = aws_api_gateway_method_response.options_neighbors.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# --- Lambda function ---

resource "aws_iam_role" "query_neighbors" {
  name = "${var.project}-${var.environment}-api-query-neighbors"

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

resource "aws_iam_role_policy" "query_neighbors" {
  name = "${var.project}-${var.environment}-api-query-neighbors"
  role = aws_iam_role.query_neighbors.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetBucketLocation",
          "s3:ListBucket",
        ]
        Resource = [
          var.lakehouse_bucket_arn,
          "${var.lakehouse_bucket_arn}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:GetBucketLocation",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::${var.athena_results_bucket}",
          "arn:aws:s3:::${var.athena_results_bucket}/*",
        ]
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

resource "aws_lambda_function" "query_neighbors" {
  function_name    = "${var.project}-${var.environment}-api-query-neighbors"
  role             = aws_iam_role.query_neighbors.arn
  handler          = "doubleday.api.query_neighbors.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_package_path
  source_code_hash = var.lambda_package_hash
  layers           = [var.powertools_layer_arn]

  environment {
    variables = {
      GLUE_DATABASE                = var.glue_database
      ATHENA_OUTPUT_BUCKET         = var.athena_results_bucket
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_query_neighbors"
    }
  }
}

resource "aws_lambda_permission" "query_neighbors" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query_neighbors.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}
