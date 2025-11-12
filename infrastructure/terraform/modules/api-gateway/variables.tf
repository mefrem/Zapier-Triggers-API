# API Gateway Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "v1"
}

variable "health_check_function_arn" {
  description = "Health check Lambda function ARN"
  type        = string
}

variable "health_check_function_name" {
  description = "Health check Lambda function name"
  type        = string
}

variable "health_check_function_invoke_arn" {
  description = "Health check Lambda function invoke ARN"
  type        = string
  default     = ""
}

variable "custom_authorizer_function_arn" {
  description = "Custom authorizer Lambda function ARN"
  type        = string
}

variable "custom_authorizer_function_invoke_arn" {
  description = "Custom authorizer Lambda function invoke ARN"
  type        = string
  default     = ""
}

variable "enable_access_logs" {
  description = "Enable API Gateway access logs"
  type        = bool
  default     = true
}
