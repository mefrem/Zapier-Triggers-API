# Getting Started with Zapier Triggers API

Welcome to the Zapier Triggers API! This guide will help you integrate in 5 minutes.

## Prerequisites

- A Zapier account
- API key (generate from your dashboard)
- curl, Python 3.7+, or Node.js 12+

## Quick Start (5 Minutes)

### Step 1: Get Your API Key (1 minute)

1. Log in to your Zapier account
2. Navigate to Settings → API Keys
3. Click "Generate New API Key"
4. Copy your key (format: `sk_live_...` or `sk_test_...`)
5. Store it securely (never commit to git!)

### Step 2: Test with curl (2 minutes)

**Send your first event:**

```bash
export API_KEY="your-api-key-here"

curl -X POST https://api.zapier.com/v1/events \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.created",
    "timestamp": "2025-11-12T10:30:00Z",
    "payload": {
      "user_id": "12345",
      "email": "user@example.com",
      "name": "John Doe"
    }
  }'
```

**Expected Response (201 Created):**
```json
{
  "event_id": "evt_550e8400e29b41d4",
  "event_type": "user.created",
  "timestamp": "2025-11-12T10:30:00.123456Z",
  "payload": {
    "user_id": "12345",
    "email": "user@example.com",
    "name": "John Doe"
  },
  "status": "received",
  "created_at": "2025-11-12T10:30:00.123456Z"
}
```

**Retrieve events from inbox:**

```bash
curl -X GET "https://api.zapier.com/v1/inbox?limit=10" \
  -H "X-API-Key: $API_KEY"
```

### Step 3: Try with Python (1 minute)

```python
import requests
import json
from datetime import datetime

API_KEY = "your-api-key-here"
API_URL = "https://api.zapier.com/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Send event
event = {
    "event_type": "order.created",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "payload": {
        "order_id": "order_123",
        "amount": 99.99,
        "customer_id": "cust_456"
    }
}

response = requests.post(f"{API_URL}/events", headers=headers, json=event)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Retrieve inbox
response = requests.get(f"{API_URL}/inbox?limit=10", headers=headers)
events = response.json()
print(f"Inbox has {len(events['events'])} undelivered events")
```

### Step 4: Try with Node.js (1 minute)

```javascript
const axios = require('axios');

const API_KEY = 'your-api-key-here';
const API_URL = 'https://api.zapier.com/v1';

const headers = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json'
};

// Send event
async function sendEvent() {
  const event = {
    event_type: 'order.created',
    timestamp: new Date().toISOString(),
    payload: {
      order_id: 'order_123',
      amount: 99.99,
      customer_id: 'cust_456'
    }
  };

  const response = await axios.post(`${API_URL}/events`, event, { headers });
  console.log('Event created:', response.data);
}

// Retrieve inbox
async function getInbox() {
  const response = await axios.get(`${API_URL}/inbox?limit=10`, { headers });
  console.log(`Inbox has ${response.data.events.length} undelivered events`);
}

sendEvent().then(getInbox).catch(console.error);
```

## Next Steps

1. **Explore Full API**: See [API Reference](./api-reference/) for all endpoints
2. **Install Sample Clients**: 
   - Python: `pip install zapier-triggers` ([Guide](../samples/python-client/README.md))
   - Node.js: `npm install zapier-triggers` ([Guide](../samples/node-client/README.md))
3. **Error Handling**: Read [Error Handling Guide](./error-handling.md)
4. **Rate Limiting**: Read [Rate Limiting Guide](./rate-limiting.md)
5. **Production Setup**: Follow [Production Checklist](./production-checklist.md)

## Common Integration Patterns

### Pattern 1: Real-time Event Streaming

Send events immediately as they occur in your system:

```python
# In your application code
def on_user_signup(user):
    send_to_zapier({
        "event_type": "user.signup",
        "payload": {
            "user_id": user.id,
            "email": user.email,
            "plan": user.plan
        }
    })
```

### Pattern 2: Batch Event Processing

Collect events and send in batches (more efficient):

```python
events = []

# Collect events
for order in recent_orders:
    events.append({
        "event_type": "order.created",
        "payload": {"order_id": order.id, "amount": order.total}
    })

# Send batch (max 100 per request)
for event in events:
    send_to_zapier(event)
```

### Pattern 3: Polling for Responses

Poll inbox for new events (webhook simulation):

```python
import time

def poll_inbox(interval_seconds=5):
    while True:
        response = requests.get(f"{API_URL}/inbox", headers=headers)
        events = response.json()['events']
        
        for event in events:
            process_event(event)
            # Acknowledge after processing
            requests.post(f"{API_URL}/events/{event['event_id']}/ack", headers=headers)
        
        time.sleep(interval_seconds)
```

## Troubleshooting

### 401 Unauthorized
- **Cause**: Missing or invalid API key
- **Solution**: Check X-API-Key header is set correctly

### 429 Too Many Requests
- **Cause**: Exceeded rate limit (1000 req/min)
- **Solution**: Implement exponential backoff, batch requests

### Events Disappearing
- **Cause**: Unacknowledged events auto-deleted after 72 hours
- **Solution**: Acknowledge events when processed

### Slow Performance
- **Cause**: Large payloads, network latency
- **Solution**: Reduce payload size, use compression

## Support

- **Documentation**: https://docs.zapier.com/api/triggers
- **Community**: https://community.zapier.com
- **Email**: api-support@zapier.com
- **Status**: https://status.zapier.com

## Rate Limits

- **Free Tier**: 100 requests/minute
- **Paid Tier**: 1000 requests/minute
- **Enterprise**: Custom limits (contact sales)

Headers returned in every response:
- `X-RateLimit-Limit`: Your rate limit
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

**Ready to build?** Check out our [sample applications](../samples/) for complete examples!
