resource "aws_iam_role" "dynamodb_load" {
  name = "${var.project}-${var.environment}-dynamodb-load"

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

resource "aws_iam_role_policy" "dynamodb_load" {
  name = "${var.project}-${var.environment}-dynamodb-load"
  role = aws_iam_role.dynamodb_load.id

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
          "dynamodb:BatchWriteItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = var.serving_table_arn
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

resource "aws_lambda_function" "dynamodb_load" {
  function_name    = "${var.project}-${var.environment}-dynamodb-load"
  role             = aws_iam_role.dynamodb_load.arn
  handler          = "doubleday.pipeline.dynamodb_load.handler.handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 256
  filename         = var.lambda_packages["dynamodb_load"].path
  source_code_hash = var.lambda_packages["dynamodb_load"].hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      GLUE_DATABASE                = var.glue_database
      ATHENA_OUTPUT_BUCKET         = var.athena_results_bucket
      SERVING_TABLE_NAME           = var.serving_table_name
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "dynamodb_load"
    }
  }
}
