# Monitoring Module Outputs

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "dashboard_arn" {
  description = "CloudWatch dashboard ARN"
  value       = aws_cloudwatch_dashboard.main.dashboard_arn
}

output "api_error_alarm_arn" {
  description = "API error rate alarm ARN"
  value       = aws_cloudwatch_metric_alarm.api_error_rate.arn
}

output "lambda_error_alarm_arn" {
  description = "Lambda error alarm ARN"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.arn
}

output "api_latency_alarm_arn" {
  description = "API latency alarm ARN"
  value       = aws_cloudwatch_metric_alarm.api_latency.arn
}
