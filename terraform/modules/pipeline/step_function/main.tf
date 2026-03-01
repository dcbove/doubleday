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
          var.validate_input_function_arn,
          var.bronze_load_function_arn,
          var.silver_load_function_arn,
          var.gold_load_function_arn,
          var.clear_staging_function_arn,
          var.check_failures_function_arn,
          var.catalog_build_function_arn,
          var.dynamodb_load_function_arn,
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
    Comment = "Doubleday ETL pipeline: validate → bronze → silver → gold → catalog"
    StartAt = "ValidateInput"
    States = {
      ValidateInput = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.validate_input_function_arn
          "Payload.$"  = "$"
        }
        ResultSelector = {
          "season.$"         = "$.Payload.season"
          "game_dates.$"     = "$.Payload.game_dates"
          "force_download.$" = "$.Payload.force_download"
          "batch_id.$"       = "$.Payload.batch_id"
        }
        ResultPath = "$"
        Next       = "BronzeLoadMap"
      }

      BronzeLoadMap = {
        Type       = "Map"
        InputPath  = "$"
        ItemsPath  = "$.game_dates"
        MaxConcurrency = 5
        Parameters = {
          "season.$"         = "$.season"
          "game_date.$"      = "$$.Map.Item.Value"
          "force_download.$" = "$.force_download"
        }
        Iterator = {
          StartAt = "BronzeLoad"
          States = {
            BronzeLoad = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = {
                FunctionName = var.bronze_load_function_arn
                "Payload.$"  = "$"
              }
              ResultPath = "$.bronze_result"
              End        = true
            }
          }
        }
        ResultPath = null
        Next       = "SilverLoadMap"
      }

      SilverLoadMap = {
        Type       = "Map"
        InputPath  = "$"
        ItemsPath  = "$.game_dates"
        MaxConcurrency = 5
        Parameters = {
          "season.$"    = "$.season"
          "game_date.$" = "$$.Map.Item.Value"
          "batch_id.$"  = "$.batch_id"
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
              Catch = [
                {
                  ErrorEquals = ["States.ALL"]
                  ResultPath  = "$.error"
                  Next        = "SilverLoadCatch"
                }
              ]
              End = true
            }
            SilverLoadCatch = {
              Type = "Pass"
              End  = true
            }
          }
        }
        ResultPath = null
        Next       = "ClearStaging"
      }

      ClearStaging = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.clear_staging_function_arn
          Payload = {
            "batch_id.$" = "$.batch_id"
          }
        }
        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        ResultPath = null
        Next       = "GoldLoadShapeSeason"
      }

      GoldLoadShapeSeason = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.gold_load_function_arn
          Payload = {
            "table_name" = "gold_pitches_shape_season"
            "season.$"   = "$.season"
          }
        }
        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        ResultPath = null
        Next       = "GoldLoadNormStats"
      }

      GoldLoadNormStats = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.gold_load_function_arn
          Payload = {
            "table_name" = "gold_pitch_type_norm_stats"
            "season.$"   = "$.season"
          }
        }
        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        ResultPath = null
        Next       = "GoldLoadNeighbors"
      }

      GoldLoadNeighbors = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.gold_load_function_arn
          Payload = {
            "table_name"    = "gold_repertoire_shape_neighbors"
            "season.$"      = "$.season"
            "format_params" = {
              "lambda" = "0.4"
              "tau"    = "1"
            }
          }
        }
        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        ResultPath = null
        Next       = "DynamoDBLoadParallel"
      }

      DynamoDBLoadParallel = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "DynamoDBLoadPitches"
            States = {
              DynamoDBLoadPitches = {
                Type     = "Task"
                Resource = "arn:aws:states:::lambda:invoke"
                Parameters = {
                  FunctionName = var.dynamodb_load_function_arn
                  Payload = {
                    "entity_type" = "pitches"
                    "season.$"    = "$.season"
                  }
                }
                ResultPath = "$.dynamodb_pitches_result"
                End        = true
              }
            }
          },
          {
            StartAt = "DynamoDBLoadNeighbors"
            States = {
              DynamoDBLoadNeighbors = {
                Type     = "Task"
                Resource = "arn:aws:states:::lambda:invoke"
                Parameters = {
                  FunctionName = var.dynamodb_load_function_arn
                  Payload = {
                    "entity_type" = "neighbors"
                    "season.$"    = "$.season"
                  }
                }
                ResultPath = "$.dynamodb_neighbors_result"
                End        = true
              }
            }
          }
        ]
        ResultPath = null
        Next       = "SetCatalogRoles"
      }

      SetCatalogRoles = {
        Type       = "Pass"
        Result     = ["pitchers", "batters"]
        ResultPath = "$.catalog_roles"
        Next       = "CatalogBuildMap"
      }

      CatalogBuildMap = {
        Type           = "Map"
        InputPath      = "$"
        ItemsPath      = "$.catalog_roles"
        MaxConcurrency = 2
        Parameters = {
          "season.$" = "$.season"
          "role.$"   = "$$.Map.Item.Value"
        }
        Iterator = {
          StartAt = "CatalogBuild"
          States = {
            CatalogBuild = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = {
                FunctionName = var.catalog_build_function_arn
                "Payload.$"  = "$"
              }
              ResultPath = "$.catalog_result"
              End        = true
            }
          }
        }
        ResultPath = null
        Next       = "CheckFailures"
      }

      CheckFailures = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.check_failures_function_arn
          Payload = {
            "batch_id.$" = "$.batch_id"
          }
        }
        ResultSelector = {
          "failure_count.$"     = "$.Payload.failure_count"
          "failed_game_dates.$" = "$.Payload.failed_game_dates"
          "failure_summary.$"   = "$.Payload.failure_summary"
        }
        ResultPath = "$.check_result"
        Next       = "HasFailures"
      }

      HasFailures = {
        Type = "Choice"
        Choices = [
          {
            Variable             = "$.check_result.failure_count"
            NumericGreaterThan   = 0
            Next                 = "PipelineFail"
          }
        ]
        Default = "Succeed"
      }

      PipelineFail = {
        Type      = "Fail"
        Error     = "SilverLoadPartialFailure"
        CausePath = "$.check_result.failure_summary"
      }

      Succeed = {
        Type = "Succeed"
      }
    }
  })
}
