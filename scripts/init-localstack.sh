#!/bin/bash

# LocalStack initialization script
# Creates DynamoDB tables, SQS queues, and Secrets Manager secrets for local development

set -e

echo "Initializing LocalStack resources..."

# Set AWS endpoint for LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
sleep 5

# Create DynamoDB Events Table
echo "Creating Events table..."
aws dynamodb create-table \
  --endpoint-url $AWS_ENDPOINT_URL \
  --table-name zapier-triggers-api-events-dev \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=timestamp#event_id,AttributeType=S \
    AttributeName=event_type#timestamp,AttributeType=S \
    AttributeName=status#timestamp,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=timestamp#event_id,KeyType=RANGE \
  --global-secondary-indexes \
    '[
      {
        "IndexName": "EventTypeIndex",
        "KeySchema": [
          {"AttributeName": "user_id", "KeyType": "HASH"},
          {"AttributeName": "event_type#timestamp", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      },
      {
        "IndexName": "StatusIndex",
        "KeySchema": [
          {"AttributeName": "user_id", "KeyType": "HASH"},
          {"AttributeName": "status#timestamp", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      }
    ]' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_DEFAULT_REGION

# Create DynamoDB API Keys Table
echo "Creating API Keys table..."
aws dynamodb create-table \
  --endpoint-url $AWS_ENDPOINT_URL \
  --table-name zapier-triggers-api-keys-dev \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=key_id,AttributeType=S \
    AttributeName=key_hash,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=key_id,KeyType=RANGE \
  --global-secondary-indexes \
    '[
      {
        "IndexName": "KeyHashIndex",
        "KeySchema": [
          {"AttributeName": "key_hash", "KeyType": "HASH"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      }
    ]' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_DEFAULT_REGION

# Create DynamoDB Audit Logs Table
echo "Creating Audit Logs table..."
aws dynamodb create-table \
  --endpoint-url $AWS_ENDPOINT_URL \
  --table-name zapier-triggers-api-audit-logs-dev \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=timestamp#log_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=timestamp#log_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_DEFAULT_REGION

# Create SQS Queues
echo "Creating SQS queues..."
DLQ_URL=$(aws sqs create-queue \
  --endpoint-url $AWS_ENDPOINT_URL \
  --queue-name zapier-triggers-events-dlq-dev \
  --region $AWS_DEFAULT_REGION \
  --output text --query 'QueueUrl')

aws sqs create-queue \
  --endpoint-url $AWS_ENDPOINT_URL \
  --queue-name zapier-triggers-events-dev \
  --region $AWS_DEFAULT_REGION \
  --attributes VisibilityTimeout=900,MessageRetentionPeriod=1209600

# Create Secrets Manager Secret
echo "Creating Secrets Manager secret..."
aws secretsmanager create-secret \
  --endpoint-url $AWS_ENDPOINT_URL \
  --name zapier-triggers-api-dev-api-keys \
  --secret-string '{"keys": []}' \
  --region $AWS_DEFAULT_REGION

# Create SSM Parameters
echo "Creating SSM parameters..."
aws ssm put-parameter \
  --endpoint-url $AWS_ENDPOINT_URL \
  --name /zapier-triggers-api/dev/api-version \
  --value "1.0.0" \
  --type String \
  --region $AWS_DEFAULT_REGION

aws ssm put-parameter \
  --endpoint-url $AWS_ENDPOINT_URL \
  --name /zapier-triggers-api/dev/rate-limit-default \
  --value "1000" \
  --type String \
  --region $AWS_DEFAULT_REGION

echo "LocalStack initialization complete!"
