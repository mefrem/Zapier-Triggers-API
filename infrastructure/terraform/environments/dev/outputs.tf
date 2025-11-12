# Development Environment Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = module.triggers_api.vpc_id
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = module.triggers_api.api_gateway_url
}

output "health_endpoint_url" {
  description = "Health check endpoint URL"
  value       = "${module.triggers_api.api_gateway_url}/health"
}

output "events_table_name" {
  description = "Events table name"
  value       = module.triggers_api.events_table_name
}

output "api_keys_table_name" {
  description = "API Keys table name"
  value       = module.triggers_api.api_keys_table_name
}

output "event_queue_url" {
  description = "Event queue URL"
  value       = module.triggers_api.event_queue_url
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = module.triggers_api.cloudwatch_dashboard_name
}
