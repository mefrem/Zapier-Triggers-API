# Development Environment

This directory contains Terraform configuration for the development environment.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.5.0 installed
3. S3 bucket and DynamoDB table for Terraform state management:
   - S3 Bucket: `zapier-triggers-api-terraform-state`
   - DynamoDB Table: `zapier-triggers-api-terraform-locks`

## Setup

### 1. Initialize Terraform Backend

```bash
cd infrastructure/terraform/environments/dev
terraform init
```

### 2. Review Configuration

```bash
terraform plan
```

### 3. Apply Infrastructure

```bash
terraform apply
```

## Configuration

All configuration values are defined in `terraform.tfvars`. Key settings:

- **Region**: us-east-1
- **VPC CIDR**: 10.0.0.0/16
- **DynamoDB**: Pay-per-request billing
- **Lambda Runtime**: Python 3.11
- **X-Ray Tracing**: Enabled

## Outputs

After applying, Terraform will output:

- VPC ID
- API Gateway URL
- Health endpoint URL
- DynamoDB table names
- SQS queue URLs
- CloudWatch dashboard name

## Destroying Resources

To tear down the environment:

```bash
terraform destroy
```

## State Management

- State file: Stored in S3 at `s3://zapier-triggers-api-terraform-state/dev/terraform.tfstate`
- State locking: DynamoDB table `zapier-triggers-api-terraform-locks`

## Notes

- This is a development environment with relaxed security settings
- NAT Gateway is enabled (incurs costs)
- All resources are tagged with `Environment=dev`
