# Monitoring Module

This module creates CloudWatch dashboards and alarms for monitoring the Triggers API.

## Features

### CloudWatch Dashboard

Unified dashboard with key metrics:

- **API Gateway**: Request count, 4XX/5XX errors, latency (avg/p95/p99)
- **Lambda**: Invocations, errors, throttles, duration
- **DynamoDB**: Read/write capacity, throttling
- **SQS**: Message queue depth, messages sent/received, DLQ depth

### CloudWatch Alarms

- **API Error Rate**: Triggers when 5XX errors exceed 10 in 5 minutes
- **Lambda Errors**: Triggers when Lambda errors exceed 5 in 5 minutes
- **Lambda Duration**: Triggers when average duration exceeds 5 seconds
- **API Latency**: Triggers when P95 latency exceeds 1 second

### X-Ray Tracing

- Enabled on API Gateway and Lambda functions
- Traces request flow across services
- Identifies performance bottlenecks

## Metrics Collected

| Service | Metrics | Purpose |
|---------|---------|---------|
| API Gateway | Count, 4XXError, 5XXError, Latency | Track API health and performance |
| Lambda | Invocations, Errors, Throttles, Duration | Monitor function execution |
| DynamoDB | ReadCapacity, WriteCapacity, UserErrors | Track database performance and throttling |
| SQS | MessagesVisible, MessagesSent, MessagesReceived | Monitor event processing queue |

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name               = "zapier-triggers-api"
  environment                = "dev"
  api_gateway_id             = module.api_gateway.api_id
  api_gateway_stage_name     = "v1"
  health_check_function_name = module.lambda.health_check_function_name
  events_table_name          = module.dynamodb.events_table_name
  event_queue_name           = module.sqs.event_queue_name
  event_dlq_name             = module.sqs.event_dlq_name
}
```

## Inputs

| Name | Description | Type |
|------|-------------|------|
| project_name | Project name | string |
| environment | Environment name | string |
| api_gateway_id | API Gateway ID | string |
| api_gateway_stage_name | API stage name | string |
| health_check_function_name | Lambda function name | string |
| events_table_name | DynamoDB table name | string |
| event_queue_name | SQS queue name | string |
| event_dlq_name | SQS DLQ name | string |

## Outputs

| Name | Description |
|------|-------------|
| dashboard_name | CloudWatch dashboard name |
| dashboard_arn | CloudWatch dashboard ARN |
| api_error_alarm_arn | API error alarm ARN |
| lambda_error_alarm_arn | Lambda error alarm ARN |
| api_latency_alarm_arn | API latency alarm ARN |
