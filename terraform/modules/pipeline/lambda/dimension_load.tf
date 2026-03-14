resource "aws_iam_role" "dimension_load" {
  name = "${var.project}-${var.environment}-dimension-load"

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

resource "aws_iam_role_policy" "dimension_load" {
  name = "${var.project}-${var.environment}-dimension-load"
  role = aws_iam_role.dimension_load.id

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
          "glue:UpdateTable",
          "glue:CreateTable",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "s3:GetBucketLocation",
        ]
        Resource = [
          var.lakehouse_bucket_arn,
          "${var.lakehouse_bucket_arn}/*",
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

resource "aws_lambda_function" "dimension_load" {
  function_name    = "${var.project}-${var.environment}-dimension-load"
  role             = aws_iam_role.dimension_load.arn
  handler          = "doubleday.pipeline.dimension_load.handler.handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 128
  filename         = var.lambda_packages["dimension_load"].path
  source_code_hash = var.lambda_packages["dimension_load"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      GLUE_DATABASE                = var.glue_database
      ATHENA_OUTPUT_BUCKET         = var.athena_results_bucket
      LAKEHOUSE_BUCKET             = var.lakehouse_bucket_name
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "dimension_load"
    }
  }
}
