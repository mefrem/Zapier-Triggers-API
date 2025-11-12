# Terraform Infrastructure

This directory contains Terraform configuration for the Zapier Triggers API infrastructure.

## Structure

```
terraform/
├── modules/           # Reusable Terraform modules
│   ├── vpc/          # VPC and networking
│   ├── dynamodb/     # DynamoDB tables
│   ├── sqs/          # SQS queues
│   ├── lambda/       # Lambda functions
│   ├── api-gateway/  # API Gateway REST API
│   └── monitoring/   # CloudWatch dashboards and alarms
├── environments/     # Environment-specific configurations
│   ├── dev/
│   ├── staging/
│   └── production/
├── main.tf          # Root module
├── variables.tf     # Root variables
├── outputs.tf       # Root outputs
└── backend.tf       # S3 backend configuration
```

## Prerequisites

1. **Terraform** >= 1.5.0
2. **AWS CLI** configured with appropriate credentials
3. **S3 bucket** for Terraform state: `zapier-triggers-api-terraform-state`
4. **DynamoDB table** for state locking: `zapier-triggers-api-terraform-locks`

## Quick Start

### 1. Create Terraform Backend Resources

Before using Terraform, create the S3 bucket and DynamoDB table for state management:

```bash
# Create S3 bucket
aws s3 mb s3://zapier-triggers-api-terraform-state --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket zapier-triggers-api-terraform-state \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for locking
aws dynamodb create-table \
  --table-name zapier-triggers-api-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 2. Deploy to Development

```bash
cd environments/dev
terraform init
terraform plan
terraform apply
```

### 3. Deploy to Staging

```bash
cd environments/staging
terraform init
terraform plan
terraform apply
```

### 4. Deploy to Production

```bash
cd environments/production
terraform init
terraform plan
terraform apply
```

## Modules

### VPC Module

Creates VPC with public and private subnets, NAT Gateway, and VPC endpoints.

**Resources**: VPC, Subnets, Internet Gateway, NAT Gateway, Security Groups, VPC Endpoints

### DynamoDB Module

Creates DynamoDB tables for events, API keys, and audit logs with GSIs and TTL.

**Resources**: 3 DynamoDB tables with indexes, point-in-time recovery, and streams

### SQS Module

Creates SQS queues for event processing with dead letter queue.

**Resources**: Main event queue, DLQ, CloudWatch alarms

### Lambda Module

Creates Lambda functions with IAM roles and permissions.

**Resources**: Health check function, custom authorizer, execution role, CloudWatch logs

### API Gateway Module

Creates REST API with health check endpoint and custom authorizer.

**Resources**: REST API, resources, methods, deployment, stage, usage plan

### Monitoring Module

Creates CloudWatch dashboards and alarms for monitoring.

**Resources**: Dashboard, alarms for errors, latency, and queue depth

## Environment Variables

Configure these environment variables in each environment's `terraform.tfvars`:

- `aws_region` - AWS region (default: us-east-1)
- `environment` - Environment name (dev, staging, production)
- `vpc_cidr` - VPC CIDR block
- `availability_zones` - AZs for multi-AZ deployment
- `dynamodb_billing_mode` - PAY_PER_REQUEST or PROVISIONED
- `enable_xray_tracing` - Enable X-Ray tracing (true/false)

## Outputs

After applying, Terraform outputs important information:

- `api_gateway_url` - API Gateway invoke URL
- `health_endpoint_url` - Health check endpoint URL
- `vpc_id` - VPC ID
- `events_table_name` - Events table name
- `event_queue_url` - SQS queue URL
- `cloudwatch_dashboard_name` - Dashboard name

## Terraform Commands

```bash
# Initialize
terraform init

# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes
terraform apply

# Destroy resources
terraform destroy
```

## Best Practices

1. **Always run `terraform plan` before `terraform apply`**
2. **Use workspaces for environment isolation**
3. **Store sensitive values in AWS Secrets Manager, not in Terraform**
4. **Tag all resources appropriately**
5. **Enable state locking with DynamoDB**
6. **Review plans carefully in production**

## Troubleshooting

### State Lock Issues

If state is locked, identify and release the lock:

```bash
aws dynamodb scan --table-name zapier-triggers-api-terraform-locks
aws dynamodb delete-item --table-name zapier-triggers-api-terraform-locks --key '{"LockID": {"S": "LOCK_ID"}}'
```

### Lambda Deployment Issues

If Lambda functions fail to deploy, ensure source code is present in `services/api/src/handlers/`.

### VPC Endpoint Issues

If VPC endpoints fail, check IAM permissions for creating interface endpoints.

## Cost Optimization

- Use `enable_nat_gateway=false` in dev to save costs (requires VPC endpoints)
- Use `dynamodb_billing_mode=PROVISIONED` with auto-scaling in production
- Enable S3 lifecycle policies for old Terraform state versions
