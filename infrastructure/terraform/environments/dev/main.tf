# Development Environment Configuration

terraform {
  backend "s3" {
    bucket         = "zapier-triggers-api-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "zapier-triggers-api-terraform-locks"
    encrypt        = true
  }

  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "zapier-triggers-api"
      Environment = "dev"
      ManagedBy   = "Terraform"
      CostCenter  = "engineering"
    }
  }
}

# Use root module
module "triggers_api" {
  source = "../.."

  aws_region              = var.aws_region
  environment             = "dev"
  project_name            = "zapier-triggers-api"
  cost_center             = "engineering"
  vpc_cidr                = var.vpc_cidr
  availability_zones      = var.availability_zones
  enable_nat_gateway      = var.enable_nat_gateway
  dynamodb_billing_mode   = var.dynamodb_billing_mode
  events_ttl_days         = var.events_ttl_days
  audit_logs_ttl_days     = var.audit_logs_ttl_days
  sqs_visibility_timeout  = var.sqs_visibility_timeout
  sqs_message_retention   = var.sqs_message_retention
  enable_xray_tracing     = var.enable_xray_tracing
  lambda_runtime          = var.lambda_runtime
  api_gateway_stage_name  = var.api_gateway_stage_name
  enable_api_gateway_access_logs = var.enable_api_gateway_access_logs
}
