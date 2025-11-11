# SQS Module

This module creates SQS queues for event buffering and dead letter queue for failed events.

## Architecture

### Main Event Queue

- **Purpose**: Buffer events for asynchronous processing
- **Visibility Timeout**: 15 minutes (configurable)
- **Message Retention**: 14 days
- **Long Polling**: Enabled (20 seconds) for cost optimization
- **Dead Letter Queue**: Messages move to DLQ after 3 failed processing attempts

### Dead Letter Queue (DLQ)

- **Purpose**: Store events that failed processing after max retries
- **Retention**: 14 days
- **Monitoring**: CloudWatch alarm triggers when messages appear in DLQ

## CloudWatch Alarms

- **Queue Depth**: Alerts when main queue exceeds 1000 messages (indicates processing delays)
- **DLQ Depth**: Alerts when messages appear in DLQ (indicates systematic failures)
- **Message Age**: Alerts when oldest message exceeds 1 hour (indicates processing bottleneck)

## Usage

```hcl
module "sqs" {
  source = "./modules/sqs"

  project_name       = "zapier-triggers-api"
  environment        = "dev"
  visibility_timeout = 900  # 15 minutes
  message_retention  = 1209600  # 14 days
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name | string | - |
| environment | Environment name | string | - |
| visibility_timeout | Visibility timeout in seconds | number | 900 |
| message_retention | Message retention in seconds | number | 1209600 |

## Outputs

| Name | Description |
|------|-------------|
| event_queue_url | Main event queue URL |
| event_queue_arn | Main event queue ARN |
| event_queue_name | Main event queue name |
| event_dlq_url | Dead letter queue URL |
| event_dlq_arn | Dead letter queue ARN |
| event_dlq_name | Dead letter queue name |
