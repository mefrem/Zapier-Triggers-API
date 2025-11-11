"""
Custom Authorizer Lambda Handler

Validates API keys from X-API-Key header.
Enhanced with proper error handling, expiration checks, and correlation IDs.
"""

import json
import os
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from src.repositories.api_key_repository import APIKeyRepository
from src.utils.rate_limiter import RateLimiter, RateLimitError


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway custom authorizer handler.

    Args:
        event: API Gateway authorizer event
        context: Lambda context

    Returns:
        IAM policy document

    Raises:
        Exception: 'Unauthorized' if authentication fails
    """
    # Generate correlation ID for tracing
    correlation_id = str(uuid.uuid4())

    try:
        # Extract API key from header
        api_key = extract_api_key_from_headers(event.get('headers', {}))
        if not api_key:
            log_auth_event(correlation_id, "MISSING_API_KEY", "API key not provided in request")
            raise Exception('Unauthorized')

        # Hash the API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Initialize repository
        try:
            repository = APIKeyRepository()
        except ValueError as e:
            log_auth_event(correlation_id, "CONFIG_ERROR", str(e))
            raise Exception('Unauthorized')

        # Lookup API key by hash
        api_key_record = repository.get_by_hash(key_hash)
        if not api_key_record:
            log_auth_event(correlation_id, "INVALID_KEY", f"API key not found: {key_hash[:8]}...")
            raise Exception('Unauthorized')

        # Check if key is active
        if not api_key_record.is_active:
            log_auth_event(
                correlation_id,
                "INACTIVE_KEY",
                f"API key is inactive: {api_key_record.key_id}"
            )
            raise Exception('Unauthorized')

        # Check if key is expired
        if is_key_expired(api_key_record.expires_at):
            log_auth_event(
                correlation_id,
                "EXPIRED_KEY",
                f"API key has expired: {api_key_record.key_id}"
            )
            raise Exception('Unauthorized')

        # Check rate limit
        try:
            rate_limiter = RateLimiter()
            is_allowed, remaining = rate_limiter.check_rate_limit(
                api_key_record.key_id,
                api_key_record.rate_limit
            )
        except RateLimitError as e:
            log_auth_event(
                correlation_id,
                "RATE_LIMIT_EXCEEDED",
                f"Rate limit exceeded for key: {api_key_record.key_id}"
            )
            # Note: API Gateway custom authorizers can't return 429 directly
            # The handler must raise 'Unauthorized' exception
            # Rate limit responses are handled at the API Gateway level
            raise Exception('Unauthorized')
        except Exception as e:
            # Rate limiter error - fail open (allow request)
            log_auth_event(
                correlation_id,
                "RATE_LIMIT_ERROR",
                f"Rate limiter error (failing open): {str(e)}"
            )
            remaining = api_key_record.rate_limit

        # Update last_used_at (fire and forget)
        try:
            repository.update_last_used(api_key_record.user_id, api_key_record.key_id)
        except Exception as e:
            log_auth_event(
                correlation_id,
                "UPDATE_ERROR",
                f"Failed to update last_used_at: {str(e)}"
            )

        # Generate allow policy
        policy = generate_policy(
            principal_id=api_key_record.user_id,
            effect='Allow',
            resource=event['methodArn'],
            context={
                'user_id': api_key_record.user_id,
                'key_id': api_key_record.key_id,
                'correlation_id': correlation_id,
                'scopes': ','.join(api_key_record.scopes),
                'rate_limit_remaining': str(remaining)
            }
        )

        log_auth_event(
            correlation_id,
            "AUTHORIZED",
            f"User authorized: {api_key_record.user_id}"
        )
        return policy

    except Exception as e:
        log_auth_event(correlation_id, "UNAUTHORIZED", f"Authorization failed: {str(e)}")
        raise Exception('Unauthorized')


def extract_api_key_from_headers(headers: Dict[str, str]) -> Optional[str]:
    """
    Extract API key from request headers (case-insensitive).

    Args:
        headers: Request headers

    Returns:
        API key if found, None otherwise
    """
    # Check both X-API-Key and x-api-key (case insensitive)
    for key in ['X-API-Key', 'x-api-key', 'X-Api-Key']:
        if key in headers:
            return headers[key]
    return None


def is_key_expired(expires_at: Optional[str]) -> bool:
    """
    Check if an API key has expired.

    Args:
        expires_at: ISO 8601 expiration timestamp (optional)

    Returns:
        True if expired, False otherwise
    """
    if not expires_at:
        return False  # No expiration set

    try:
        expiration_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        return current_time > expiration_time
    except (ValueError, AttributeError):
        # Invalid timestamp format, treat as not expired to avoid breaking auth
        return False


def log_auth_event(correlation_id: str, event_type: str, message: str) -> None:
    """
    Log authentication event with correlation ID.

    Args:
        correlation_id: Unique request identifier
        event_type: Type of auth event (AUTHORIZED, UNAUTHORIZED, etc.)
        message: Log message
    """
    print(json.dumps({
        'correlation_id': correlation_id,
        'event_type': event_type,
        'message': message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }))


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
