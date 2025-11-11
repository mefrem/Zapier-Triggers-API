# Monitoring Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "api_gateway_id" {
  description = "API Gateway ID"
  type        = string
}

variable "api_gateway_stage_name" {
  description = "API Gateway stage name"
  type        = string
}

variable "health_check_function_name" {
  description = "Health check Lambda function name"
  type        = string
}

variable "events_table_name" {
  description = "DynamoDB Events table name"
  type        = string
}

variable "event_queue_name" {
  description = "SQS event queue name"
  type        = string
}

variable "event_dlq_name" {
  description = "SQS dead letter queue name"
  type        = string
}
