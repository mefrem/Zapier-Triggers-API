# Runbook: High Error Rate (>5%)

## Issue Description
Error rate has exceeded 5% threshold, indicating potential system issues affecting API reliability.

## Symptoms
- CloudWatch alarm 'zapier-triggers-api-high-error-rate' is in ALARM state
- Email alert received from ops-alerts@zapier.com
- Dashboard shows elevated error count
- Customer complaints about failed requests

## Diagnosis Steps

### 1. Check CloudWatch Dashboard
Navigate to: https://console.aws.amazon.com/cloudwatch/dashboards
- View current error rate percentage
- Identify affected endpoints (POST /events, GET /inbox, etc.)
- Check error trend (increasing, stable, decreasing)

### 2. Run CloudWatch Insights Query
Navigate to CloudWatch Logs Insights

**Query: Find top errors**
```
fields @timestamp, @message, status_code, error_code, user_id, path
| filter status_code >= 400
| stats count() as error_count by error_code
| sort error_count desc
```

**Query: Find affected endpoints**
```
fields @timestamp, path, status_code, method
| filter status_code >= 400
| stats count() as error_count by path, status_code
| sort error_count desc
```

**Query: Find affected users**
```
fields @timestamp, user_id, error_code
| filter status_code >= 400
| stats count() as error_count by user_id
| sort error_count desc
| limit 20
```

### 3. Check Recent Deployments
```bash
# Check recent Lambda deployments
aws lambda list-versions-by-function \
  --function-name zapier-triggers-api \
  --max-items 5

# Check when current version was deployed
aws lambda get-function \
  --function-name zapier-triggers-api \
  --query 'Configuration.LastModified'
```

### 4. Review Error Types

Common error patterns:

- **DynamoDB ProvisionedThroughputExceededException**: DynamoDB throttling
- **Lambda Timeout**: Function exceeding time limit
- **ValidationException**: Invalid request payload
- **UnauthorizedException**: Authentication failures
- **InternalServerError**: Code bugs or external dependency failures

## Resolution Steps

### For DynamoDB Throttling (ProvisionedThroughputExceededException)

```bash
# Check current capacity
aws dynamodb describe-table \
  --table-name triggers-api-events \
  --query 'Table.ProvisionedThroughput'

# Temporarily increase capacity (if auto-scaling not fast enough)
aws dynamodb update-table \
  --table-name triggers-api-events \
  --provisioned-throughput \
    ReadCapacityUnits=500,WriteCapacityUnits=1000
```

### For Lambda Timeout Errors

```bash
# Check Lambda timeout setting
aws lambda get-function-configuration \
  --function-name zapier-triggers-api \
  --query 'Timeout'

# Increase timeout if needed (max 900 seconds)
aws lambda update-function-configuration \
  --function-name zapier-triggers-api \
  --timeout 60
```

### For Code Bugs (InternalServerError)

```bash
# Review recent code changes
git log --oneline -10

# Rollback to previous version if needed
aws lambda update-function-configuration \
  --function-name zapier-triggers-api \
  --environment Variables={ACTIVE_VERSION=<previous-version>}

# Or use Lambda aliases for blue/green deployment
aws lambda update-alias \
  --function-name zapier-triggers-api \
  --name live \
  --function-version <previous-version>
```

### For Authentication Failures

```bash
# Check if API key validation is failing
# Review authentication logs
aws logs tail /aws/lambda/zapier-triggers-api \
  --filter-pattern "authentication failed" \
  --since 1h
```

## Prevention

1. **Enable Auto-Scaling**: Ensure DynamoDB auto-scaling is configured
2. **Load Testing**: Run load tests before deploying major changes
3. **Canary Deployments**: Roll out changes gradually (10% → 50% → 100%)
4. **Error Rate Monitoring**: Lower alarm threshold to 2% for earlier detection
5. **Pre-Deployment Testing**: Run full integration test suite
6. **Code Review**: Require 2+ approvals for production deployments

## Escalation

- **5 minutes**: No improvement → Notify Tech Lead
- **15 minutes**: Still critical → Page VP Engineering
- **30 minutes**: Customer impact → Notify Customer Success team
- **1 hour**: Consider complete rollback to last known good version

## Post-Incident

1. Create incident report (template: docs/templates/incident-report.md)
2. Schedule post-mortem within 24 hours
3. Document root cause and resolution
4. Update runbook with lessons learned
5. Implement preventive measures

## Contacts

- **Platform Slack**: #zapier-triggers-api
- **On-Call Engineer**: PagerDuty rotation
- **Tech Lead**: via Slack DM
- **Wiki**: https://wiki.zapier.com/api/triggers/
- **Incidents**: https://incidents.zapier.com/

## Related Alarms

- `zapier-triggers-api-high-error-rate` (this alarm)
- `zapier-triggers-api-high-latency-p95` (often correlated)
- `zapier-triggers-api-dynamodb-throttling`

## References

- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/dashboards)
- [X-Ray Service Map](https://console.aws.amazon.com/xray/home#/service-map)
- [DynamoDB Metrics](https://console.aws.amazon.com/dynamodb/home#tables)
- [Lambda Monitoring](https://console.aws.amazon.com/lambda/home#/functions)

---

**Last Updated**: 2025-11-12
**Version**: 1.0
**Owner**: Platform Team
