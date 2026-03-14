resource "aws_iam_role" "authorizer" {
  name = "${var.project}-${var.environment}-api-authorizer"

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

resource "aws_iam_role_policy" "authorizer" {
  name = "${var.project}-${var.environment}-api-authorizer"
  role = aws_iam_role.authorizer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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

resource "aws_lambda_function" "authorizer" {
  function_name    = "${var.project}-${var.environment}-api-authorizer"
  role             = aws_iam_role.authorizer.arn
  handler          = "doubleday.api.authorizer.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_packages["authorizer"].path
  source_code_hash = var.lambda_packages["authorizer"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      COGNITO_USER_POOL_ID         = var.cognito_user_pool_id
      COGNITO_REGION               = var.region
      COGNITO_CLIENT_IDS           = join(",", var.cognito_client_ids)
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_authorizer"
    }
  }
}

resource "aws_lambda_permission" "authorizer" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}
