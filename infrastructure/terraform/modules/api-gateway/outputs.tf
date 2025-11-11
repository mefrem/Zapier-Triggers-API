# API Gateway Module Outputs

output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_arn" {
  description = "API Gateway REST API ARN"
  value       = aws_api_gateway_rest_api.main.arn
}

output "api_url" {
  description = "API Gateway invoke URL"
  value       = "${aws_api_gateway_stage.main.invoke_url}"
}

output "api_execution_arn" {
  description = "API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.main.execution_arn
}

output "stage_name" {
  description = "API Gateway stage name"
  value       = aws_api_gateway_stage.main.stage_name
}

output "health_endpoint_url" {
  description = "Health check endpoint URL"
  value       = "${aws_api_gateway_stage.main.invoke_url}/health"
}

output "custom_authorizer_id" {
  description = "Custom authorizer ID"
  value       = aws_api_gateway_authorizer.custom.id
}

output "usage_plan_id" {
  description = "Usage plan ID"
  value       = aws_api_gateway_usage_plan.main.id
}
