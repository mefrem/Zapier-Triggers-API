"""
Health Check Lambda Handler

Returns API health status and performs basic dependency checks.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Health check endpoint handler.

    Returns:
        API Gateway proxy response with health status
    """
    try:
        # Get environment variables
        environment = os.environ.get('ENVIRONMENT', 'unknown')
        events_table_name = os.environ.get('EVENTS_TABLE_NAME', '')
        api_keys_table_name = os.environ.get('API_KEYS_TABLE_NAME', '')

        # Perform basic dependency checks
        checks = {
            'dynamodb': check_dynamodb_connectivity(events_table_name),
            'environment_config': bool(events_table_name and api_keys_table_name)
        }

        # Determine overall health status
        is_healthy = all(checks.values())
        status_code = 200 if is_healthy else 503

        response_body = {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': '1.0.0',
            'environment': environment,
            'checks': checks
        }

        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-API-Key',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps(response_body)
        }

    except Exception as e:
        # Log error and return 500
        print(f"Health check error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'message': 'Internal server error during health check'
            })
        }


def check_dynamodb_connectivity(table_name: str) -> bool:
    """
    Check if DynamoDB table is accessible.

    Args:
        table_name: DynamoDB table name

    Returns:
        True if table is accessible, False otherwise
    """
    if not table_name:
        return False

    try:
        dynamodb = boto3.client('dynamodb')
        # Describe table to verify connectivity
        dynamodb.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        print(f"DynamoDB connectivity check failed: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error checking DynamoDB: {str(e)}")
        return False
