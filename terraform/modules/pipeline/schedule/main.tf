# --- daily_trigger Lambda ---

resource "aws_iam_role" "daily_trigger" {
  name = "${var.project}-${var.environment}-daily-trigger"

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

resource "aws_iam_role_policy" "daily_trigger" {
  name = "${var.project}-${var.environment}-daily-trigger"
  role = aws_iam_role.daily_trigger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
        ]
        Resource = var.state_machine_arn
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

resource "aws_lambda_function" "daily_trigger" {
  function_name    = "${var.project}-${var.environment}-daily-trigger"
  role             = aws_iam_role.daily_trigger.arn
  handler          = "doubleday.pipeline.daily_trigger.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_package_path
  source_code_hash = var.lambda_package_hash
  layers           = [var.powertools_layer_arn]

  environment {
    variables = {
      STATE_MACHINE_ARN              = var.state_machine_arn
      POWERTOOLS_METRICS_NAMESPACE   = "Doubleday"
      POWERTOOLS_SERVICE_NAME        = "daily_trigger"
    }
  }
}

# --- EventBridge Scheduler ---

resource "aws_iam_role" "scheduler" {
  name = "${var.project}-${var.environment}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${var.project}-${var.environment}-scheduler"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
        ]
        Resource = aws_lambda_function.daily_trigger.arn
      },
    ]
  })
}

resource "aws_scheduler_schedule" "daily_pipeline" {
  name       = "${var.project}-${var.environment}-daily-pipeline"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 9 * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = aws_lambda_function.daily_trigger.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}
