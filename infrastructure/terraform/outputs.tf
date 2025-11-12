# Root Module Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = module.api_gateway.api_url
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = module.api_gateway.api_id
}

output "events_table_name" {
  description = "DynamoDB Events table name"
  value       = module.dynamodb.events_table_name
}

output "api_keys_table_name" {
  description = "DynamoDB API Keys table name"
  value       = module.dynamodb.api_keys_table_name
}

output "audit_logs_table_name" {
  description = "DynamoDB Audit Logs table name"
  value       = module.dynamodb.audit_logs_table_name
}

output "event_queue_url" {
  description = "SQS event queue URL"
  value       = module.sqs.event_queue_url
}

output "event_dlq_url" {
  description = "SQS dead letter queue URL"
  value       = module.sqs.event_dlq_url
}

output "health_check_function_arn" {
  description = "Health check Lambda function ARN"
  value       = module.lambda.health_check_function_arn
}

output "secrets_manager_secret_arn" {
  description = "Secrets Manager secret ARN for API keys"
  value       = aws_secretsmanager_secret.api_keys.arn
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = module.monitoring.dashboard_name
}
