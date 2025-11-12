# SQS Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "visibility_timeout" {
  description = "Visibility timeout in seconds (time to process message before it becomes visible again)"
  type        = number
  default     = 900 # 15 minutes
}

variable "message_retention" {
  description = "Message retention period in seconds"
  type        = number
  default     = 1209600 # 14 days
}
