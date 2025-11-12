"""
Rate Limiter

Distributed rate limiting using DynamoDB with rolling window.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
import boto3
from botocore.exceptions import ClientError


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        """
        Initialize rate limit error.

        Args:
            retry_after: Seconds until rate limit resets
        """
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """
    Distributed rate limiter using DynamoDB.

    Implements a rolling window rate limiter with 60-second windows.
    Uses DynamoDB atomic counters and TTL for automatic cleanup.
    """

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize the rate limiter.

        Args:
            table_name: DynamoDB table name for rate limit tracking
                       (defaults to environment variable RATE_LIMIT_TABLE_NAME)
        """
        self.table_name = table_name or os.environ.get('RATE_LIMIT_TABLE_NAME', '')
        if not self.table_name:
            # Fallback to API_KEYS_TABLE_NAME with rate_limit prefix
            # For simplicity, we use the same table with a composite key
            self.table_name = os.environ.get('API_KEYS_TABLE_NAME', '')

        if not self.table_name:
            raise ValueError("RATE_LIMIT_TABLE_NAME or API_KEYS_TABLE_NAME must be set")

        self.dynamodb = boto3.client('dynamodb')
        self.window_seconds = 60  # 60-second rolling window

    def check_rate_limit(self, key_id: str, rate_limit: int) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.

        Uses a sliding window approach with DynamoDB atomic operations.
        The window is based on the current minute (Unix timestamp / 60).

        Args:
            key_id: API key identifier
            rate_limit: Maximum requests per minute

        Returns:
            Tuple of (is_allowed, requests_remaining)

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        # Calculate current window (minute-based)
        current_time = int(time.time())
        window_key = current_time // self.window_seconds

        # Create composite key for rate limiting
        # Format: rl#{key_id}#{window}
        rate_limit_key = f"rl#{key_id}#{window_key}"

        # Calculate TTL (expire after 2 minutes to ensure cleanup)
        ttl = current_time + (self.window_seconds * 2)

        try:
            # Atomic increment with conditional check
            response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': rate_limit_key},
                    'key_id': {'S': 'rate_limit_counter'}
                },
                UpdateExpression='SET request_count = if_not_exists(request_count, :zero) + :inc, '
                                 'ttl = :ttl, '
                                 'window_start = if_not_exists(window_start, :timestamp)',
                ExpressionAttributeValues={
                    ':zero': {'N': '0'},
                    ':inc': {'N': '1'},
                    ':ttl': {'N': str(ttl)},
                    ':timestamp': {'N': str(current_time)},
                    ':limit': {'N': str(rate_limit)}
                },
                ConditionExpression='attribute_not_exists(request_count) OR request_count < :limit',
                ReturnValues='ALL_NEW'
            )

            # Get updated count
            new_count = int(response['Attributes']['request_count']['N'])
            remaining = max(0, rate_limit - new_count)

            return True, remaining

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Rate limit exceeded
                raise RateLimitError(retry_after=self.window_seconds)

            # Other errors - log and allow (fail open for availability)
            print(f"Rate limit check failed: {e}")
            return True, rate_limit  # Fail open

    def get_current_usage(self, key_id: str) -> int:
        """
        Get current request count for a key in the current window.

        Args:
            key_id: API key identifier

        Returns:
            Current request count
        """
        current_time = int(time.time())
        window_key = current_time // self.window_seconds
        rate_limit_key = f"rl#{key_id}#{window_key}"

        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': rate_limit_key},
                    'key_id': {'S': 'rate_limit_counter'}
                }
            )

            if 'Item' in response:
                return int(response['Item']['request_count']['N'])
            return 0

        except ClientError as e:
            print(f"Failed to get current usage: {e}")
            return 0

    def reset_rate_limit(self, key_id: str) -> bool:
        """
        Reset rate limit for a key (for testing/admin purposes).

        Args:
            key_id: API key identifier

        Returns:
            True if successful, False otherwise
        """
        current_time = int(time.time())
        window_key = current_time // self.window_seconds
        rate_limit_key = f"rl#{key_id}#{window_key}"

        try:
            self.dynamodb.delete_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': rate_limit_key},
                    'key_id': {'S': 'rate_limit_counter'}
                }
            )
            return True

        except ClientError as e:
            print(f"Failed to reset rate limit: {e}")
            return False
