# --- Stripe EventBridge partner integration ---

# The partner event source is created in the Stripe Dashboard.
# The event source name is passed via var.stripe_event_source_name.

resource "aws_cloudwatch_event_bus" "stripe" {
  name              = var.stripe_event_source_name
  event_source_name = var.stripe_event_source_name
}

# Single rule matching the 4 subscription lifecycle event types
resource "aws_cloudwatch_event_rule" "stripe_entitlements" {
  name           = "${var.project}-${var.environment}-stripe-entitlements"
  event_bus_name = aws_cloudwatch_event_bus.stripe.name

  event_pattern = jsonencode({
    source      = [{ "prefix" : "aws.partner/stripe.com" }]
    detail-type = [
      "checkout.session.completed",
      "customer.subscription.updated",
      "customer.subscription.deleted",
      "invoice.payment_failed",
    ]
  })
}

resource "aws_cloudwatch_event_target" "stripe_entitlements" {
  rule           = aws_cloudwatch_event_rule.stripe_entitlements.name
  event_bus_name = aws_cloudwatch_event_bus.stripe.name
  arn            = aws_lambda_function.stripe_events.arn
}

# --- Lambda function ---

resource "aws_iam_role" "stripe_events" {
  name = "${var.project}-${var.environment}-api-stripe-events"

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

resource "aws_iam_role_policy" "stripe_events" {
  name = "${var.project}-${var.environment}-api-stripe-events"
  role = aws_iam_role.stripe_events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
        ]
        Resource = aws_dynamodb_table.entitlements.arn
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
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

resource "aws_lambda_function" "stripe_events" {
  function_name    = "${var.project}-${var.environment}-api-stripe-events"
  role             = aws_iam_role.stripe_events.arn
  handler          = "doubleday.api.stripe_events.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = var.lambda_package_path
  source_code_hash = var.lambda_package_hash
  layers           = [var.powertools_layer_arn, var.deps_layer_arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY            = var.stripe_secret_key
      ENTITLEMENTS_TABLE_NAME      = aws_dynamodb_table.entitlements.name
      POWERTOOLS_METRICS_NAMESPACE = "Doubleday"
      POWERTOOLS_SERVICE_NAME      = "api_stripe_events"
    }
  }
}

resource "aws_lambda_permission" "stripe_events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stripe_events.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stripe_entitlements.arn
}
