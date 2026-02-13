resource "aws_iam_role" "pipeline" {
  name = "${var.project}-${var.environment}-pipeline"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "pipeline" {
  name = "${var.project}-${var.environment}-pipeline"
  role = aws_iam_role.pipeline.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = [
          var.silver_load_function_arn,
          var.gold_load_function_arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/aws/stepfunction/${var.project}-${var.environment}-pipeline"
  retention_in_days = 30
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.project}-${var.environment}-pipeline"
  role_arn = aws_iam_role.pipeline.arn

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.pipeline.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  definition = jsonencode({
    Comment = "Doubleday ETL pipeline: silver load per game_date, then gold load per table"
    StartAt = "SilverLoadMap"
    States = {
      SilverLoadMap = {
        Type       = "Map"
        InputPath  = "$"
        ItemsPath  = "$.game_dates"
        MaxConcurrency = 5
        Parameters = {
          "partition_name.$" = "States.Format('season={}/game_date={}', $.season, $$.Map.Item.Value)"
        }
        Iterator = {
          StartAt = "SilverLoad"
          States = {
            SilverLoad = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = {
                FunctionName = var.silver_load_function_arn
                "Payload.$"  = "$"
              }
              ResultPath = "$.silver_result"
              End        = true
            }
          }
        }
        ResultPath = "$.silver_results"
        Next       = "GoldLoadMap"
      }

      GoldLoadMap = {
        Type       = "Map"
        InputPath  = "$"
        ItemsPath  = "$.gold_tables"
        MaxConcurrency = 1
        Parameters = {
          "table_name.$" = "$$.Map.Item.Value"
          "season.$"     = "$.season"
        }
        Iterator = {
          StartAt = "GoldLoad"
          States = {
            GoldLoad = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = {
                FunctionName = var.gold_load_function_arn
                "Payload.$"  = "$"
              }
              ResultPath = "$.gold_result"
              End        = true
            }
          }
        }
        ResultPath = "$.gold_results"
        Next       = "Succeed"
      }

      Succeed = {
        Type = "Succeed"
      }
    }
  })
}
