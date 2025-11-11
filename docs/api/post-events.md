# POST /events - Event Ingestion API

## Overview

The POST /events endpoint allows external developers to submit events to the Zapier Triggers API. Events are validated, persisted to DynamoDB, and queued for processing to trigger Zapier workflows.

**Endpoint:** `POST /v1/events`

**Authentication:** Required (X-API-Key header)

**Content-Type:** `application/json`

**Rate Limits:** 10,000 requests per second per API key

---

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Yes | Your API key for authentication |
| `Content-Type` | Yes | Must be `application/json` |
| `X-Request-ID` | No | Optional correlation ID for request tracing (auto-generated if not provided) |

### Request Body

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `event_type` | string | Yes | Event type identifier (e.g., "user.created", "order.completed") | Non-empty string, max 256 characters |
| `payload` | object | Yes | Event data as JSON object | Non-empty object, max 1MB |

### Request Example

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: zap_live_abc123def456ghi789" \
  -d '{
    "event_type": "user.created",
    "payload": {
      "user_id": "usr_12345",
      "email": "jane.doe@example.com",
      "name": "Jane Doe",
      "created_at": "2025-11-11T10:00:00Z",
      "plan": "pro"
    }
  }'
```

### Python Example

```python
import requests

api_key = "zap_live_abc123def456ghi789"
api_url = "https://api.zapier-triggers.com/v1"

event_data = {
    "event_type": "order.completed",
    "payload": {
        "order_id": "ord_98765",
        "customer_id": "cst_54321",
        "total": 99.99,
        "currency": "USD",
        "items": [
            {"sku": "PROD-001", "quantity": 2, "price": 29.99},
            {"sku": "PROD-002", "quantity": 1, "price": 40.01}
        ],
        "completed_at": "2025-11-11T10:15:30Z"
    }
}

response = requests.post(
    f"{api_url}/events",
    json=event_data,
    headers={"X-API-Key": api_key}
)

if response.status_code == 201:
    result = response.json()
    print(f"Event created successfully!")
    print(f"Event ID: {result['event_id']}")
    print(f"Status: {result['status']}")
    print(f"Timestamp: {result['timestamp']}")
else:
    error = response.json()
    print(f"Error: {error['error']['message']}")
    if 'details' in error['error']:
        for detail in error['error']['details']:
            print(f"  - {detail['field']}: {detail['message']}")
```

### JavaScript Example

```javascript
const axios = require('axios');

const apiKey = 'zap_live_abc123def456ghi789';
const apiUrl = 'https://api.zapier-triggers.com/v1';

const eventData = {
  event_type: 'payment.succeeded',
  payload: {
    payment_id: 'pay_xyz789',
    customer_id: 'cst_54321',
    amount: 49.99,
    currency: 'USD',
    payment_method: 'credit_card',
    processed_at: '2025-11-11T10:20:00Z'
  }
};

axios.post(`${apiUrl}/events`, eventData, {
  headers: {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
  }
})
.then(response => {
  console.log('Event created successfully!');
  console.log('Event ID:', response.data.event_id);
  console.log('Status:', response.data.status);
  console.log('Timestamp:', response.data.timestamp);
})
.catch(error => {
  if (error.response) {
    console.error('Error:', error.response.data.error.message);
    if (error.response.data.error.details) {
      error.response.data.error.details.forEach(detail => {
        console.error(`  - ${detail.field}: ${detail.message}`);
      });
    }
  } else {
    console.error('Network error:', error.message);
  }
});
```

---

## Response

### Success Response (201 Created)

When an event is successfully created, the API returns HTTP 201 Created with the following response body:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "received",
  "timestamp": "2025-11-11T10:00:00.123456Z",
  "message": "Event successfully created and queued for processing"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | Unique UUID v4 identifier for the event |
| `status` | string | Event status: "received" (queued for processing) |
| `timestamp` | string | ISO 8601 timestamp (UTC) when event was received |
| `message` | string | Confirmation message |

---

## Error Responses

### 400 Bad Request - Validation Error

Returned when the request body fails validation (missing required fields, invalid format, etc.).

**Example - Missing event_type:**

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: zap_live_abc123def456ghi789" \
  -d '{
    "payload": {
      "user_id": "usr_12345"
    }
  }'
```

**Response:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload",
    "details": [
      {
        "field": "event_type",
        "message": "Field required"
      }
    ],
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-123"
  }
}
```

**Example - Empty payload:**

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: zap_live_abc123def456ghi789" \
  -d '{
    "event_type": "test.event",
    "payload": {}
  }'
```

**Response:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload",
    "details": [
      {
        "field": "payload",
        "message": "payload cannot be empty"
      }
    ],
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-456"
  }
}
```

**Example - Payload exceeds 1MB:**

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: zap_live_abc123def456ghi789" \
  -d '{
    "event_type": "large.event",
    "payload": {
      "large_data": "... (more than 1MB of data) ..."
    }
  }'
```

**Response:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload",
    "details": [
      {
        "field": "payload",
        "message": "payload exceeds maximum size of 1MB (current size: 1049000 bytes)"
      }
    ],
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-789"
  }
}
```

---

### 401 Unauthorized - Invalid API Key

Returned when the X-API-Key header is missing or invalid.

**Example:**

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: invalid-key" \
  -d '{
    "event_type": "user.created",
    "payload": {"user_id": "123"}
  }'
```

**Response:**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API key",
    "details": null,
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-unauthorized"
  }
}
```

---

### 415 Unsupported Media Type - Invalid Content-Type

Returned when the Content-Type header is not `application/json`.

**Example:**

```bash
curl -X POST https://api.zapier-triggers.com/v1/events \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-API-Key: zap_live_abc123def456ghi789" \
  -d 'event_type=user.created&payload=data'
