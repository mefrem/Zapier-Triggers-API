# API Gateway Module

This module creates an API Gateway REST API with health check endpoint and custom authorizer.

## Architecture

### REST API Configuration

- **Type**: Regional API Gateway
- **Stage**: v1 (configurable)
- **Endpoints**:
  - `GET /health` - Health check (no authentication)
- **Custom Authorizer**: Token-based authorizer validating X-API-Key header
- **CORS**: Enabled for all endpoints
- **Throttling**: 1000 requests/sec with 2000 burst
- **Access Logs**: CloudWatch Logs (structured JSON)
- **X-Ray Tracing**: Enabled

### Security

- **Authentication**: Custom authorizer Lambda validates API keys
- **Authorization Caching**: Results cached for 5 minutes
- **Rate Limiting**: Enforced via usage plan (1000 req/min per key)

### Endpoints

#### GET /health

- **Authentication**: None
- **Purpose**: Health check and API status
- **Response**: 200 OK with status information
- **CORS**: Enabled

## Usage

```hcl
module "api_gateway" {
  source = "./modules/api-gateway"

  project_name                      = "zapier-triggers-api"
  environment                       = "dev"
  stage_name                        = "v1"
  health_check_function_arn         = module.lambda.health_check_function_arn
  health_check_function_name        = module.lambda.health_check_function_name
  custom_authorizer_function_arn    = module.lambda.custom_authorizer_function_arn
  enable_access_logs                = true
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name | string | - |
| environment | Environment name | string | - |
| stage_name | API stage name | string | v1 |
| health_check_function_arn | Health check Lambda ARN | string | - |
| health_check_function_name | Health check Lambda name | string | - |
| custom_authorizer_function_arn | Custom authorizer Lambda ARN | string | - |
| enable_access_logs | Enable access logs | bool | true |

## Outputs

| Name | Description |
|------|-------------|
| api_id | API Gateway ID |
| api_url | API invoke URL |
| api_execution_arn | API execution ARN |
| stage_name | Stage name |
| health_endpoint_url | Health check endpoint URL |
| custom_authorizer_id | Custom authorizer ID |
| usage_plan_id | Usage plan ID |
