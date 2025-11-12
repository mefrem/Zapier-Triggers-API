# Deployment Verification Guide

This document provides step-by-step instructions for verifying that the Zapier Triggers API infrastructure has been successfully deployed to AWS.

## Prerequisites Verification

Before deploying, verify these prerequisites:

```bash
# Check Terraform version (should be >= 1.5.0)
terraform --version

# Check AWS CLI is configured
aws sts get-caller-identity

# Verify AWS region
aws configure get region
```

## Step 1: Create Backend Infrastructure

The Terraform backend (S3 bucket and DynamoDB table) must be created before running `terraform init`.

### Create S3 Bucket for State

```bash
# Create S3 bucket
aws s3 mb s3://zapier-triggers-api-terraform-state --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket zapier-triggers-api-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket zapier-triggers-api-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Verify bucket exists
aws s3 ls s3://zapier-triggers-api-terraform-state
```

### Create DynamoDB Table for State Locking

```bash
# Create DynamoDB table
aws dynamodb create-table \
  --table-name zapier-triggers-api-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Verify table exists
aws dynamodb describe-table \
  --table-name zapier-triggers-api-terraform-locks \
  --query 'Table.TableStatus'
```

Expected output: `"ACTIVE"`

## Step 2: Initialize Terraform

```bash
cd infrastructure/terraform/environments/dev

# Initialize Terraform (downloads providers, configures backend)
terraform init

# Verify initialization
terraform validate

# Format configuration files
terraform fmt -recursive
```

**Verification**: You should see:
- `.terraform/` directory created
- `.terraform.lock.hcl` file created
- Message: "Terraform has been successfully initialized!"

## Step 3: Plan Deployment

```bash
# Generate execution plan
terraform plan -out=tfplan

# Review the plan carefully
terraform show tfplan
```

**Verification**: Check that plan includes:
- VPC and networking resources (subnets, IGW, NAT Gateway, security groups)
- 3 DynamoDB tables (events, api-keys, audit-logs)
- 2 SQS queues (main queue, DLQ)
- 2 Lambda functions (health check, custom authorizer)
- API Gateway REST API with /health endpoint
- CloudWatch dashboard and alarms
- IAM roles and policies

## Step 4: Apply Configuration

```bash
# Apply the Terraform configuration
terraform apply tfplan

# Wait for completion (typically 5-10 minutes)
```

**Verification**: You should see:
- "Apply complete! Resources: X added, 0 changed, 0 destroyed."
- Terraform outputs displayed (API Gateway URL, table names, etc.)

## Step 5: Verify Backend State

```bash
# Check that state file exists in S3
aws s3 ls s3://zapier-triggers-api-terraform-state/dev/

# Download and inspect state (optional)
aws s3 cp s3://zapier-triggers-api-terraform-state/dev/terraform.tfstate /tmp/terraform.tfstate
cat /tmp/terraform.tfstate | jq '.resources | length'
```

Expected: State file exists and contains resources

## Step 6: Verify AWS Resources

### Check VPC

```bash
# List VPCs
aws ec2 describe-vpcs \
  --filters "Name=tag:Project,Values=zapier-triggers-api" \
  --query 'Vpcs[*].[VpcId,CidrBlock,Tags[?Key==`Environment`].Value|[0]]' \
  --output table

# Check subnets (should have 2 public, 2 private)
aws ec2 describe-subnets \
  --filters "Name=tag:Project,Values=zapier-triggers-api" \
  --query 'Subnets[*].[SubnetId,CidrBlock,AvailabilityZone,Tags[?Key==`Type`].Value|[0]]' \
  --output table
```

### Check DynamoDB Tables

```bash
# List tables
aws dynamodb list-tables --query 'TableNames[?contains(@, `zapier-triggers-api`)]'

# Verify Events table
aws dynamodb describe-table \
  --table-name zapier-triggers-api-events-dev \
  --query '{Status:Table.TableStatus, BillingMode:Table.BillingModeSummary.BillingMode, StreamEnabled:Table.StreamSpecification.StreamEnabled, PITR:Table.ArchivalSummary.ArchivalDateTime}' \
  --output json

# Verify API Keys table with KeyHashIndex GSI
aws dynamodb describe-table \
  --table-name zapier-triggers-api-keys-dev \
  --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]' \
  --output table

# Verify Audit Logs table
aws dynamodb describe-table \
  --table-name zapier-triggers-api-audit-logs-dev \
  --query 'Table.{Status:TableStatus,TTL:TimeToLiveDescription.AttributeName}' \
  --output json
```

