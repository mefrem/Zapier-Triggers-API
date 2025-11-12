"""
Unit tests for rate limiter.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.utils.rate_limiter import RateLimiter, RateLimitError


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB client."""
    with patch('boto3.client') as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        yield mock_db


@pytest.fixture
def rate_limiter(mock_dynamodb):
    """Create RateLimiter with mocked DynamoDB."""
    with patch.dict('os.environ', {'API_KEYS_TABLE_NAME': 'test-api-keys'}):
        return RateLimiter()


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    def test_init_with_table_name(self, mock_dynamodb):
        """Test initialization with explicit table name."""
        limiter = RateLimiter(table_name='custom-table')
        assert limiter.table_name == 'custom-table'
        assert limiter.window_seconds == 60

    def test_init_with_env_var(self, mock_dynamodb):
        """Test initialization with environment variable."""
        with patch.dict('os.environ', {'API_KEYS_TABLE_NAME': 'env-table'}):
            limiter = RateLimiter()
            assert limiter.table_name == 'env-table'

    def test_init_without_table_name_raises_error(self, mock_dynamodb):
        """Test initialization fails without table name."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="RATE_LIMIT_TABLE_NAME or API_KEYS_TABLE_NAME"):
                RateLimiter()


class TestCheckRateLimit:
    """Tests for check_rate_limit method."""

    def test_first_request_allowed(self, rate_limiter, mock_dynamodb):
        """Test first request is always allowed."""
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'request_count': {'N': '1'},
                'ttl': {'N': str(int(time.time()) + 120)},
                'window_start': {'N': str(int(time.time()))}
            }
        }

        is_allowed, remaining = rate_limiter.check_rate_limit('key-123', 1000)

        assert is_allowed is True
        assert remaining == 999
        mock_dynamodb.update_item.assert_called_once()

    def test_within_rate_limit(self, rate_limiter, mock_dynamodb):
        """Test requests within rate limit are allowed."""
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'request_count': {'N': '500'},
                'ttl': {'N': str(int(time.time()) + 120)},
                'window_start': {'N': str(int(time.time()))}
            }
        }

        is_allowed, remaining = rate_limiter.check_rate_limit('key-123', 1000)

        assert is_allowed is True
        assert remaining == 500

    def test_rate_limit_exceeded(self, rate_limiter, mock_dynamodb):
        """Test request exceeding rate limit raises error."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'UpdateItem'
        )

        with pytest.raises(RateLimitError) as exc_info:
            rate_limiter.check_rate_limit('key-123', 1000)

        assert exc_info.value.retry_after == 60
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_at_rate_limit_boundary(self, rate_limiter, mock_dynamodb):
        """Test request at exactly the rate limit."""
        # Simulate reaching exactly the limit
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'request_count': {'N': '1000'},
                'ttl': {'N': str(int(time.time()) + 120)},
                'window_start': {'N': str(int(time.time()))}
            }
        }

        is_allowed, remaining = rate_limiter.check_rate_limit('key-123', 1000)

        assert is_allowed is True
        assert remaining == 0

    def test_different_keys_independent_limits(self, rate_limiter, mock_dynamodb):
        """Test different keys have independent rate limits."""
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'request_count': {'N': '1'},
                'ttl': {'N': str(int(time.time()) + 120)},
                'window_start': {'N': str(int(time.time()))}
            }
        }

        # Key 1
        is_allowed1, _ = rate_limiter.check_rate_limit('key-1', 1000)

        # Key 2
        is_allowed2, _ = rate_limiter.check_rate_limit('key-2', 1000)

        assert is_allowed1 is True
        assert is_allowed2 is True
        assert mock_dynamodb.update_item.call_count == 2

        # Verify different composite keys were used
        calls = mock_dynamodb.update_item.call_args_list
        key1 = calls[0][1]['Key']['user_id']['S']
        key2 = calls[1][1]['Key']['user_id']['S']
        assert 'key-1' in key1
        assert 'key-2' in key2
        assert key1 != key2

    def test_dynamo_error_fails_open(self, rate_limiter, mock_dynamodb):
        """Test DynamoDB errors fail open (allow request)."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'UpdateItem'
        )

        is_allowed, remaining = rate_limiter.check_rate_limit('key-123', 1000)

        # Should fail open and allow the request
        assert is_allowed is True
        assert remaining == 1000

    def test_rate_limit_key_format(self, rate_limiter, mock_dynamodb):
        """Test rate limit key format includes window."""
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'request_count': {'N': '1'},
                'ttl': {'N': str(int(time.time()) + 120)},
                'window_start': {'N': str(int(time.time()))}
            }
        }

        rate_limiter.check_rate_limit('key-123', 1000)

        # Verify the composite key format
        call_args = mock_dynamodb.update_item.call_args
        user_id = call_args[1]['Key']['user_id']['S']

        assert user_id.startswith('rl#key-123#')
        assert '#' in user_id


class TestGetCurrentUsage:
    """Tests for get_current_usage method."""

    def test_get_usage_exists(self, rate_limiter, mock_dynamodb):
        """Test getting usage when record exists."""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'request_count': {'N': '750'}
            }
        }

        usage = rate_limiter.get_current_usage('key-123')

        assert usage == 750
        mock_dynamodb.get_item.assert_called_once()

    def test_get_usage_not_exists(self, rate_limiter, mock_dynamodb):
        """Test getting usage when record doesn't exist."""
        mock_dynamodb.get_item.return_value = {}

        usage = rate_limiter.get_current_usage('key-123')

        assert usage == 0

    def test_get_usage_error_returns_zero(self, rate_limiter, mock_dynamodb):
        """Test error during get usage returns zero."""
        mock_dynamodb.get_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'GetItem'
        )

        usage = rate_limiter.get_current_usage('key-123')

        assert usage == 0


class TestResetRateLimit:
    """Tests for reset_rate_limit method."""

    def test_reset_success(self, rate_limiter, mock_dynamodb):
        """Test successful rate limit reset."""
        mock_dynamodb.delete_item.return_value = {}

        result = rate_limiter.reset_rate_limit('key-123')

        assert result is True
        mock_dynamodb.delete_item.assert_called_once()

    def test_reset_error(self, rate_limiter, mock_dynamodb):
        """Test error during reset returns False."""
        mock_dynamodb.delete_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'DeleteItem'
        )

        result = rate_limiter.reset_rate_limit('key-123')

        assert result is False


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_default(self):
        """Test RateLimitError with default retry_after."""
        error = RateLimitError()

        assert error.retry_after == 60
        assert "60 seconds" in str(error)

    def test_rate_limit_error_custom_retry(self):
        """Test RateLimitError with custom retry_after."""
        error = RateLimitError(retry_after=120)

        assert error.retry_after == 120
        assert "120 seconds" in str(error)

    def test_rate_limit_error_can_be_raised(self):
        """Test RateLimitError can be raised and caught."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError(retry_after=30)

        assert exc_info.value.retry_after == 30
