resource "aws_iam_role" "bronze_load" {
  name = "${var.project}-${var.environment}-bronze-load"

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

resource "aws_iam_role_policy" "bronze_load" {
  name = "${var.project}-${var.environment}-bronze-load"
  role = aws_iam_role.bronze_load.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${var.lakehouse_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = var.lakehouse_bucket_arn
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

resource "aws_lambda_function" "bronze_load" {
  function_name    = "${var.project}-${var.environment}-bronze-load"
  role             = aws_iam_role.bronze_load.arn
  handler          = "doubleday.pipeline.bronze_load.handler.handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 128
  filename         = var.lambda_packages["bronze_load"].path
  source_code_hash = var.lambda_packages["bronze_load"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      LAKEHOUSE_BUCKET               = var.lakehouse_bucket_name
      POWERTOOLS_METRICS_NAMESPACE   = "Doubleday"
      POWERTOOLS_SERVICE_NAME        = "bronze_load"
    }
  }
}
