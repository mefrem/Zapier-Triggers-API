# DynamoDB Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "billing_mode" {
  description = "DynamoDB billing mode (PROVISIONED or PAY_PER_REQUEST)"
  type        = string
  default     = "PAY_PER_REQUEST"
  validation {
    condition     = contains(["PROVISIONED", "PAY_PER_REQUEST"], var.billing_mode)
    error_message = "Billing mode must be PROVISIONED or PAY_PER_REQUEST."
  }
}

variable "events_ttl_days" {
  description = "TTL for events table in days"
  type        = number
  default     = 30
}

variable "audit_logs_ttl_days" {
  description = "TTL for audit logs table in days"
  type        = number
  default     = 2557 # 7 years
}
