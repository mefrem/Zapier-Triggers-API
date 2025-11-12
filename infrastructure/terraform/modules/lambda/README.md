# Lambda Module

This module creates Lambda functions for the Triggers API, including execution roles and permissions.

## Functions

### Health Check Lambda

- **Purpose**: Health check endpoint returning API status
- **Handler**: `health.lambda_handler`
- **Runtime**: Python 3.11
- **Timeout**: 30 seconds
- **Memory**: 256 MB
- **VPC**: Deployed in private subnets
- **Tracing**: X-Ray enabled (configurable)

### Custom Authorizer Lambda

- **Purpose**: API Gateway custom authorizer for API key validation
- **Handler**: `auth.lambda_handler`
- **Runtime**: Python 3.11
- **Timeout**: 10 seconds
- **Memory**: 256 MB
- **VPC**: Deployed in private subnets
- **Caching**: Authorization results cached by API Gateway (5 minutes)

## IAM Permissions

Lambda execution role includes permissions for:
- CloudWatch Logs (logging)
- VPC networking (ENI management)
- DynamoDB (read/write Events and API Keys tables)
- SQS (send/receive messages)
- Secrets Manager (read API keys)
- SSM Parameter Store (read configuration)
- X-Ray (distributed tracing)

## Deployment

Lambda functions are packaged from `services/api/src/handlers/` directory. The module automatically creates ZIP files for deployment.

## Usage

```hcl
module "lambda" {
  source = "./modules/lambda"

  project_name             = "zapier-triggers-api"
  environment              = "dev"
  lambda_runtime           = "python3.11"
  vpc_id                   = module.vpc.vpc_id
  private_subnet_ids       = module.vpc.private_subnet_ids
  lambda_security_group_id = module.vpc.lambda_security_group_id
  events_table_name        = module.dynamodb.events_table_name
  api_keys_table_name      = module.dynamodb.api_keys_table_name
  event_queue_url          = module.sqs.event_queue_url
  enable_xray_tracing      = true
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name | string | - |
| environment | Environment name | string | - |
| lambda_runtime | Lambda runtime | string | python3.11 |
| vpc_id | VPC ID | string | - |
| private_subnet_ids | Private subnet IDs | list(string) | - |
| lambda_security_group_id | Lambda security group ID | string | - |
| events_table_name | Events table name | string | - |
| api_keys_table_name | API Keys table name | string | - |
| event_queue_url | Event queue URL | string | - |
| enable_xray_tracing | Enable X-Ray | bool | true |

## Outputs

| Name | Description |
|------|-------------|
| health_check_function_arn | Health check function ARN |
| health_check_function_name | Health check function name |
| custom_authorizer_function_arn | Custom authorizer function ARN |
| custom_authorizer_function_name | Custom authorizer function name |
