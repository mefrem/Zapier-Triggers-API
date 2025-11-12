# Incident Response Runbook - Zapier Triggers API

## Overview

This runbook provides step-by-step procedures for responding to incidents affecting the Zapier Triggers API.

**On-Call Rotation**: PagerDuty  
**Incident Channel**: #incidents on Slack  
**Status Page**: https://status.zapier.com

## Incident Categories & Severity

### P1 - Critical (Page Immediately)
- API completely unavailable (500 errors >5%)
- Data loss or corruption
- Security breach
- **Response Time**: 5 minutes
- **Escalation**: Immediate (Tech Lead + VP Eng)

### P2 - High (Notify Urgently)
- Elevated error rate (1-5%)
- High latency (p95 >200ms)
- Partial service degradation
- **Response Time**: 15 minutes
- **Escalation**: After 30 min if no progress

### P3 - Medium (Standard Response)
- Minor performance degradation
- Non-critical feature issues
- **Response Time**: 1 hour
- **Escalation**: If SLA breach imminent

## Incident Response Flow

### 1. Detection
- CloudWatch alarm triggers
- PagerDuty notification sent
- Customer reports via support

### 2. Acknowledgment
- On-call engineer acknowledges in PagerDuty
- Create Slack thread in #incidents
- Post initial status update

### 3. Investigation
- Check CloudWatch dashboard
- Review CloudWatch Logs
- Check X-Ray service map
- Identify root cause

### 4. Mitigation
- Implement temporary fix
- Rollback if needed
- Verify service restored

### 5. Communication
- Update status page
- Notify affected customers
- Post updates every 15 min (P1/P2)

### 6. Resolution
- Verify metrics normalized
- Confirm customer impact resolved
- Document timeline and actions

### 7. Post-Mortem
- Schedule within 24 hours
- Document root cause
- Create action items

## Common Incidents

### Incident: API Unavailable (500 Errors >5%)

**Severity**: P1 (Critical)

**Diagnosis**:
1. Check health endpoint: `curl https://api.zapier.com/v1/health`
2. Review Lambda logs for errors
3. Check DynamoDB for throttling
4. Verify network connectivity

**Resolution**:
```bash
# Check Lambda status
aws lambda get-function-configuration \
  --function-name zapier-triggers-api

# Review recent errors
aws logs tail /aws/lambda/zapier-triggers-api --since 5m \
  | grep ERROR

# If code bug: Rollback
aws lambda update-alias \
  --function-name zapier-triggers-api \
  --name live \
  --function-version <previous-version>

# If capacity issue: Scale DynamoDB
aws dynamodb update-table \
  --table-name triggers-api-events \
  --provisioned-throughput ReadCapacityUnits=500,WriteCapacityUnits=1000
```

**Communication Template**:
```
[INCIDENT] Zapier Triggers API Unavailable

Status: INVESTIGATING
Impact: API returning 500 errors, customers cannot send events
Started: [time]
ETA: Investigating

We're working to restore service. Updates every 15 minutes.

Status Page: https://status.zapier.com
Slack: #api-status
```

**Escalation**: If not resolved in 15 min, escalate to Tech Lead.

---

### Incident: High Latency (p95 >200ms)

**Severity**: P2 (High)

**Diagnosis**:
1. Check CloudWatch latency metrics
2. Review X-Ray traces
3. Check DynamoDB latency
4. Identify slow queries

**Resolution**:
```bash
# Check for cold starts
aws logs insights query \
  --log-group-name /aws/lambda/zapier-triggers-api \
  --query-string 'filter @type = "REPORT" | stats count(*) by @message'

# Enable provisioned concurrency if needed
aws lambda put-provisioned-concurrency-config \
  --function-name zapier-triggers-api \
  --provisioned-concurrent-executions 10 \
  --qualifier live

# Increase Lambda memory (improves CPU)
aws lambda update-function-configuration \
  --function-name zapier-triggers-api \
  --memory-size 1024
```

**Communication**: Notify affected partners via Slack.

---

### Incident: DynamoDB Throttling

**Severity**: P2 (High)

**Diagnosis**:
1. Check DynamoDB metrics for ProvisionedThroughputExceededException
2. Verify auto-scaling is enabled
3. Check capacity utilization

**Resolution**:
```bash
# Check current capacity
aws dynamodb describe-table \
  --table-name triggers-api-events \
  --query 'Table.ProvisionedThroughput'

# Increase capacity immediately
aws dynamodb update-table \
  --table-name triggers-api-events \
  --provisioned-throughput ReadCapacityUnits=500,WriteCapacityUnits=2000

# Verify auto-scaling enabled
aws application-autoscaling describe-scalable-targets \
  --service-namespace dynamodb
```

## On-Call Escalation

**Level 1: On-Call Engineer**
- First responder
- Response time: 5 minutes
- Authority: Restart services, rollback code

**Level 2: Tech Lead**
- Escalate after 15 min (P1) or 30 min (P2)
- Response time: 15 minutes
- Authority: Architecture changes, database operations

**Level 3: VP Engineering**
- Escalate after 30 min if no progress
- Response time: 30 minutes
- Authority: Customer communications, timeline decisions

## Communication Templates

### Status Update (During Incident)
```
[UPDATE] Zapier Triggers API Incident

Status: INVESTIGATING / IDENTIFIED / MONITORING
Impact: [describe customer impact]
Started: [time]
ETA: [estimated resolution time]

Current Actions:
- [action 1]
- [action 2]

Next Update: [time]
```

### Resolution Notification
```
[RESOLVED] Zapier Triggers API Incident

Status: RESOLVED
Impact: [what was affected]
Duration: [start time] - [end time]
Root Cause: [brief description]

The issue has been resolved. All services are operating normally.

Post-Mortem: [link] (available within 24 hours)
```

## Tools & Access

- **AWS Console**: https://console.aws.amazon.com
- **CloudWatch Dashboard**: [Link]
- **PagerDuty**: https://zapier.pagerduty.com
- **Slack**: #incidents, #api-status
- **Status Page Admin**: https://status.zapier.com/admin
- **Runbooks**: /docs/runbooks/

## Post-Incident Review

1. Create incident ticket (Jira)
2. Schedule post-mortem within 24 hours
3. Document timeline and actions
4. Identify root cause
5. Create action items (prevention, detection, response)
6. Update runbook with lessons learned

**Post-Mortem Template**: `docs/templates/post-mortem-template.md`

---

**Questions?** Contact Platform Team via #zapier-triggers-api Slack channel.
