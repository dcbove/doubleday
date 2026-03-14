resource "aws_iam_role" "validate_input" {
  name = "${var.project}-${var.environment}-validate-input"

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

resource "aws_iam_role_policy" "validate_input" {
  name = "${var.project}-${var.environment}-validate-input"
  role = aws_iam_role.validate_input.id

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

resource "aws_lambda_function" "validate_input" {
  function_name    = "${var.project}-${var.environment}-validate-input"
  role             = aws_iam_role.validate_input.arn
  handler          = "doubleday.pipeline.validate_input.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_packages["validate_input"].path
  source_code_hash = var.lambda_packages["validate_input"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "validate_input"
    }
  }
}
