# AWS WAF Configuration for Zapier Triggers API
# Provides DDoS protection, rate limiting, SQL injection prevention, XSS protection

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "api_name" {
  description = "API name"
  type        = string
  default     = "zapier-triggers-api"
}

# WAF Web ACL
resource "aws_wafv2_web_acl" "triggers_api" {
  name  = "${var.api_name}-${var.environment}-waf"
  scope = "CLOUDFRONT"  # Use REGIONAL for API Gateway only
  
  default_action {
    allow {}
  }
  
  # Rule 1: Rate Limiting (2000 req per 5 min per IP)
  rule {
    name     = "rate-limiting"
    priority = 1
    
    action {
      block {
        custom_response {
          response_code = 429
          custom_response_body_key = "rate_limit_exceeded"
        }
      }
    }
    
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.api_name}-rate-limiting"
      sampled_requests_enabled   = true
    }
  }
  
  # Rule 2: SQL Injection Prevention
  rule {
    name     = "sql-injection-prevention"
    priority = 2
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.api_name}-sql-injection"
      sampled_requests_enabled   = true
    }
  }
  
  # Rule 3: XSS Prevention
  rule {
    name     = "xss-prevention"
    priority = 3
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.api_name}-xss-prevention"
      sampled_requests_enabled   = true
    }
  }
  
  # Rule 4: IP Reputation List
  rule {
    name     = "ip-reputation-list"
    priority = 4
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.api_name}-ip-reputation"
      sampled_requests_enabled   = true
    }
  }
  
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.api_name}-waf"
    sampled_requests_enabled   = true
  }
  
  tags = {
    Name        = "${var.api_name}-waf"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Custom response body for rate limiting
resource "aws_wafv2_web_acl_association" "custom_response_body" {
  web_acl_arn = aws_wafv2_web_acl.triggers_api.arn
  resource_arn = var.cloudfront_distribution_arn
}

# CloudWatch Alarms for WAF
resource "aws_cloudwatch_metric_alarm" "waf_blocked_requests" {
  alarm_name          = "${var.api_name}-${var.environment}-waf-high-block-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "WAF blocking >100 requests in 5 minutes"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    WebACL = aws_wafv2_web_acl.triggers_api.name
    Region = "us-east-1"
    Rule   = "ALL"
  }
  
  tags = {
    Name        = "${var.api_name}-waf-block-alarm"
    Environment = var.environment
  }
}

# Outputs
output "waf_web_acl_id" {
  value = aws_wafv2_web_acl.triggers_api.id
}

output "waf_web_acl_arn" {
  value = aws_wafv2_web_acl.triggers_api.arn
}