**Expected**:
- All tables in ACTIVE status
- Events table: TTL enabled, Streams enabled, PITR enabled
- API Keys table: KeyHashIndex GSI in ACTIVE status
- Audit Logs table: TTL enabled

### Check SQS Queues

```bash
# List queues
aws sqs list-queues --queue-name-prefix zapier-triggers

# Get main queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name zapier-triggers-events-dev --query 'QueueUrl' --output text)
echo "Queue URL: $QUEUE_URL"

# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names All \
  --query 'Attributes.{VisibilityTimeout:VisibilityTimeout,MessageRetentionPeriod:MessageRetentionPeriod,RedrivePolicy:RedrivePolicy}' \
  --output json

# Verify DLQ exists
aws sqs get-queue-url --queue-name zapier-triggers-events-dlq-dev
```

### Check Lambda Functions

```bash
# List Lambda functions
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `zapier-triggers-api`)].{Name:FunctionName,Runtime:Runtime,Status:State}' \
  --output table

# Check health check function
aws lambda get-function \
  --function-name zapier-triggers-api-health-check-dev \
  --query '{Status:Configuration.State, Runtime:Configuration.Runtime, Handler:Configuration.Handler}' \
  --output json

# Check custom authorizer function
aws lambda get-function \
  --function-name zapier-triggers-api-custom-authorizer-dev \
  --query '{Status:Configuration.State, Runtime:Configuration.Runtime, Handler:Configuration.Handler}' \
  --output json

# Test health check Lambda directly
aws lambda invoke \
  --function-name zapier-triggers-api-health-check-dev \
  --payload '{}' \
  /tmp/health-response.json

cat /tmp/health-response.json | jq '.'
```

**Expected**: Both Lambda functions in ACTIVE state, health check returns 200

### Check API Gateway

```bash
# List REST APIs
aws apigateway get-rest-apis \
  --query 'items[?contains(name, `zapier-triggers-api`)].{Name:name,ID:id,CreatedDate:createdDate}' \
  --output table

# Get API ID
API_ID=$(aws apigateway get-rest-apis \
  --query 'items[?contains(name, `zapier-triggers-api-dev`)].id' \
  --output text)

echo "API Gateway ID: $API_ID"

# Get deployment stages
aws apigateway get-stages \
  --rest-api-id $API_ID \
  --query 'item[*].{Stage:stageName,DeploymentId:deploymentId,LastUpdated:lastUpdatedDate}' \
  --output table

# Get resources (should include /health)
aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[*].{Path:path,Methods:resourceMethods}' \
  --output table

# Get API Gateway URL
REGION=$(aws configure get region)
API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/dev"
echo "API Gateway URL: $API_URL"
```

### Check CloudWatch Resources

```bash
# List CloudWatch dashboards
aws cloudwatch list-dashboards \
  --query 'DashboardEntries[?contains(DashboardName, `zapier-triggers-api`)]' \
  --output table

# List CloudWatch alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix zapier-triggers-api \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue,Metric:MetricName}' \
  --output table
```

## Step 7: Test Health Check Endpoint

### Test via API Gateway

```bash
# Get API Gateway URL from Terraform outputs
API_URL=$(cd infrastructure/terraform/environments/dev && terraform output -raw api_gateway_url)

# Test health endpoint (no authentication required)
curl -X GET "${API_URL}/health" -H "Content-Type: application/json" | jq '.'

# Or with verbose output
curl -v -X GET "${API_URL}/health"
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T21:00:00.000Z",
  "version": "1.0.0",
  "environment": "dev",
  "checks": {
    "dynamodb": true,
    "environment_config": true
  }
}
```

**Expected HTTP Status**: `200 OK`

### Test via Direct Lambda Invocation

```bash
# Invoke health check Lambda directly
aws lambda invoke \
  --function-name zapier-triggers-api-health-check-dev \
  --payload '{"httpMethod":"GET","path":"/health"}' \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  /tmp/health-direct.json | base64 -d

# View response
cat /tmp/health-direct.json | jq '.body | fromjson'
```

## Step 8: Verify Resource Tags

```bash
# Check VPC tags
aws ec2 describe-vpcs \
  --filters "Name=tag:Project,Values=zapier-triggers-api" \
  --query 'Vpcs[*].Tags' \
  --output json

# Check DynamoDB tags
aws dynamodb list-tags-of-resource \
  --resource-arn $(aws dynamodb describe-table --table-name zapier-triggers-api-events-dev --query 'Table.TableArn' --output text) \
  --output json
```

