resource "aws_cloudwatch_dashboard" "pipeline" {
  dashboard_name = "${var.project}-${var.environment}-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Silver Load Failures"
          region = var.region
          metrics = [
            ["Doubleday", "SilverLoadFailed", { stat = "Sum", period = 86400 }]
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Silver Load Successes"
          region = var.region
          metrics = [
            ["Doubleday", "PartitionsInserted", { stat = "Sum", period = 86400 }]
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 6
        width  = 24
        height = 6
        properties = {
          title  = "Recent Failure Details"
          region = var.region
          query  = "SOURCE '/aws/lambda/${var.project}-${var.environment}-silver-load' | fields @timestamp, game_date, season, error\n| filter level = \"ERROR\"\n| sort @timestamp desc\n| limit 50"
          view   = "table"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title  = "Pipeline Execution Status"
          region = var.region
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", "arn:aws:states:${var.region}:*:stateMachine:${var.project}-${var.environment}-pipeline", { stat = "Sum", period = 86400 }],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", "arn:aws:states:${var.region}:*:stateMachine:${var.project}-${var.environment}-pipeline", { stat = "Sum", period = 86400 }]
          ]
          view = "timeSeries"
        }
      },
    ]
  })
}
