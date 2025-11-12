# Lambda Module Outputs

output "lambda_execution_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_execution.arn
}

output "health_check_function_arn" {
  description = "Health check Lambda function ARN"
  value       = aws_lambda_function.health_check.arn
}

output "health_check_function_name" {
  description = "Health check Lambda function name"
  value       = aws_lambda_function.health_check.function_name
}

output "health_check_invoke_arn" {
  description = "Health check Lambda invoke ARN"
  value       = aws_lambda_function.health_check.invoke_arn
}

output "custom_authorizer_function_arn" {
  description = "Custom authorizer Lambda function ARN"
  value       = aws_lambda_function.custom_authorizer.arn
}

output "custom_authorizer_function_name" {
  description = "Custom authorizer Lambda function name"
  value       = aws_lambda_function.custom_authorizer.function_name
}

output "custom_authorizer_invoke_arn" {
  description = "Custom authorizer Lambda invoke ARN"
  value       = aws_lambda_function.custom_authorizer.invoke_arn
}
