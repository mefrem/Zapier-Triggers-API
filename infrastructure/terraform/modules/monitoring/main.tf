# CloudWatch Dashboard, Alarms, and X-Ray Configuration for Zapier Triggers API

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "api_name" {
  description = "API name for CloudWatch metrics"
  type        = string
  default     = "zapier-triggers-api"
}

variable "lambda_function_name" {
  description = "Lambda function name for monitoring"
  type        = string
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name for monitoring"
  type        = string
}

variable "sns_alert_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
}

# SNS Topic for Alerts
resource "aws_sns_topic" "ops_alerts" {
  name = "${var.api_name}-${var.environment}-ops-alerts"

  tags = {
    Name        = "${var.api_name}-ops-alerts"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_sns_topic_subscription" "ops_alerts_email" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.sns_alert_email
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 90

  tags = {
    Name        = "${var.api_name}-lambda-logs"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.api_name}-${var.environment}-main-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Total Requests" }],
            [".", "Errors", { stat = "Sum", label = "Errors" }],
            [".", "Throttles", { stat = "Sum", label = "Throttles" }]
          ]
          period = 60
          stat   = "Average"
          region = "us-east-1"
          title  = "Lambda Invocations & Errors"
          yAxis = {
            left = {
              label = "Count"
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", { stat = "p50", label = "p50" }],
            ["...", { stat = "p95", label = "p95" }],
            ["...", { stat = "p99", label = "p99" }]
          ]
          period = 60
          stat   = "Average"
          region = "us-east-1"
          title  = "Lambda Latency Percentiles"
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", { stat = "Sum" }],
            [".", "ConsumedReadCapacityUnits", { stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = "us-east-1"
          title  = "DynamoDB Capacity Usage"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["ZapierTriggersAPI", "EventsIngested", { stat = "Sum" }],
            [".", "EventsDelivered", { stat = "Sum" }],
            [".", "EventsFailed", { stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = "us-east-1"
          title  = "Custom Business Metrics"
        }
      }
    ]
  })
}

# High Error Rate Alarm (>5%)
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.api_name}-${var.environment}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 5.0
  alarm_description   = "Error rate exceeded 5% over 5-minute period"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / invocations) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = var.lambda_function_name
      }
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = var.lambda_function_name
      }
    }
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]

  tags = {
    Name        = "${var.api_name}-high-error-rate-alarm"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# High Latency Alarm (p95 > 100ms)
resource "aws_cloudwatch_metric_alarm" "high_latency_p95" {
  alarm_name          = "${var.api_name}-${var.environment}-high-latency-p95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "p95"
  threshold           = 100
  alarm_description   = "p95 latency exceeded 100ms for 10 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]

  tags = {
    Name        = "${var.api_name}-high-latency-alarm"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# X-Ray Sampling Rule
resource "aws_xray_sampling_rule" "triggers_api" {
  rule_name      = "${var.api_name}-${var.environment}-sampling"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = var.environment == "prod" ? 0.01 : 1.0
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = var.api_name
  resource_arn   = "*"

  tags = {
    Name        = "${var.api_name}-xray-sampling"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Outputs
output "dashboard_url" {
  description = "URL to CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.ops_alerts.arn
}

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}
