# DynamoDB Event Storage - Monitoring & Operations Runbook

**Version:** 1.0
**Last Updated:** 2025-11-11
**Story:** 1.4 - Event Storage with DynamoDB

---

## Overview

This runbook provides operational guidance for monitoring and troubleshooting the DynamoDB Events table in the Zapier Triggers API. The Events table is the primary data store for all incoming events, supporting:

- Event persistence with 30-day TTL
- Real-time event delivery via DynamoDB Streams
- Point-in-time recovery (PITR) for disaster recovery
- On-demand billing with automatic scaling

---

## Table of Contents

1. [Architecture Summary](#architecture-summary)
2. [CloudWatch Dashboard](#cloudwatch-dashboard)
3. [Alarms and Alerts](#alarms-and-alerts)
4. [Common Issues and Resolution](#common-issues-and-resolution)
5. [Performance Targets](#performance-targets)
6. [Disaster Recovery](#disaster-recovery)
7. [CloudWatch Insights Queries](#cloudwatch-insights-queries)
8. [Maintenance Procedures](#maintenance-procedures)

---

## Architecture Summary

### DynamoDB Events Table

**Table Name:** `zapier-triggers-api-{env}-events`

**Schema:**
- **Partition Key:** `user_id` (String)
- **Sort Key:** `timestamp#event_id` (String)
- **Attributes:** event_id, event_type, payload, status, timestamp, ttl, retry_count, metadata

**Global Secondary Indexes (GSI):**
1. **EventTypeIndex:** `user_id` (PK) + `event_type#timestamp` (SK)
   - Used for querying events by type
2. **StatusIndex:** `user_id` (PK) + `status#timestamp` (SK)
   - Used for querying events by status

**Configuration:**
- **Billing Mode:** PAY_PER_REQUEST (On-Demand)
- **TTL:** Enabled on `ttl` attribute (30-day expiration)
- **Point-in-Time Recovery:** Enabled (35-day retention)
- **DynamoDB Streams:** Enabled with NEW_IMAGE view type
- **Encryption:** AWS-managed keys (default)

---

## CloudWatch Dashboard

### Dashboard Name
`zapier-triggers-api-{env}-dashboard`

### Key Widgets

#### 1. DynamoDB - Events Table Capacity
**Metrics:**
- ConsumedReadCapacityUnits (Sum)
- ConsumedWriteCapacityUnits (Sum)

**Purpose:** Monitor read/write capacity consumption to identify usage patterns.

**Normal Range:**
- Write: 10-1000 WCU/min (depends on event volume)
- Read: 5-500 RCU/min (depends on query volume)

#### 2. DynamoDB - Throttling
**Metrics:**
- UserErrors (Sum)

**Purpose:** Detect throttling events indicating capacity limits.

**Normal Range:** 0 errors/5min

**Alert Threshold:** > 10 errors/5min triggers alarm

#### 3. DynamoDB - Write Latency (PutItem)
**Metrics:**
- SuccessfulRequestLatency (Average, p95, p99)

**Purpose:** Monitor event write performance.

**Target Latency:**
- Average: < 8ms
- p95: < 10ms
- p99: < 20ms

**Alert Threshold:** p99 > 20ms triggers alarm

#### 4. DynamoDB - Read Latency (Query/GetItem)
**Metrics:**
- SuccessfulRequestLatency (Average, p95)

**Purpose:** Monitor event read/query performance.

**Target Latency:**
- Average: < 10ms
- p95: < 50ms

**Alert Threshold:** p95 > 50ms triggers alarm

---

## Alarms and Alerts

### Critical Alarms

#### 1. DynamoDB Throttling
**Alarm Name:** `zapier-triggers-api-{env}-events-table-throttles`

**Trigger:** UserErrors > 10 for 2 consecutive 5-min periods

**Severity:** HIGH

**Impact:** Events may fail to persist; API requests return 503 errors

**Resolution:**
1. Check CloudWatch dashboard for capacity consumption
2. If PAY_PER_REQUEST: Verify burst capacity not exceeded (40K RCU/WCU)
3. Implement exponential backoff in API layer
4. Check for hot partitions (uneven user_id distribution)
5. Consider adding write buffering via SQS

**Prevention:**
- Monitor capacity trends
- Implement circuit breakers in API layer
- Add request throttling at API Gateway level

---

#### 2. DynamoDB Write Latency High
**Alarm Name:** `zapier-triggers-api-{env}-dynamodb-write-latency`

**Trigger:** SuccessfulRequestLatency (p99) > 20ms for 3 consecutive 5-min periods

**Severity:** MEDIUM

**Impact:** Slower event ingestion; potential API timeout cascades

**Resolution:**
1. Check CloudWatch for latency trends
2. Verify DynamoDB service health status
3. Check for large payloads (>100KB) causing slow writes
4. Review table capacity consumption
5. Investigate network issues between Lambda and DynamoDB

**Prevention:**
- Enforce payload size limits (1MB max)
- Monitor payload size distribution
- Use VPC endpoints for DynamoDB access

---

#### 3. DynamoDB Read Latency High
**Alarm Name:** `zapier-triggers-api-{env}-dynamodb-read-latency`

**Trigger:** SuccessfulRequestLatency (p95) > 50ms for 3 consecutive 5-min periods

**Severity:** MEDIUM

**Impact:** Slower GET /inbox queries; poor user experience

**Resolution:**
1. Check CloudWatch for GSI query patterns
2. Verify GSI projections include required attributes
3. Check for table scans (should use GSIs exclusively)
4. Review query filter complexity
5. Consider implementing caching layer (Redis/ElastiCache)

**Prevention:**
- Always use GSI for queries
- Limit result set sizes (pagination)
- Implement read-through caching

---

## Common Issues and Resolution

### Issue 1: Events Not Persisting

**Symptoms:**
- POST /events returns 500 errors
- CloudWatch Logs show DynamoDB ClientError
- UserErrors metric shows throttling

**Diagnosis:**
```bash
# Check for throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=zapier-triggers-api-dev-events \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Check table status
aws dynamodb describe-table --table-name zapier-triggers-api-dev-events
```

**Resolution:**
1. Verify table is ACTIVE
2. Check for throttling in CloudWatch
3. Review Lambda logs for specific error messages
4. Implement exponential backoff in EventRepository
5. Consider increasing Lambda concurrency limits

---

### Issue 2: TTL Not Deleting Expired Events

**Symptoms:**
- Events older than 30 days still present in table
- Table size growing unexpectedly
- Storage costs increasing

**Diagnosis:**
```bash
# Check TTL configuration
aws dynamodb describe-time-to-live \
  --table-name zapier-triggers-api-dev-events

# Query for expired events
aws dynamodb query \
  --table-name zapier-triggers-api-dev-events \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid": {"S": "sample-user"}}' \
  --projection-expression "event_id, ttl, #ts" \
  --expression-attribute-names '{"#ts": "timestamp"}'
```

**Resolution:**
1. Verify TTL status is "ENABLED"
2. Check `ttl` attribute is set on events (Unix timestamp)
3. Wait 24-48 hours for TTL background process
4. If persistent, contact AWS Support
5. Manually clean up old events if urgent

**Note:** TTL deletion is asynchronous and may take up to 48 hours.

---

### Issue 3: DynamoDB Streams Not Delivering Events

**Symptoms:**
- Events persist successfully
- Downstream processors not receiving events
- Stream shard iterators timing out

**Diagnosis:**
```bash
# Check stream status
aws dynamodb describe-table \
  --table-name zapier-triggers-api-dev-events \
  --query 'Table.StreamSpecification'

# List stream shards
aws dynamodbstreams describe-stream \
  --stream-arn $(aws dynamodb describe-table \
    --table-name zapier-triggers-api-dev-events \
    --query 'Table.LatestStreamArn' --output text)
```

**Resolution:**
1. Verify StreamEnabled is true
2. Check stream view type is NEW_IMAGE
3. Verify Lambda consumer has correct IAM permissions
4. Check Lambda event source mapping is ENABLED
5. Review Lambda consumer logs for processing errors

---

### Issue 4: Hot Partition (Throttling on Specific user_id)

**Symptoms:**
- Throttling errors for specific users
- Uneven capacity consumption
- High latency for specific user queries

**Diagnosis:**
```bash
# CloudWatch Insights query for top users by event count
fields user_id, count(*) as event_count
| filter @message like /Event created/
| stats count() by user_id
| sort event_count desc
| limit 10
```

**Resolution:**
1. Identify hot partition users (>1000 events/sec)
2. Implement write sharding: Add random suffix to user_id
3. Distribute writes across multiple partitions
4. Consider composite partition key redesign
5. Implement rate limiting per user

**Prevention:**
- Monitor user-level event rates
- Implement per-user rate limits at API Gateway
- Design partition keys for even distribution

---

## Performance Targets

### Write Operations (PutItem)
- **p50:** < 5ms
- **p95:** < 10ms
- **p99:** < 20ms
- **Throughput:** Support 1,000 events/sec sustained

### Read Operations (Query/GetItem)
- **p50:** < 10ms
- **p95:** < 50ms
- **p99:** < 100ms
- **Throughput:** Support 100 queries/sec

### Availability
- **Target:** 99.9% uptime
- **SLA:** DynamoDB SLA is 99.99% (AWS-managed)

### Data Durability
- **Target:** 99.999999999% (11 nines) - AWS-managed

---

## Disaster Recovery

### Point-in-Time Recovery (PITR)

**Retention:** 35 days (AWS maximum)

**Restore Procedure:**

1. **Identify Restore Point:**
   ```bash
   # List continuous backups
   aws dynamodb describe-continuous-backups \
     --table-name zapier-triggers-api-dev-events
   ```

2. **Initiate Restore:**
   ```bash
   # Restore to specific timestamp
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name zapier-triggers-api-dev-events \
     --target-table-name zapier-triggers-api-dev-events-restored-$(date +%Y%m%d) \
     --restore-date-time "2025-11-10T12:00:00Z"
   ```

3. **Verify Restored Table:**
   ```bash
   # Check table status
   aws dynamodb describe-table \
     --table-name zapier-triggers-api-dev-events-restored-$(date +%Y%m%d)

   # Sample data to verify
   aws dynamodb scan \
     --table-name zapier-triggers-api-dev-events-restored-$(date +%Y%m%d) \
     --limit 10
   ```

4. **Cutover to Restored Table:**
   - Update Lambda environment variables (EVENTS_TABLE_NAME)
   - Redeploy Lambda functions
   - Update Terraform state (if needed)
   - Verify API functionality

5. **Cleanup:**
   - Delete original corrupted table (only after verification)
   - Update monitoring dashboards
   - Document incident in postmortem

**Recovery Time Objective (RTO):** < 4 hours
**Recovery Point Objective (RPO):** < 5 minutes (PITR granularity)

---

## CloudWatch Insights Queries

### Query 1: Event Write Latency by User

```sql
fields @timestamp, user_id, event_id, @duration
| filter @message like /Event created/
| stats avg(@duration) as avg_latency_ms,
        pct(@duration, 95) as p95_latency_ms,
        count(*) as event_count
  by user_id
| sort p95_latency_ms desc
| limit 20
```

**Purpose:** Identify users with high write latency.

---

### Query 2: DynamoDB Errors by Type

```sql
fields @timestamp, @message, error_code, error_message
| filter error_code like /DynamoDB/
| stats count() by error_code
| sort count desc
```

**Purpose:** Identify most common DynamoDB errors.

---

### Query 3: TTL Deletion Tracking

```sql
fields @timestamp, event_id, user_id, ttl
| filter @message like /TTL/
| stats count() by bin(1h)
```

**Purpose:** Monitor TTL deletion activity over time.

---

### Query 4: Query Performance (GET /inbox)

```sql
fields @timestamp, user_id, @duration, item_count
| filter @message like /Query events/
| stats avg(@duration) as avg_latency_ms,
        pct(@duration, 95) as p95_latency_ms,
        avg(item_count) as avg_items
  by bin(5m)
```

**Purpose:** Monitor GET /inbox query performance.

---

## Maintenance Procedures

### Monthly Health Check

**Schedule:** First Monday of each month

1. **Review Capacity Trends:**
   - Check CloudWatch dashboard for capacity consumption trends
   - Verify no sustained throttling events
   - Review cost trends (PAY_PER_REQUEST charges)

2. **Verify TTL Deletion:**
   - Sample events older than 30 days (should be 0)
   - Check TTL status remains ENABLED

3. **Test PITR Restore:**
   - Restore table to test environment
   - Verify data integrity
   - Document restore time

4. **Review Alarms:**
   - Verify all alarms are functional
   - Update thresholds based on usage patterns
   - Add new alarms for emerging issues

5. **Audit IAM Permissions:**
   - Review Lambda execution role permissions
   - Verify least-privilege access
   - Check for unused permissions

---

### Quarterly Performance Review

**Schedule:** End of each quarter

1. **Analyze Performance Metrics:**
   - Calculate p50/p95/p99 latencies for quarter
   - Compare to performance targets
   - Identify degradation trends

2. **Capacity Planning:**
   - Project capacity needs for next quarter
   - Evaluate cost optimization opportunities
   - Consider provisioned billing if predictable load

3. **Schema Review:**
   - Evaluate GSI usage patterns
   - Consider adding/removing indexes
   - Review partition key distribution

4. **Disaster Recovery Drill:**
   - Simulate data corruption scenario
   - Perform full PITR restore
   - Document lessons learned

---

## Contacts and Escalation

**On-Call Engineer:** [Your team's on-call rotation]
**AWS Support:** Use AWS Support Console for DynamoDB issues
**Escalation Path:**
1. On-call engineer (response: 15 min)
2. Team lead (response: 30 min)
3. AWS Support (response: varies by severity)

---

## References

- [AWS DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [DynamoDB Troubleshooting](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html)
- Architecture Document: `/docs/architecture.md`
- Story 1.4: `/stories/1.4-event-storage.md`

---

**Document History:**

| Version | Date       | Author | Changes                          |
|---------|------------|--------|----------------------------------|
| 1.0     | 2025-11-11 | James  | Initial runbook for Story 1.4    |
