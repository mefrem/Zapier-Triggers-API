# Runbook: High Latency (p95 >100ms)

## Issue Description
p95 latency has exceeded 100ms threshold, indicating performance degradation affecting user experience.

## Symptoms
- CloudWatch alarm 'zapier-triggers-api-high-latency-p95' is in ALARM state
- p95 latency consistently >100ms for 10+ minutes
- Customer reports of slow API responses
- Dashboard shows elevated Lambda duration

## Diagnosis Steps

### 1. Check Current Latency
```bash
# Get recent latency metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=zapier-triggers-api \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,p95,p99
```

### 2. Check X-Ray Service Map
Navigate to X-Ray console to identify slow services:
- DynamoDB query latency
- External API calls
- Lambda cold starts
- SQS processing time

### 3. Check DynamoDB Performance
```bash
# Check DynamoDB latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name SuccessfulRequestLatency \
  --dimensions Name=TableName,Value=triggers-api-events \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,p95,p99
```

### 4. Check for Lambda Cold Starts
```bash
# Count cold starts vs warm starts
aws logs insights query \
  --log-group-name /aws/lambda/zapier-triggers-api \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'filter @type = "REPORT" | stats count(*) as total, sum(case(@message =~ /Init Duration/, 1, 0)) as cold_starts | extend cold_start_rate = cold_starts / total * 100'
```

## Resolution Steps

### For DynamoDB Slow Queries
1. Check query patterns - ensure GSI usage
2. Verify no full table scans
3. Increase provisioned capacity if throttling
4. Review index efficiency

### For Lambda Cold Starts
```bash
# Enable provisioned concurrency (keeps functions warm)
aws lambda put-provisioned-concurrency-config \
  --function-name zapier-triggers-api \
  --provisioned-concurrent-executions 10 \
  --qualifier live
```

### For High Lambda Duration
```bash
# Increase Lambda memory (also increases CPU)
aws lambda update-function-configuration \
  --function-name zapier-triggers-api \
  --memory-size 1024  # Increase from 512MB to 1024MB
```

### For External Dependencies
- Check if external services (AWS services) experiencing issues
- Review AWS Health Dashboard
- Check X-Ray for slow external calls
- Implement timeouts and circuit breakers

## Prevention
1. Provisioned concurrency for prod (10+ instances)
2. Regular performance testing (weekly)
3. Monitor DynamoDB query efficiency
4. Cache frequently accessed data
5. Optimize database queries

## Escalation
- **10 minutes**: No improvement → Notify Tech Lead
- **30 minutes**: p95 >150ms → Escalate to VP Engineering
- **Contact**: Platform Team via #zapier-triggers-api Slack

## References
- [X-Ray Service Map](https://console.aws.amazon.com/xray/home#/service-map)
- [Lambda Performance Tuning Guide](docs/performance/lambda-tuning.md)
- [DynamoDB Query Optimization](docs/performance/dynamodb-optimization.md)

---
**Last Updated**: 2025-11-12
