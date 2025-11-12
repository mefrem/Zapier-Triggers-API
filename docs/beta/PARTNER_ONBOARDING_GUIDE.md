# Zapier Triggers API - Beta Partner Onboarding Guide

Welcome to the Zapier Triggers API Beta Program! This guide will help you integrate in 5 minutes.

## Welcome

Thank you for partnering with us to validate our new event delivery platform. As a beta partner, you'll get early access to the API and direct support from our engineering team.

## Your Beta Partner Information

- **Partner ID**: [Assigned by team]
- **API Key**: `sk_beta_[partner]_...` (sent separately via secure email)
- **Rate Limit**: 100 requests/second (10x higher than standard tier)
- **Support Channel**: #[partner]-beta on Slack
- **Primary Contact**: [Your name], [email]
- **Beta Duration**: 6 weeks (until [end date])

## 5-Minute Quick Start

### Step 1: Verify Your API Key (1 minute)

```bash
export API_KEY="sk_beta_your_key_here"

curl -X GET https://api.zapier.com/v1/health \
  -H "X-API-Key: $API_KEY"

# Should return: {"status": "healthy", ...}
```

### Step 2: Send Your First Event (2 minutes)

```bash
curl -X POST https://api.zapier.com/v1/events \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "timestamp": "2025-11-12T10:30:00Z",
    "payload": {
      "order_id": "order_001",
      "customer_email": "customer@example.com",
      "amount": 99.99
    }
  }'

# Should return: {"event_id": "evt_...", "status": "received", ...}
```

### Step 3: Retrieve Events from Inbox (2 minutes)

```bash
curl -X GET "https://api.zapier.com/v1/inbox?limit=10" \
  -H "X-API-Key: $API_KEY"

# Should return: {"events": [...], "has_more": false}
```

## Common Integration Patterns

### Pattern 1: Real-Time Event Streaming

Send events immediately as they occur:

```python
import requests
from datetime import datetime

API_KEY = "sk_beta_your_key_here"
API_URL = "https://api.zapier.com/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def send_event(event_type, payload):
    event = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": payload
    }
    
    response = requests.post(f"{API_URL}/events", headers=headers, json=event)
    return response.json()

# Example: Send order created event
send_event("order.created", {
    "order_id": "order_123",
    "amount": 99.99,
    "customer_id": "cust_456"
})
```

### Pattern 2: Batch Processing

Collect and send events in batches:

```python
events = []

for order in recent_orders:
    events.append({
        "event_type": "order.created",
        "timestamp": order.created_at.isoformat() + "Z",
        "payload": {
            "order_id": order.id,
            "amount": order.total
        }
    })

# Send each event (max 100/sec for beta partners)
for event in events:
    send_event(event["event_type"], event["payload"])
```

### Pattern 3: Polling for Events

Poll inbox periodically:

```python
import time

def poll_inbox(interval_seconds=5):
    while True:
        response = requests.get(f"{API_URL}/inbox?limit=100", headers=headers)
        events = response.json()["events"]
        
        for event in events:
            process_event(event)
            # Acknowledge after processing
            requests.post(
                f"{API_URL}/events/{event['event_id']}/ack",
                headers=headers
            )
        
        time.sleep(interval_seconds)

poll_inbox()
```

## Beta Program Expectations

### What We Provide
- Direct Slack support (#[partner]-beta channel)
- Weekly check-in calls (30 min)
- Immediate bug fixes and feature requests
- Early access to new features
- Dedicated partner manager

### What We Ask
- Honest feedback (good and bad!)
- Weekly usage report (we'll provide template)
- Bug reports with reproduction steps
- Participate in weekly survey (2 min)
- Join bi-weekly beta call (30 min, optional)

## Support

### Slack Channel: #[partner]-beta
- Real-time support (business hours)
- Response time: <2 hours
- Technical questions, bug reports

### Email: beta-support@zapier.com
- Non-urgent questions
- Response time: 24 hours

### Weekly Check-In Call
- Scheduled: [Day/Time]
- Zoom link: [Link]
- Agenda: Progress, blockers, feedback

### Escalation
- Critical issues: @mention partner manager in Slack
- Emergency contact: [Phone number]

## Troubleshooting

### 401 Unauthorized
- **Issue**: Invalid or missing API key
- **Solution**: Check X-API-Key header, verify key hasn't expired

### 429 Too Many Requests
- **Issue**: Exceeded 100 req/sec rate limit
- **Solution**: Implement exponential backoff, batch requests

### Events Disappearing
- **Issue**: Unacknowledged events auto-deleted after 72 hours
- **Solution**: Acknowledge events promptly after processing

### Slow Performance
- **Issue**: High latency
- **Solution**: Report to Slack channel with details (endpoint, time, event IDs)

## Resources

- **API Documentation**: https://docs.zapier.com/api/triggers
- **OpenAPI Spec**: https://api.zapier.com/openapi.yaml
- **Sample Code**: [GitHub repo link]
- **Status Page**: https://status.zapier.com

## Feedback

We value your input! Please share:
- What's working well
- What's frustrating
- Missing features
- Performance concerns
- Any integration challenges

**Weekly Survey**: [Google Forms link]  
**Slack**: #[partner]-beta  
**Email**: beta-support@zapier.com

## Next Steps

1. ✓ Complete 5-minute quick start
2. Integrate API into your system
3. Join weekly check-in call
4. Complete weekly feedback survey
5. Help us build the best API possible!

---

**Thank you for being a beta partner!**

Questions? Reach out on Slack (#[partner]-beta) or email beta-support@zapier.com.
