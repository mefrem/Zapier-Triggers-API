# DynamoDB Module Outputs

output "events_table_name" {
  description = "Events table name"
  value       = aws_dynamodb_table.events.name
}

output "events_table_arn" {
  description = "Events table ARN"
  value       = aws_dynamodb_table.events.arn
}

output "events_table_stream_arn" {
  description = "Events table stream ARN"
  value       = aws_dynamodb_table.events.stream_arn
}

output "api_keys_table_name" {
  description = "API Keys table name"
  value       = aws_dynamodb_table.api_keys.name
}

output "api_keys_table_arn" {
  description = "API Keys table ARN"
  value       = aws_dynamodb_table.api_keys.arn
}

output "audit_logs_table_name" {
  description = "Audit Logs table name"
  value       = aws_dynamodb_table.audit_logs.name
}

output "audit_logs_table_arn" {
  description = "Audit Logs table ARN"
  value       = aws_dynamodb_table.audit_logs.arn
}