```

**Response:**

```json
{
  "error": {
    "code": "UNSUPPORTED_MEDIA_TYPE",
    "message": "Content-Type must be application/json",
    "details": null,
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-unsupported"
  }
}
```

---

### 500 Internal Server Error

Returned when an unexpected error occurs on the server.

**Response:**

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "details": null,
    "timestamp": "2025-11-11T10:00:00.123456Z",
    "request_id": "correlation-id-internal-error"
  }
}
```

Use the `request_id` when contacting support for troubleshooting.

---

## Event Types

You can use any custom event type string, but here are some recommended patterns:

| Pattern | Example | Use Case |
|---------|---------|----------|
| `resource.action` | `user.created`, `order.completed` | Standard CRUD operations |
| `resource.status_change` | `payment.succeeded`, `shipment.delivered` | Status transitions |
| `system.event` | `system.webhook_failed`, `system.rate_limit_exceeded` | System-level events |

---

## Payload Guidelines

### Best Practices

1. **Include IDs:** Always include unique identifiers (e.g., `user_id`, `order_id`)
2. **Timestamps:** Use ISO 8601 format for all timestamps (e.g., `2025-11-11T10:00:00Z`)
3. **Keep it relevant:** Only include data needed for Zapier workflows
4. **Avoid PII:** Don't include sensitive personal information unless required
5. **Use nested objects:** Organize related data into nested objects for clarity

### Size Limits

- **Maximum payload size:** 1MB (1,048,576 bytes)
- **Maximum event_type length:** 256 characters
- **Maximum nesting depth:** Unlimited, but keep it reasonable for performance

### Example Payloads

**User Created Event:**

```json
{
  "event_type": "user.created",
  "payload": {
    "user_id": "usr_12345",
    "email": "jane.doe@example.com",
    "name": "Jane Doe",
    "plan": "pro",
    "created_at": "2025-11-11T10:00:00Z"
  }
}
```

**Order Completed Event:**

```json
{
  "event_type": "order.completed",
  "payload": {
    "order_id": "ord_98765",
    "customer_id": "cst_54321",
    "total": 99.99,
    "currency": "USD",
    "items": [
      {"sku": "PROD-001", "quantity": 2, "price": 29.99},
      {"sku": "PROD-002", "quantity": 1, "price": 40.01}
    ],
    "completed_at": "2025-11-11T10:15:30Z"
  }
}
```

**Payment Succeeded Event:**

```json
{
  "event_type": "payment.succeeded",
  "payload": {
    "payment_id": "pay_xyz789",
    "customer_id": "cst_54321",
    "amount": 49.99,
    "currency": "USD",
    "payment_method": "credit_card",
    "processed_at": "2025-11-11T10:20:00Z"
  }
}
```

---

## Event Lifecycle

1. **Ingestion:** Event received at POST /events endpoint
2. **Validation:** Request validated (required fields, payload size, format)
3. **Persistence:** Event stored in DynamoDB with 30-day TTL
4. **Queuing:** Event queued to SQS for asynchronous processing
5. **Response:** 201 Created returned with event_id
6. **Processing:** Background worker processes event and triggers Zapier workflows
7. **Status Updates:** Event status tracked (received → processing → completed/failed)
8. **Retrieval:** Event can be retrieved via GET /events/{event_id} or GET /inbox

---

## Idempotency

The API generates a unique `event_id` for each request. If you submit the same event multiple times, each submission will receive a unique `event_id` and will be treated as a separate event.

To implement idempotency on the client side:
1. Generate a unique `X-Request-ID` header for each logical event
2. Store the returned `event_id` associated with that `X-Request-ID`
3. On retry, check if you already have an `event_id` for that `X-Request-ID`

Future versions may support explicit idempotency keys via `X-Idempotency-Key` header.

---

## Rate Limits

- **Per API Key:** 10,000 requests per second
- **Burst:** Up to 20,000 requests per second for short bursts
- **Rate Limit Headers:** (Future - not yet implemented)
  - `X-RateLimit-Limit`: Maximum requests per second
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Unix timestamp when rate limit resets

When rate limit is exceeded, the API returns HTTP 429 Too Many Requests.

---

## Monitoring and Observability

### Correlation IDs

Every request includes a correlation ID for tracking:
- Provided via `X-Request-ID` header (if not provided, auto-generated)
- Returned in all responses (success and error) as `request_id`
- Use this ID when contacting support or debugging issues

### Metrics

All events are tracked in CloudWatch with the following metrics:
- `EventsCreated`: Count of successfully created events
- `ValidationErrors`: Count of validation failures
- `InternalErrors`: Count of internal server errors
- `EventCreationDuration`: Duration (ms) to create event

### Logging

All API requests are logged with structured JSON logs including:
- Request ID (correlation ID)
- User ID (from API key)
- Event type
- HTTP status code
- Response time (ms)

---

## Auto-Generated API Documentation

Interactive API documentation is available at:
- **Swagger UI:** `https://api.zapier-triggers.com/docs`
- **ReDoc:** `https://api.zapier-triggers.com/redoc`
- **OpenAPI Spec:** `https://api.zapier-triggers.com/openapi.json`

---

## Support

For questions or issues:
- **Documentation:** https://docs.zapier-triggers.com
- **Support:** support@zapier-triggers.com
- **Status:** https://status.zapier-triggers.com

When contacting support, please include the `request_id` from the error response.
