resource "aws_iam_role" "check_failures" {
  name = "${var.project}-${var.environment}-check-failures"

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

resource "aws_iam_role_policy" "check_failures" {
  name = "${var.project}-${var.environment}-check-failures"
  role = aws_iam_role.check_failures.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
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

resource "aws_lambda_function" "check_failures" {
  function_name    = "${var.project}-${var.environment}-check-failures"
  role             = aws_iam_role.check_failures.arn
  handler          = "doubleday.pipeline.check_failures.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_package_path
  source_code_hash = var.lambda_package_hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      LAKEHOUSE_BUCKET                = var.lakehouse_bucket_name
      POWERTOOLS_METRICS_NAMESPACE    = "Doubleday"
      POWERTOOLS_SERVICE_NAME         = "check_failures"
    }
  }
}
