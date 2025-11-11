# DynamoDB Schema Reference

**Version:** 1.0
**Last Updated:** 2025-11-11
**Story:** 1.4 - Event Storage with DynamoDB

---

## Overview

This document provides a comprehensive reference for the DynamoDB tables used in the Zapier Triggers API. It includes schema definitions, access patterns, and usage examples.

---

## Events Table

### Table Configuration

**Table Name:** `zapier-triggers-api-{env}-events`

**Billing Mode:** PAY_PER_REQUEST (On-Demand)

**Encryption:** AWS-managed keys (AES-256)

**Streams:** Enabled (NEW_IMAGE view type)

**TTL:** Enabled on `ttl` attribute

**Point-in-Time Recovery:** Enabled (35-day retention)

---

### Primary Key Schema

| Attribute                | Type   | Key Type | Description                              |
|--------------------------|--------|----------|------------------------------------------|
| `user_id`                | String | HASH     | Partition key - User/tenant identifier   |
| `timestamp#event_id`     | String | RANGE    | Sort key - Composite timestamp + event ID |

**Composite Sort Key Format:** `{ISO8601_timestamp}#{UUID_v4}`

**Example:** `2025-11-11T10:30:45.123456Z#550e8400-e29b-41d4-a716-446655440000`

**Rationale:**
- Partition by `user_id` for data isolation and query efficiency
- Sort by timestamp for chronological event ordering
- Include event_id in sort key for uniqueness and direct access

---

### Attributes

| Attribute             | Type   | Required | Description                                      |
|-----------------------|--------|----------|--------------------------------------------------|
| `user_id`             | String | Yes      | User identifier (partition key)                  |
| `timestamp#event_id`  | String | Yes      | Composite sort key                               |
| `event_id`            | String | Yes      | Unique event identifier (UUID v4)                |
| `event_type`          | String | Yes      | Event type identifier (e.g., "user.created")     |
| `payload`             | Map    | Yes      | Event payload data (JSON object)                 |
| `status`              | String | Yes      | Event status (received, delivered, failed)       |
| `timestamp`           | String | Yes      | ISO 8601 timestamp with microseconds             |
| `ttl`                 | Number | Yes      | Unix timestamp for TTL expiration (30 days)      |
| `retry_count`         | Number | Yes      | Number of delivery retry attempts                |
| `metadata`            | Map    | No       | Metadata (source_ip, api_version, correlation_id)|
| `event_type#timestamp`| String | Yes      | GSI-1 composite key (for EventTypeIndex)         |
| `status#timestamp`    | String | Yes      | GSI-2 composite key (for StatusIndex)            |

---

### Global Secondary Indexes (GSI)

#### GSI-1: EventTypeIndex

**Purpose:** Query events by event type for a specific user.

**Key Schema:**

| Attribute             | Type   | Key Type |
|-----------------------|--------|----------|
| `user_id`             | String | HASH     |
| `event_type#timestamp`| String | RANGE    |

**Projection:** ALL

**Use Cases:**
- Retrieve all "user.created" events for a user
- Filter GET /inbox by event_type parameter
- Generate event type analytics

**Example Query:**
```python
response = table.query(
    IndexName='EventTypeIndex',
    KeyConditionExpression='user_id = :uid AND begins_with(#et, :event_type)',
    ExpressionAttributeNames={'#et': 'event_type#timestamp'},
    ExpressionAttributeValues={
        ':uid': 'user-123',
        ':event_type': 'user.created'
    }
)
```

---

#### GSI-2: StatusIndex

**Purpose:** Query events by status for a specific user.

**Key Schema:**

| Attribute             | Type   | Key Type |
|-----------------------|--------|----------|
| `user_id`             | String | HASH     |
| `status#timestamp`    | String | RANGE    |

**Projection:** ALL

**Use Cases:**
- Retrieve all pending events for retry
- Monitor failed events for alerting
- Generate delivery status reports

**Example Query:**
```python
response = table.query(
    IndexName='StatusIndex',
    KeyConditionExpression='user_id = :uid AND begins_with(#st, :status)',
    ExpressionAttributeNames={'#st': 'status#timestamp'},
    ExpressionAttributeValues={
        ':uid': 'user-123',
        ':status': 'failed'
    }
)
```

---

## Access Patterns

### Pattern 1: Create Event

**Operation:** PutItem

**Purpose:** Persist new event with TTL

**Partition Key:** `user_id`

**Sort Key:** `timestamp#event_id`

