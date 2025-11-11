"""
Custom Authorizer Lambda Handler

Validates API keys from X-API-Key header.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway custom authorizer handler.

    Args:
        event: API Gateway authorizer event
        context: Lambda context

    Returns:
        IAM policy document
    """
    try:
        # Extract API key from header
        api_key = None
        headers = event.get('headers', {})

        # Check both X-API-Key and x-api-key (case insensitive)
        for key in ['X-API-Key', 'x-api-key']:
            if key in headers:
                api_key = headers[key]
                break

        if not api_key:
            print("Missing API key in request headers")
            raise Exception('Unauthorized')

        # Hash the API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Lookup API key in DynamoDB
        api_keys_table_name = os.environ.get('API_KEYS_TABLE_NAME', '')
        if not api_keys_table_name:
            print("API_KEYS_TABLE_NAME environment variable not set")
            raise Exception('Unauthorized')

        dynamodb = boto3.client('dynamodb')

        # Query using KeyHashIndex GSI
        response = dynamodb.query(
            TableName=api_keys_table_name,
            IndexName='KeyHashIndex',
            KeyConditionExpression='key_hash = :key_hash',
            ExpressionAttributeValues={
                ':key_hash': {'S': key_hash}
            },
            Limit=1
        )

        items = response.get('Items', [])
        if not items:
            print(f"API key not found: {key_hash[:8]}...")
            raise Exception('Unauthorized')

        api_key_record = items[0]

        # Check if key is active
        is_active = api_key_record.get('is_active', {}).get('BOOL', False)
        if not is_active:
            print(f"API key is inactive: {key_hash[:8]}...")
            raise Exception('Unauthorized')

        # Extract user_id
        user_id = api_key_record.get('user_id', {}).get('S', 'unknown')
        key_id = api_key_record.get('key_id', {}).get('S', 'unknown')

        # Update last_used_at (fire and forget)
        try:
            dynamodb.update_item(
                TableName=api_keys_table_name,
                Key={
                    'user_id': {'S': user_id},
                    'key_id': {'S': key_id}
                },
                UpdateExpression='SET last_used_at = :timestamp',
                ExpressionAttributeValues={
                    ':timestamp': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            )
        except Exception as e:
            print(f"Failed to update last_used_at: {str(e)}")

        # Generate allow policy
        policy = generate_policy(
            principal_id=user_id,
            effect='Allow',
            resource=event['methodArn'],
            context={
                'user_id': user_id,
                'key_id': key_id
            }
        )

        print(f"Authorized user: {user_id}")
        return policy

    except Exception as e:
        print(f"Authorization failed: {str(e)}")
        raise Exception('Unauthorized')


def generate_policy(principal_id: str, effect: str, resource: str, context: Dict[str, str]) -> Dict[str, Any]:
    """
    Generate IAM policy for API Gateway.

    Args:
        principal_id: User ID
        effect: Allow or Deny
        resource: Resource ARN
        context: Additional context to pass to Lambda

    Returns:
        IAM policy document
    """
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        },
        'context': context
    }
