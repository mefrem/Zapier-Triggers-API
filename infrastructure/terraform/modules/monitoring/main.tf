# Monitoring Module - CloudWatch Dashboards and Alarms

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.resource_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # API Gateway Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "Total Requests" }],
            [".", "4XXError", { stat = "Sum", label = "4XX Errors" }],
            [".", "5XXError", { stat = "Sum", label = "5XX Errors" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "API Gateway - Request Count"
          period  = 300
          dimensions = {
            ApiName = "${local.resource_prefix}-api"
            Stage   = var.api_gateway_stage_name
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Latency", { stat = "Average", label = "Average Latency" }],
            ["...", { stat = "p95", label = "P95 Latency" }],
            ["...", { stat = "p99", label = "P99 Latency" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "API Gateway - Latency"
          period = 300
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
          dimensions = {
            ApiName = "${local.resource_prefix}-api"
            Stage   = var.api_gateway_stage_name
          }
        }
      },
      # Lambda Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum" }],
            [".", "Errors", { stat = "Sum" }],
            [".", "Throttles", { stat = "Sum" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "Lambda - Health Check Function"
          period = 300
          dimensions = {
            FunctionName = var.health_check_function_name
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", { stat = "Average", label = "Average Duration" }],
            ["...", { stat = "Maximum", label = "Max Duration" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "Lambda - Duration"
          period = 300
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
          dimensions = {
            FunctionName = var.health_check_function_name
          }
        }
      },
      # DynamoDB Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", { stat = "Sum", label = "Read Capacity" }],
            [".", "ConsumedWriteCapacityUnits", { stat = "Sum", label = "Write Capacity" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "DynamoDB - Events Table Capacity"
          period = 300
          dimensions = {
            TableName = var.events_table_name
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "UserErrors", { stat = "Sum", label = "Throttled Requests" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "DynamoDB - Throttling"
          period = 300
          dimensions = {
            TableName = var.events_table_name
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "SuccessfulRequestLatency", { stat = "Average", label = "Average Latency" }],
            ["...", { stat = "p95", label = "P95 Latency" }],
            ["...", { stat = "p99", label = "P99 Latency" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "DynamoDB - Write Latency (PutItem)"
          period = 300
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
          dimensions = {
            TableName = var.events_table_name
            Operation = "PutItem"
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "SuccessfulRequestLatency", { stat = "Average", label = "Average Latency" }],
            ["...", { stat = "p95", label = "P95 Latency" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "DynamoDB - Read Latency (Query/GetItem)"
          period = 300
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
          dimensions = {
            TableName = var.events_table_name
            Operation = "Query"
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "AccountMaxTableLevelReads", { stat = "Average", label = "Max Table Reads" }],
            [".", "AccountMaxTableLevelWrites", { stat = "Average", label = "Max Table Writes" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "DynamoDB - Table Level Limits"
          period = 300
          dimensions = {
            TableName = var.events_table_name
          }
        }
      },
      # SQS Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", { stat = "Average", label = "Messages in Queue" }],
            [".", "NumberOfMessagesSent", { stat = "Sum", label = "Messages Sent" }],
            [".", "NumberOfMessagesReceived", { stat = "Sum", label = "Messages Received" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "SQS - Event Queue"
          period = 300
          dimensions = {
            QueueName = var.event_queue_name
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", { stat = "Average" }]
          ]
          view   = "timeSeries"
          region = data.aws_region.current.name
          title  = "SQS - Dead Letter Queue"
          period = 300
          dimensions = {
            QueueName = var.event_dlq_name
          }
        }
      }
    ]
  })
}

# API Gateway Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "api_error_rate" {
  alarm_name          = "${local.resource_prefix}-api-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when API Gateway 5XX error count exceeds threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = "${local.resource_prefix}-api"
    Stage   = var.api_gateway_stage_name
  }

  tags = {
    Name = "${local.resource_prefix}-api-error-rate"
  }
}

# Lambda Error Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.resource_prefix}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Lambda function errors exceed threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.health_check_function_name
  }

  tags = {
    Name = "${local.resource_prefix}-lambda-errors"
  }
}

# Lambda Duration Alarm (Cold Starts)
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${local.resource_prefix}-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 5000 # 5 seconds
  alarm_description   = "Alert when Lambda function duration exceeds 5 seconds"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.health_check_function_name
  }

  tags = {
    Name = "${local.resource_prefix}-lambda-duration"
  }
}

# API Gateway Latency Alarm
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${local.resource_prefix}-api-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 1000 # 1 second
  alarm_description   = "Alert when API Gateway P95 latency exceeds 1 second"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = "${local.resource_prefix}-api"
    Stage   = var.api_gateway_stage_name
  }

  tags = {
    Name = "${local.resource_prefix}-api-latency"
  }
}

# DynamoDB Write Latency Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_write_latency" {
  alarm_name          = "${local.resource_prefix}-dynamodb-write-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "SuccessfulRequestLatency"
  namespace           = "AWS/DynamoDB"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 20 # 20 milliseconds
  alarm_description   = "Alert when DynamoDB P99 write latency exceeds 20ms"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = var.events_table_name
    Operation = "PutItem"
  }

  tags = {
    Name = "${local.resource_prefix}-dynamodb-write-latency"
  }
}

# DynamoDB Read Latency Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_read_latency" {
  alarm_name          = "${local.resource_prefix}-dynamodb-read-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "SuccessfulRequestLatency"
  namespace           = "AWS/DynamoDB"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 50 # 50 milliseconds
  alarm_description   = "Alert when DynamoDB P95 read latency exceeds 50ms"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = var.events_table_name
    Operation = "Query"
  }

  tags = {
    Name = "${local.resource_prefix}-dynamodb-read-latency"
  }
}

# Data source for current AWS region
data "aws_region" "current" {}