**Example:**
```python
from datetime import datetime, timedelta
import time
import uuid

event_id = str(uuid.uuid4())
timestamp = datetime.utcnow().isoformat() + "Z"
ttl = int(time.time()) + (30 * 24 * 60 * 60)  # 30 days

table.put_item(
    Item={
        'user_id': 'user-123',
        'timestamp#event_id': f'{timestamp}#{event_id}',
        'event_id': event_id,
        'event_type': 'user.created',
        'payload': {'email': 'user@example.com'},
        'status': 'received',
        'timestamp': timestamp,
        'ttl': ttl,
        'retry_count': 0,
        'metadata': {'source_ip': '192.168.1.1'},
        'event_type#timestamp': f'user.created#{timestamp}',
        'status#timestamp': f'received#{timestamp}'
    }
)
```

**Performance Target:** < 10ms p95

---

### Pattern 2: Get Event by ID

**Operation:** GetItem

**Purpose:** Retrieve specific event by composite key

**Example:**
```python
response = table.get_item(
    Key={
        'user_id': 'user-123',
        'timestamp#event_id': '2025-11-11T10:00:00.123456Z#550e8400-e29b-41d4-a716-446655440000'
    }
)
event = response.get('Item')
```

**Performance Target:** < 5ms p95

---

### Pattern 3: Query Events by User (GET /inbox)

**Operation:** Query

**Purpose:** Retrieve all events for a user, ordered by timestamp

**Example:**
```python
response = table.query(
    KeyConditionExpression='user_id = :uid',
    ExpressionAttributeValues={':uid': 'user-123'},
    Limit=100,
    ScanIndexForward=False  # Descending order (newest first)
)
events = response['Items']
```

**Performance Target:** < 50ms p95

---

### Pattern 4: Query Events by Event Type

**Operation:** Query (EventTypeIndex GSI)

**Purpose:** Filter events by type for a user

**Example:**
```python
response = table.query(
    IndexName='EventTypeIndex',
    KeyConditionExpression='user_id = :uid AND begins_with(#et, :event_type)',
    ExpressionAttributeNames={'#et': 'event_type#timestamp'},
    ExpressionAttributeValues={
        ':uid': 'user-123',
        ':event_type': 'order.completed'
    },
    Limit=50
)
```

**Performance Target:** < 50ms p95

---

### Pattern 5: Query Events by Status

**Operation:** Query (StatusIndex GSI)

**Purpose:** Retrieve pending/failed events for retry

**Example:**
```python
response = table.query(
    IndexName='StatusIndex',
    KeyConditionExpression='user_id = :uid AND begins_with(#st, :status)',
    ExpressionAttributeNames={'#st': 'status#timestamp'},
    ExpressionAttributeValues={
        ':uid': 'user-123',
        ':status': 'failed'
    }
)
failed_events = response['Items']
```

**Performance Target:** < 50ms p95

---

### Pattern 6: Update Event Status

**Operation:** UpdateItem

**Purpose:** Update event status and retry count after delivery attempt

**Example:**
```python
table.update_item(
    Key={
        'user_id': 'user-123',
        'timestamp#event_id': '2025-11-11T10:00:00.123456Z#evt-123'
    },
    UpdateExpression='SET #status = :status, retry_count = :retry_count, #st = :st_val',
    ExpressionAttributeNames={
        '#status': 'status',
        '#st': 'status#timestamp'
    },
    ExpressionAttributeValues={
        ':status': 'delivered',
        ':retry_count': 3,
        ':st_val': f'delivered#{timestamp}'
    },
    ReturnValues='ALL_NEW'
)
```

**Performance Target:** < 10ms p95

---

## Data Model Examples

### Example Event Item

```json
{
  "user_id": "user-12345",
  "timestamp#event_id": "2025-11-11T10:30:45.123456Z#550e8400-e29b-41d4-a716-446655440000",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "user.created",
  "payload": {
    "user_id": "12345",
    "email": "newuser@example.com",
    "name": "John Doe",
    "created_at": "2025-11-11T10:30:45Z"
  },
  "status": "received",
  "timestamp": "2025-11-11T10:30:45.123456Z",
  "ttl": 1735831845,
  "retry_count": 0,
  "metadata": {
    "source_ip": "192.168.1.1",
    "api_version": "v1",
    "correlation_id": "req-abc123"
  },
  "event_type#timestamp": "user.created#2025-11-11T10:30:45.123456Z",
  "status#timestamp": "received#2025-11-11T10:30:45.123456Z"
}
```

---

## Status Transitions

Events can transition through the following statuses:

```
received → delivered (success)
received → failed → retrying → delivered (retry success)
received → failed → retrying → failed (retry exhausted)
```

**Status Enum:**
- `received`: Event ingested and persisted
- `delivered`: Event successfully delivered to workflow
- `failed`: Delivery failed (temporary or permanent)
- `retrying`: Delivery retry in progress

