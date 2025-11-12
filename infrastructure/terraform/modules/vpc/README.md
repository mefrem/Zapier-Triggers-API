# VPC Module

This module creates a VPC with public and private subnets across multiple availability zones for high availability.

## Architecture

- **VPC**: CIDR block 10.0.0.0/16
- **Public Subnets**: 10.0.1.0/24, 10.0.2.0/24 (for NAT Gateway)
- **Private Subnets**: 10.0.10.0/24, 10.0.11.0/24 (for Lambda functions)
- **Internet Gateway**: For public internet access
- **NAT Gateway**: For private subnet outbound internet access
- **VPC Endpoints**: DynamoDB, S3, Secrets Manager (cost optimization)

## Security Groups

- **Lambda Security Group**: Allows all outbound traffic, no inbound (functions initiated from within VPC)
- **API Gateway Security Group**: Allows HTTPS (443) inbound from anywhere

## Usage

```hcl
module "vpc" {
  source = "./modules/vpc"

  project_name       = "zapier-triggers-api"
  environment        = "dev"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  enable_nat_gateway = true
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name for resource naming | string | - |
| environment | Environment name (dev, staging, production) | string | - |
| vpc_cidr | CIDR block for VPC | string | - |
| availability_zones | List of availability zones | list(string) | - |
| enable_nat_gateway | Enable NAT Gateway | bool | true |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC ID |
| public_subnet_ids | Public subnet IDs |
| private_subnet_ids | Private subnet IDs |
| lambda_security_group_id | Lambda security group ID |
