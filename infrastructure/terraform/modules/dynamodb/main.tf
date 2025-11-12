# DynamoDB Module - Event Storage, API Keys, Audit Logs

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
}

# Events Table
resource "aws_dynamodb_table" "events" {
  name         = "${local.resource_prefix}-events"
  billing_mode = var.billing_mode
  hash_key     = "user_id"
  range_key    = "timestamp#event_id"

  # Primary Key Attributes
  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "timestamp#event_id"
    type = "S"
  }

  # GSI Attributes
  attribute {
    name = "event_type#timestamp"
    type = "S"
  }

  attribute {
    name = "status#timestamp"
    type = "S"
  }

  # Global Secondary Index 1: EventTypeIndex
  global_secondary_index {
    name            = "EventTypeIndex"
    hash_key        = "user_id"
    range_key       = "event_type#timestamp"
    projection_type = "ALL"
  }

  # Global Secondary Index 2: StatusIndex
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "user_id"
    range_key       = "status#timestamp"
    projection_type = "ALL"
  }

  # TTL Configuration (30 days)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = true
  }

  # DynamoDB Streams for event notifications
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  tags = {
    Name = "${local.resource_prefix}-events"
  }
}

# API Keys Table
resource "aws_dynamodb_table" "api_keys" {
  name         = "${local.resource_prefix}-api-keys"
  billing_mode = var.billing_mode
  hash_key     = "user_id"
  range_key    = "key_id"

  # Primary Key Attributes
  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "key_id"
    type = "S"
  }

  # GSI Attribute
  attribute {
    name = "key_hash"
    type = "S"
  }

  # Global Secondary Index: KeyHashIndex (for authentication lookups)
  global_secondary_index {
    name            = "KeyHashIndex"
    hash_key        = "key_hash"
    projection_type = "ALL"
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${local.resource_prefix}-api-keys"
  }
}

# Audit Logs Table
resource "aws_dynamodb_table" "audit_logs" {
  name         = "${local.resource_prefix}-audit-logs"
  billing_mode = var.billing_mode
  hash_key     = "user_id"
  range_key    = "timestamp#log_id"

  # Primary Key Attributes
  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "timestamp#log_id"
    type = "S"
  }

  # TTL Configuration (7 years for compliance)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${local.resource_prefix}-audit-logs"
  }
}

# CloudWatch Alarms for DynamoDB throttling
resource "aws_cloudwatch_metric_alarm" "events_table_throttles" {
  alarm_name          = "${local.resource_prefix}-events-table-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "This alarm triggers when Events table experiences throttling"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.events.name
  }
}

resource "aws_cloudwatch_metric_alarm" "api_keys_table_throttles" {
  alarm_name          = "${local.resource_prefix}-api-keys-table-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "This alarm triggers when API Keys table experiences throttling"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.api_keys.name
  }
}
