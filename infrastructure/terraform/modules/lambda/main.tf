# Lambda Module - Serverless Function Management

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
}

# IAM Role for Lambda Functions
resource "aws_iam_role" "lambda_execution" {
  name = "${local.resource_prefix}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.resource_prefix}-lambda-execution-role"
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC execution policy
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom IAM Policy for Lambda Functions
resource "aws_iam_policy" "lambda_custom_policy" {
  name        = "${local.resource_prefix}-lambda-custom-policy"
  description = "Custom policy for Lambda functions to access DynamoDB, SQS, and Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          var.events_table_arn,
          "${var.events_table_arn}/index/*",
          var.api_keys_table_arn,
          "${var.api_keys_table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          var.event_queue_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:${local.resource_prefix}-api-keys-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:*:*:parameter/${var.project_name}/${var.environment}/*"
        ]
      }
    ]
  })

  tags = {
    Name = "${local.resource_prefix}-lambda-custom-policy"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_custom_policy" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_custom_policy.arn
}

# X-Ray Tracing Policy
resource "aws_iam_role_policy_attachment" "lambda_xray" {
  count      = var.enable_xray_tracing ? 1 : 0
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Health Check Lambda Function
resource "aws_lambda_function" "health_check" {
  filename         = data.archive_file.health_check_lambda.output_path
  function_name    = "${local.resource_prefix}-health-check"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "health.lambda_handler"
  source_code_hash = data.archive_file.health_check_lambda.output_base64sha256
  runtime          = var.lambda_runtime
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT        = var.environment
      EVENTS_TABLE_NAME  = var.events_table_name
      API_KEYS_TABLE_NAME = var.api_keys_table_name
      LOG_LEVEL          = "INFO"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  tags = {
    Name = "${local.resource_prefix}-health-check"
  }
}

# Custom Authorizer Lambda Function
resource "aws_lambda_function" "custom_authorizer" {
  filename         = data.archive_file.custom_authorizer_lambda.output_path
  function_name    = "${local.resource_prefix}-custom-authorizer"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "auth.lambda_handler"
  source_code_hash = data.archive_file.custom_authorizer_lambda.output_base64sha256
  runtime          = var.lambda_runtime
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT         = var.environment
      API_KEYS_TABLE_NAME = var.api_keys_table_name
      LOG_LEVEL           = "INFO"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  tags = {
    Name = "${local.resource_prefix}-custom-authorizer"
  }
}

# Lambda Permission for API Gateway to invoke Health Check
resource "aws_lambda_permission" "health_check_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_check.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:*:*:*/*/*"
}

# Lambda Permission for API Gateway to invoke Custom Authorizer
resource "aws_lambda_permission" "custom_authorizer_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.custom_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:*:*:*/*/*"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "health_check" {
  name              = "/aws/lambda/${aws_lambda_function.health_check.function_name}"
  retention_in_days = 14

  tags = {
    Name = "${local.resource_prefix}-health-check-logs"
  }
}

resource "aws_cloudwatch_log_group" "custom_authorizer" {
  name              = "/aws/lambda/${aws_lambda_function.custom_authorizer.function_name}"
  retention_in_days = 14

  tags = {
    Name = "${local.resource_prefix}-custom-authorizer-logs"
  }
}

# Package Lambda functions
data "archive_file" "health_check_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../../services/api/src/handlers"
  output_path = "${path.module}/health_check_lambda.zip"
  excludes    = ["__pycache__", "*.pyc", ".pytest_cache"]
}

data "archive_file" "custom_authorizer_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../../services/api/src/handlers"
  output_path = "${path.module}/custom_authorizer_lambda.zip"
  excludes    = ["__pycache__", "*.pyc", ".pytest_cache"]
}
