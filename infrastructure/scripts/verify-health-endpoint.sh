#!/bin/bash
#
# Health Check Endpoint Verification Script
#
# This script verifies that the health check endpoint is functioning correctly
# in the deployed environment.
#
# Usage: ./verify-health-endpoint.sh [environment]
#   environment: dev, staging, or production (default: dev)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-dev}"
TERRAFORM_DIR="../terraform/environments/${ENVIRONMENT}"

echo "========================================="
echo "Health Check Endpoint Verification"
echo "Environment: ${ENVIRONMENT}"
echo "========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}ERROR: terraform not found. Please install Terraform.${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: aws CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}ERROR: jq not found. Please install jq.${NC}"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo -e "${RED}ERROR: curl not found. Please install curl.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites installed${NC}"
echo ""

# Get API Gateway URL from Terraform outputs
echo "Retrieving API Gateway URL..."

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}ERROR: Terraform directory not found: $TERRAFORM_DIR${NC}"
    exit 1
fi

cd "$TERRAFORM_DIR"

if [ ! -f ".terraform/terraform.tfstate" ] && [ ! -f "terraform.tfstate" ]; then
    echo -e "${YELLOW}WARNING: No terraform state found. Have you deployed yet?${NC}"
    echo "Please run 'terraform apply' first."
    exit 1
fi

API_URL=$(terraform output -raw api_gateway_url 2>/dev/null)

if [ -z "$API_URL" ]; then
    echo -e "${RED}ERROR: Could not retrieve api_gateway_url from Terraform outputs${NC}"
    echo "Make sure Terraform has been applied successfully."
    exit 1
fi

HEALTH_URL="${API_URL}/health"
echo -e "${GREEN}✓ API Gateway URL: ${API_URL}${NC}"
echo -e "  Health endpoint: ${HEALTH_URL}"
echo ""

# Test 1: Basic connectivity
echo "Test 1: Basic HTTP connectivity..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ HTTP 200 OK received${NC}"
else
    echo -e "${RED}✗ FAILED: Expected HTTP 200, got HTTP ${HTTP_CODE}${NC}"
    exit 1
fi
echo ""

# Test 2: Response body validation
echo "Test 2: Response body validation..."
RESPONSE=$(curl -s "${HEALTH_URL}")

echo "Response body:"
echo "$RESPONSE" | jq '.'

# Check required fields
STATUS=$(echo "$RESPONSE" | jq -r '.status')
TIMESTAMP=$(echo "$RESPONSE" | jq -r '.timestamp')
VERSION=$(echo "$RESPONSE" | jq -r '.version')
ENV=$(echo "$RESPONSE" | jq -r '.environment')
CHECKS=$(echo "$RESPONSE" | jq -r '.checks')

FAILED=0

if [ "$STATUS" != "healthy" ]; then
    echo -e "${RED}✗ FAILED: status field should be 'healthy', got '${STATUS}'${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Status: healthy${NC}"
fi

if [ -z "$TIMESTAMP" ] || [ "$TIMESTAMP" = "null" ]; then
    echo -e "${RED}✗ FAILED: timestamp field is missing or null${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Timestamp: ${TIMESTAMP}${NC}"
fi

if [ -z "$VERSION" ] || [ "$VERSION" = "null" ]; then
    echo -e "${RED}✗ FAILED: version field is missing or null${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Version: ${VERSION}${NC}"
fi

if [ "$ENV" != "$ENVIRONMENT" ]; then
    echo -e "${YELLOW}WARNING: environment field is '${ENV}', expected '${ENVIRONMENT}'${NC}"
else
    echo -e "${GREEN}✓ Environment: ${ENV}${NC}"
fi

if [ -z "$CHECKS" ] || [ "$CHECKS" = "null" ]; then
    echo -e "${RED}✗ FAILED: checks field is missing or null${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Checks object present${NC}"
fi

# Validate checks sub-fields
DYNAMODB_CHECK=$(echo "$RESPONSE" | jq -r '.checks.dynamodb')
ENV_CONFIG_CHECK=$(echo "$RESPONSE" | jq -r '.checks.environment_config')

if [ "$DYNAMODB_CHECK" != "true" ]; then
    echo -e "${RED}✗ FAILED: DynamoDB check is not true (got: ${DYNAMODB_CHECK})${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ DynamoDB check: passed${NC}"
fi

if [ "$ENV_CONFIG_CHECK" != "true" ]; then
    echo -e "${RED}✗ FAILED: Environment config check is not true (got: ${ENV_CONFIG_CHECK})${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Environment config check: passed${NC}"
fi