**Expected Tags**:
- Project: zapier-triggers-api
- Environment: dev
- ManagedBy: terraform

## Step 9: Verify Terraform Outputs

```bash
cd infrastructure/terraform/environments/dev

# Display all outputs
terraform output

# Get specific outputs
terraform output api_gateway_url
terraform output vpc_id
terraform output events_table_name
terraform output health_check_lambda_arn
terraform output custom_authorizer_lambda_arn
```

## Deployment Verification Checklist

Use this checklist to confirm successful deployment:

- [ ] Backend infrastructure created (S3 bucket, DynamoDB table)
- [ ] Terraform initialization completed successfully
- [ ] Terraform plan reviewed and validated
- [ ] Terraform apply completed without errors
- [ ] Terraform state file exists in S3
- [ ] VPC created with correct CIDR (10.0.0.0/16)
- [ ] 2 public subnets created across 2 AZs
- [ ] 2 private subnets created across 2 AZs
- [ ] Internet Gateway and NAT Gateway created
- [ ] DynamoDB Events table created with TTL and Streams enabled
- [ ] DynamoDB API Keys table created with KeyHashIndex GSI
- [ ] DynamoDB Audit Logs table created with TTL enabled
- [ ] Main SQS queue created (zapier-triggers-events-dev)
- [ ] Dead letter queue created (zapier-triggers-events-dlq-dev)
- [ ] Health check Lambda function deployed and ACTIVE
- [ ] Custom authorizer Lambda function deployed and ACTIVE
- [ ] API Gateway REST API created
- [ ] API Gateway /health endpoint configured
- [ ] API Gateway deployment created (dev stage)
- [ ] CloudWatch dashboard created
- [ ] CloudWatch alarms configured
- [ ] Health check endpoint returns 200 OK
- [ ] Health check response includes all required fields
- [ ] Resource tags match organizational standards
- [ ] Terraform outputs display correctly

## Troubleshooting

### Terraform Backend Error

**Error**: "Error: Failed to get existing workspaces: S3 bucket does not exist"

**Solution**: Create S3 bucket and DynamoDB table as described in Step 1

### Lambda Function Fails to Deploy

**Error**: "Error creating Lambda function: InvalidParameterValueException"

**Solution**:
1. Verify handler files exist in `services/api/src/handlers/`
2. Check that ZIP file was created correctly
3. Verify IAM role has correct permissions

### API Gateway 403 Forbidden

**Error**: Health endpoint returns 403

**Solution**:
1. Verify API Gateway deployment exists
2. Check that custom authorizer is NOT applied to /health endpoint
3. Ensure resource policy allows public access to /health

### DynamoDB Table Not Found

**Error**: Health check fails with "ResourceNotFoundException"

**Solution**:
1. Verify table name environment variable is set correctly in Lambda
2. Check that Lambda has IAM permissions to access DynamoDB
3. Verify table exists in correct AWS region

### State Lock Error

**Error**: "Error: Error acquiring the state lock"

**Solution**:
```bash
# List locks
aws dynamodb scan --table-name zapier-triggers-api-terraform-locks

# Force unlock (use with caution)
terraform force-unlock LOCK_ID
```

## Rollback Procedure

If deployment fails or needs to be rolled back:

```bash
cd infrastructure/terraform/environments/dev

# Destroy all resources
terraform destroy

# Confirm destruction
# Type "yes" when prompted

# Verify all resources deleted
aws ec2 describe-vpcs --filters "Name=tag:Project,Values=zapier-triggers-api"
aws dynamodb list-tables | grep zapier-triggers-api
aws sqs list-queues | grep zapier-triggers
```

## Next Steps

After successful deployment verification:

1. **Test Authentication**: Deploy a test API key to DynamoDB and test custom authorizer
2. **Load Testing**: Run load tests against health endpoint to verify scalability
3. **Monitoring**: Set up CloudWatch alerts for production issues
4. **Backup Verification**: Confirm point-in-time recovery is working for DynamoDB
5. **Documentation**: Update runbooks with actual deployed resource IDs

## Resources

- Terraform AWS Provider Documentation: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- AWS CLI Reference: https://awscli.amazonaws.com/v2/documentation/api/latest/index.html
- Project Architecture: `docs/architecture.md`
- Terraform README: `infrastructure/terraform/README.md`
