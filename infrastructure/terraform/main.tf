# Root Terraform Configuration
# Orchestrates all infrastructure modules

locals {
  resource_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# VPC Module - Networking infrastructure
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_nat_gateway = var.enable_nat_gateway
}

# DynamoDB Module - Event storage, API keys, audit logs
module "dynamodb" {
  source = "./modules/dynamodb"

  project_name      = var.project_name
  environment       = var.environment
  billing_mode      = var.dynamodb_billing_mode
  events_ttl_days   = var.events_ttl_days
  audit_logs_ttl_days = var.audit_logs_ttl_days
}

# SQS Module - Event queuing and dead letter queue
module "sqs" {
  source = "./modules/sqs"

  project_name          = var.project_name
  environment           = var.environment
  visibility_timeout    = var.sqs_visibility_timeout
  message_retention     = var.sqs_message_retention
}

# Lambda Module - Serverless function management
module "lambda" {
  source = "./modules/lambda"

  project_name             = var.project_name
  environment              = var.environment
  lambda_runtime           = var.lambda_runtime
  vpc_id                   = module.vpc.vpc_id
  private_subnet_ids       = module.vpc.private_subnet_ids
  lambda_security_group_id = module.vpc.lambda_security_group_id
  events_table_name        = module.dynamodb.events_table_name
  events_table_arn         = module.dynamodb.events_table_arn
  api_keys_table_name      = module.dynamodb.api_keys_table_name
  api_keys_table_arn       = module.dynamodb.api_keys_table_arn
  event_queue_url          = module.sqs.event_queue_url
  event_queue_arn          = module.sqs.event_queue_arn
  enable_xray_tracing      = var.enable_xray_tracing
}

# API Gateway Module - REST API management
module "api_gateway" {
  source = "./modules/api-gateway"

  project_name                         = var.project_name
  environment                          = var.environment
  stage_name                           = var.api_gateway_stage_name
  health_check_function_arn            = module.lambda.health_check_function_arn
  health_check_function_name           = module.lambda.health_check_function_name
  health_check_function_invoke_arn     = module.lambda.health_check_invoke_arn
  custom_authorizer_function_arn       = module.lambda.custom_authorizer_function_arn
  custom_authorizer_function_invoke_arn = module.lambda.custom_authorizer_invoke_arn
  enable_access_logs                   = var.enable_api_gateway_access_logs
}

# Monitoring Module - CloudWatch dashboards and alarms
module "monitoring" {
  source = "./modules/monitoring"

  project_name              = var.project_name
  environment               = var.environment
  api_gateway_id            = module.api_gateway.api_id
  api_gateway_stage_name    = var.api_gateway_stage_name
  health_check_function_name = module.lambda.health_check_function_name
  events_table_name         = module.dynamodb.events_table_name
  event_queue_name          = module.sqs.event_queue_name
  event_dlq_name            = module.sqs.event_dlq_name
}

# Secrets Manager - API key storage
resource "aws_secretsmanager_secret" "api_keys" {
  name        = "${local.resource_prefix}-api-keys"
  description = "API keys for Zapier Triggers API authentication"

  recovery_window_in_days = 30

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "api_keys_initial" {
  secret_id     = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    keys = []
  })
}

# SSM Parameter Store - Configuration parameters
resource "aws_ssm_parameter" "api_version" {
  name        = "/${var.project_name}/${var.environment}/api-version"
  description = "API version"
  type        = "String"
  value       = "1.0.0"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "rate_limit_default" {
  name        = "/${var.project_name}/${var.environment}/rate-limit-default"
  description = "Default rate limit per API key (requests per minute)"
  type        = "String"
  value       = "1000"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "event_retention_days" {
  name        = "/${var.project_name}/${var.environment}/event-retention-days"
  description = "Event retention period in days"
  type        = "String"
  value       = tostring(var.events_ttl_days)

  tags = local.common_tags
}
