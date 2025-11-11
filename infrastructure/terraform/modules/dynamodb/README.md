# DynamoDB Module

This module creates DynamoDB tables for event storage, API key management, and audit logging.

## Tables

### Events Table

**Purpose**: Store incoming events with lifecycle tracking

**Schema**:
- **Partition Key**: `user_id` (String)
- **Sort Key**: `timestamp#event_id` (String) - composite key for chronological ordering
- **GSI 1**: EventTypeIndex - Query events by type
  - PK: `user_id`, SK: `event_type#timestamp`
- **GSI 2**: StatusIndex - Query events by status
  - PK: `user_id`, SK: `status#timestamp`
- **TTL**: 30 days (configurable)
- **Streams**: Enabled for Zapier workflow integration
- **PITR**: Enabled for disaster recovery

### API Keys Table

**Purpose**: Store API keys for authentication

**Schema**:
- **Partition Key**: `user_id` (String)
- **Sort Key**: `key_id` (String)
- **GSI 1**: KeyHashIndex - Lookup keys by hash during authentication
  - PK: `key_hash`
- **PITR**: Enabled

### Audit Logs Table

**Purpose**: Immutable audit trail for compliance

**Schema**:
- **Partition Key**: `user_id` (String)
- **Sort Key**: `timestamp#log_id` (String)
- **TTL**: 7 years (2557 days) for compliance
- **PITR**: Enabled

## Usage

```hcl
module "dynamodb" {
  source = "./modules/dynamodb"

  project_name        = "zapier-triggers-api"
  environment         = "dev"
  billing_mode        = "PAY_PER_REQUEST"
  events_ttl_days     = 30
  audit_logs_ttl_days = 2557
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project_name | Project name | string | - |
| environment | Environment name | string | - |
| billing_mode | Billing mode | string | PAY_PER_REQUEST |
| events_ttl_days | Events TTL in days | number | 30 |
| audit_logs_ttl_days | Audit logs TTL in days | number | 2557 |

## Outputs

| Name | Description |
|------|-------------|
| events_table_name | Events table name |
| events_table_arn | Events table ARN |
| events_table_stream_arn | Events table stream ARN |
| api_keys_table_name | API Keys table name |
| api_keys_table_arn | API Keys table ARN |
| audit_logs_table_name | Audit Logs table name |
| audit_logs_table_arn | Audit Logs table ARN |
