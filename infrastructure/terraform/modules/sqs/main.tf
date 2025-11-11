# SQS Module - Event Queuing and Dead Letter Queue

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
}

# Dead Letter Queue (DLQ)
resource "aws_sqs_queue" "event_dlq" {
  name                      = "${local.resource_prefix}-events-dlq"
  message_retention_seconds = var.message_retention

  tags = {
    Name = "${local.resource_prefix}-events-dlq"
  }
}

# Main Event Queue
resource "aws_sqs_queue" "event_queue" {
  name                       = "${local.resource_prefix}-events"
  visibility_timeout_seconds = var.visibility_timeout
  message_retention_seconds  = var.message_retention
  delay_seconds              = 0
  receive_wait_time_seconds  = 20 # Enable long polling for cost optimization

  # Dead Letter Queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.event_dlq.arn
    maxReceiveCount     = 3 # Retry up to 3 times before moving to DLQ
  })

  tags = {
    Name = "${local.resource_prefix}-events"
  }
}

# CloudWatch Alarm - Main Queue Depth
resource "aws_cloudwatch_metric_alarm" "queue_depth" {
  alarm_name          = "${local.resource_prefix}-event-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 1000
  alarm_description   = "Alert when event queue depth exceeds 1000 messages"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.event_queue.name
  }
}

# CloudWatch Alarm - Dead Letter Queue Depth
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${local.resource_prefix}-event-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 10
  alarm_description   = "Alert when messages appear in DLQ (indicating processing failures)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.event_dlq.name
  }
}

# CloudWatch Alarm - Message Age
resource "aws_cloudwatch_metric_alarm" "message_age" {
  alarm_name          = "${local.resource_prefix}-event-queue-message-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 3600 # 1 hour in seconds
  alarm_description   = "Alert when oldest message in queue exceeds 1 hour"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.event_queue.name
  }
}
