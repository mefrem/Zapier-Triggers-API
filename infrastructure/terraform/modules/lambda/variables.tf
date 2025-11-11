# Lambda Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "lambda_runtime" {
  description = "Lambda runtime version"
  type        = string
  default     = "python3.11"
}

variable "vpc_id" {
  description = "VPC ID for Lambda functions"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Lambda functions"
  type        = list(string)
}

variable "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  type        = string
}

variable "events_table_name" {
  description = "DynamoDB Events table name"
  type        = string
}

variable "events_table_arn" {
  description = "DynamoDB Events table ARN"
  type        = string
  default     = ""
}

variable "api_keys_table_name" {
  description = "DynamoDB API Keys table name"
  type        = string
}

variable "api_keys_table_arn" {
  description = "DynamoDB API Keys table ARN"
  type        = string
  default     = ""
}

variable "event_queue_url" {
  description = "SQS event queue URL"
  type        = string
}

variable "event_queue_arn" {
  description = "SQS event queue ARN"
  type        = string
  default     = ""
}

variable "enable_xray_tracing" {
  description = "Enable X-Ray tracing for Lambda functions"
  type        = bool
  default     = true
}