---

## TTL (Time-To-Live) Behavior

### Configuration

**Attribute:** `ttl`

**Type:** Number (Unix timestamp in seconds)

**Expiration:** 30 days from event creation

**Calculation:**
```python
import time
from datetime import datetime, timedelta

ttl = int(time.time()) + (30 * 24 * 60 * 60)
# Or using datetime
ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
```

### Deletion Process

1. DynamoDB background process scans for expired items (ttl < current_time)
2. Items are deleted asynchronously (typically within 48 hours)
3. Deletion is free (no WCU consumed)
4. No guarantees on exact deletion time

### Monitoring TTL Deletion

**CloudWatch Metric:** (Custom metric via DynamoDB Streams)

**Query Expired Events:**
```bash
aws dynamodb query \
  --table-name zapier-triggers-api-dev-events \
  --key-condition-expression "user_id = :uid" \
  --filter-expression "#ttl < :now" \
  --expression-attribute-names '{"#ttl": "ttl"}' \
  --expression-attribute-values '{":uid": {"S": "user-123"}, ":now": {"N": "'$(date +%s)'"}}' \
  --projection-expression "event_id, ttl"
```

---

## DynamoDB Streams

### Stream Configuration

**Stream View Type:** NEW_IMAGE

**Purpose:** Capture event changes for downstream processing

**Stream ARN:** `arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/zapier-triggers-api-{env}-events/stream/TIMESTAMP`

### Stream Record Format

```json
{
  "eventID": "1",
  "eventName": "INSERT",
  "eventVersion": "1.1",
  "eventSource": "aws:dynamodb",
  "awsRegion": "us-east-1",
  "dynamodb": {
    "Keys": {
      "user_id": {"S": "user-123"},
      "timestamp#event_id": {"S": "2025-11-11T10:00:00Z#evt-123"}
    },
    "NewImage": {
      "user_id": {"S": "user-123"},
      "event_id": {"S": "evt-123"},
      "event_type": {"S": "user.created"},
      "payload": {"M": {...}},
      "status": {"S": "received"},
      "ttl": {"N": "1735831845"}
    },
    "SequenceNumber": "111",
    "SizeBytes": 512,
    "StreamViewType": "NEW_IMAGE"
  }
}
```

### Consumer Lambda Integration

Lambda can consume DynamoDB Streams via EventSourceMapping:

```python
# Lambda function handler
def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            new_image = record['dynamodb']['NewImage']
            # Process new event for delivery
            process_event(new_image)
    return {'statusCode': 200}
```

---

## Capacity Planning

### On-Demand Billing (Current Configuration)

**Reads:**
- $0.25 per million read request units
- Each GetItem = 1 RRU (up to 4KB)
- Each Query = 1 RRU per 4KB scanned

**Writes:**
- $1.25 per million write request units
- Each PutItem = 1 WRU (up to 1KB)

**Burst Capacity:**
- Up to 40,000 RCU/WCU instantly
- Suitable for unpredictable/spiky workloads

### Provisioned Billing (Future Consideration)

If traffic becomes predictable (e.g., 500 events/sec sustained):

**Estimated Provisioned Capacity:**
- Write: 500 WCU (500 events/sec × 1KB avg)
- Read: 100 RCU (100 queries/sec × 4KB avg)

**Cost Comparison:**
- On-Demand: ~$0.65/million writes
- Provisioned: ~$0.00065/WCU/hour × 500 WCU = $0.325/hour = $234/month

**Recommendation:** Stay on On-Demand until sustained > 1000 events/sec.

---

## Anti-Patterns to Avoid

### 1. Table Scans
**Bad:**
```python
response = table.scan(FilterExpression=Attr('event_type').eq('user.created'))
```

**Good:**
```python
response = table.query(
    IndexName='EventTypeIndex',
    KeyConditionExpression='user_id = :uid AND begins_with(#et, :event_type)',
    ...
)
```

### 2. Hot Partitions
**Bad:** Single user generating >1000 events/sec

**Good:** Implement rate limiting per user at API layer

### 3. Large Payloads
**Bad:** Storing 10MB payload in event

**Good:** Store payload in S3, reference S3 key in event

### 4. Unbounded Queries
**Bad:** Query without Limit parameter

**Good:** Always specify Limit and implement pagination

---

## References

- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- Story 1.4: `/stories/1.4-event-storage.md`
- Architecture Document: `/docs/architecture.md`

---

**Document History:**

| Version | Date       | Author | Changes                          |
|---------|------------|--------|----------------------------------|
| 1.0     | 2025-11-11 | James  | Initial schema documentation     |
