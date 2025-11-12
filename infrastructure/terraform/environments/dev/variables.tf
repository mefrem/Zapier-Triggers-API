# Development Environment Variables

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway"
  type        = bool
  default     = true
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "events_ttl_days" {
  description = "Events TTL in days"
  type        = number
  default     = 30
}

variable "audit_logs_ttl_days" {
  description = "Audit logs TTL in days"
  type        = number
  default     = 2557
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout"
  type        = number
  default     = 900
}

variable "sqs_message_retention" {
  description = "SQS message retention"
  type        = number
  default     = 1209600
}

variable "enable_xray_tracing" {
  description = "Enable X-Ray tracing"
  type        = bool
  default     = true
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.11"
}

variable "api_gateway_stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "v1"
}

variable "enable_api_gateway_access_logs" {
  description = "Enable API Gateway access logs"
  type        = bool
  default     = true
}
