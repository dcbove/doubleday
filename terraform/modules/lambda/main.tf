data "archive_file" "silver_load" {
  type        = "zip"
  output_path = "${path.module}/../../../builds/silver_load.zip"

  dynamic "source" {
    for_each = fileset("${path.module}/../../../src", "doubleday/**/*.py")
    content {
      content  = file("${path.module}/../../../src/${source.value}")
      filename = source.value
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/../../../sql/pipeline", "silver_*.sql")
    content {
      content  = file("${path.module}/../../../sql/pipeline/${source.value}")
      filename = "sql/${source.value}"
    }
  }
}

resource "aws_iam_role" "silver_load" {
  name = "${var.project}-${var.environment}-silver-load"

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

resource "aws_iam_role_policy" "silver_load" {
  name = "${var.project}-${var.environment}-silver-load"
  role = aws_iam_role.silver_load.id

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

resource "aws_lambda_function" "silver_load" {
  function_name    = "${var.project}-${var.environment}-silver-load"
  role             = aws_iam_role.silver_load.arn
  handler          = "doubleday.lambdas.silver_load.handler.handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 128
  filename         = data.archive_file.silver_load.output_path
  source_code_hash = data.archive_file.silver_load.output_base64sha256
  layers           = [var.powertools_layer_arn]

  environment {
    variables = {
      GLUE_DATABASE                  = var.glue_database
      ATHENA_OUTPUT_BUCKET           = var.athena_results_bucket
      POWERTOOLS_METRICS_NAMESPACE   = "Doubleday"
      POWERTOOLS_SERVICE_NAME        = "silver_load"
    }
  }
}