if [ $FAILED -eq 1 ]; then
    echo ""
    echo -e "${RED}Response body validation FAILED${NC}"
    exit 1
fi
echo ""

# Test 3: Response headers
echo "Test 3: Response headers validation..."
HEADERS=$(curl -s -I "${HEALTH_URL}")

if echo "$HEADERS" | grep -q "Content-Type: application/json"; then
    echo -e "${GREEN}✓ Content-Type: application/json${NC}"
else
    echo -e "${RED}✗ FAILED: Content-Type header missing or incorrect${NC}"
    FAILED=1
fi

if echo "$HEADERS" | grep -q "Access-Control-Allow-Origin"; then
    echo -e "${GREEN}✓ CORS headers present${NC}"
else
    echo -e "${YELLOW}WARNING: CORS headers not found${NC}"
fi
echo ""

# Test 4: Response time
echo "Test 4: Response time check..."
START=$(date +%s%N)
curl -s "${HEALTH_URL}" > /dev/null
END=$(date +%s%N)
DURATION_MS=$(( ($END - $START) / 1000000 ))

echo "Response time: ${DURATION_MS}ms"

if [ $DURATION_MS -lt 1000 ]; then
    echo -e "${GREEN}✓ Response time under 1 second${NC}"
elif [ $DURATION_MS -lt 3000 ]; then
    echo -e "${YELLOW}WARNING: Response time is ${DURATION_MS}ms (should be under 1000ms)${NC}"
else
    echo -e "${RED}✗ FAILED: Response time is too slow (${DURATION_MS}ms)${NC}"
    FAILED=1
fi
echo ""

# Test 5: Multiple requests (basic load test)
echo "Test 5: Consistency check (10 requests)..."
SUCCESS_COUNT=0
for i in {1..10}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}")
    if [ "$HTTP_CODE" = "200" ]; then
        ((SUCCESS_COUNT++))
    fi
done

echo "Successful requests: ${SUCCESS_COUNT}/10"
if [ $SUCCESS_COUNT -eq 10 ]; then
    echo -e "${GREEN}✓ All requests successful${NC}"
elif [ $SUCCESS_COUNT -ge 8 ]; then
    echo -e "${YELLOW}WARNING: ${SUCCESS_COUNT}/10 requests succeeded${NC}"
else
    echo -e "${RED}✗ FAILED: Only ${SUCCESS_COUNT}/10 requests succeeded${NC}"
    FAILED=1
fi
echo ""

# Test 6: Verify Lambda function directly
echo "Test 6: Direct Lambda invocation..."
LAMBDA_NAME="zapier-triggers-api-health-check-${ENVIRONMENT}"
LAMBDA_RESPONSE_FILE="/tmp/health-lambda-response-$$.json"

if aws lambda invoke \
    --function-name "$LAMBDA_NAME" \
    --payload '{"httpMethod":"GET","path":"/health"}' \
    --query 'StatusCode' \
    --output text \
    "$LAMBDA_RESPONSE_FILE" > /dev/null 2>&1; then

    LAMBDA_STATUS=$(cat "$LAMBDA_RESPONSE_FILE" | jq -r '.statusCode')
    if [ "$LAMBDA_STATUS" = "200" ]; then
        echo -e "${GREEN}✓ Lambda invocation successful (HTTP $LAMBDA_STATUS)${NC}"
    else
        echo -e "${RED}✗ FAILED: Lambda returned HTTP $LAMBDA_STATUS${NC}"
        FAILED=1
    fi
    rm -f "$LAMBDA_RESPONSE_FILE"
else
    echo -e "${YELLOW}WARNING: Could not invoke Lambda directly (may lack permissions)${NC}"
fi
echo ""

# Test 7: CloudWatch Logs
echo "Test 7: CloudWatch Logs verification..."
LOG_GROUP="/aws/lambda/${LAMBDA_NAME}"

if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --query 'logGroups[0].logGroupName' --output text > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CloudWatch log group exists${NC}"

    # Get most recent log stream
    LATEST_STREAM=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --query 'logStreams[0].logStreamName' \
        --output text 2>/dev/null)

    if [ -n "$LATEST_STREAM" ] && [ "$LATEST_STREAM" != "None" ]; then
        echo -e "${GREEN}✓ Recent log entries found${NC}"
    else
        echo -e "${YELLOW}WARNING: No recent log entries found${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: Could not verify CloudWatch logs (may lack permissions)${NC}"
fi
echo ""

# Final summary
echo "========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo "Health check endpoint is functioning correctly."
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "Please review the errors above and fix the issues."
    exit 1
fi
