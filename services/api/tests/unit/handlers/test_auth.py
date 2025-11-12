"""
Unit tests for custom authorizer Lambda handler (enhanced version).
"""

import json
import pytest
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.handlers.auth import (
    lambda_handler,
    extract_api_key_from_headers,
    is_key_expired,
    log_auth_event,
    generate_policy
)
from src.models.api_key import APIKey


@pytest.fixture
def valid_api_key():
    """Return a valid test API key."""
    return "zap_test1234567890abcdefghijklmno"


@pytest.fixture
def valid_api_key_hash(valid_api_key):
    """Return hash of valid API key."""
    return hashlib.sha256(valid_api_key.encode()).hexdigest()


@pytest.fixture
def mock_api_key_record():
    """Create mock APIKey record."""
    return APIKey(
        key_id='key-456',
        user_id='user-123',
        key_hash=hashlib.sha256('zap_test1234567890abcdefghijklmno'.encode()).hexdigest(),
        name='Test Key',
        created_at='2025-01-01T00:00:00Z',
        last_used_at='2025-11-10T00:00:00Z',
        expires_at=None,
        rate_limit=1000,
        is_active=True,
        scopes=['events:write', 'events:read']
    )


@pytest.fixture
def mock_event(valid_api_key):
    """Create mock API Gateway authorizer event."""
    return {
        'headers': {
            'X-API-Key': valid_api_key
        },
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'
    }


@pytest.fixture
def mock_context():
    """Create mock Lambda context."""
    return MagicMock()


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch('src.handlers.auth.APIKeyRepository')
    def test_valid_api_key_authorization(self, mock_repo_class, mock_event, mock_context, mock_api_key_record):
        """Test successful authorization with valid API key."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = mock_api_key_record
        mock_repo.update_last_used.return_value = True

        policy = lambda_handler(mock_event, mock_context)

        # Verify policy structure
        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1

        statement = policy['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Resource'] == mock_event['methodArn']

        # Verify context
        assert policy['context']['user_id'] == 'user-123'
        assert policy['context']['key_id'] == 'key-456'
        assert 'correlation_id' in policy['context']
        assert policy['context']['scopes'] == 'events:write,events:read'

        # Verify repository calls
        mock_repo.get_by_hash.assert_called_once()
        mock_repo.update_last_used.assert_called_once_with('user-123', 'key-456')

    @patch('src.handlers.auth.APIKeyRepository')
    def test_missing_api_key_header(self, mock_repo_class, mock_context):
        """Test authorization fails when API key header is missing."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo

        event = {
            'headers': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'
        }

        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, mock_context)

        assert str(exc_info.value) == 'Unauthorized'
        mock_repo.get_by_hash.assert_not_called()

    @patch('src.handlers.auth.APIKeyRepository')
    def test_case_insensitive_api_key_header(self, mock_repo_class, mock_context, mock_api_key_record):
        """Test authorization works with lowercase x-api-key header."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = mock_api_key_record
        mock_repo.update_last_used.return_value = True

        event = {
            'headers': {
                'x-api-key': 'zap_test1234567890abcdefghijklmno'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'
        }

        policy = lambda_handler(event, mock_context)
        assert policy['principalId'] == 'user-123'

    @patch('src.handlers.auth.APIKeyRepository')
    def test_api_key_not_found(self, mock_repo_class, mock_event, mock_context):
        """Test authorization fails when API key is not found."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = None  # Key not found

        with pytest.raises(Exception) as exc_info:
            lambda_handler(mock_event, mock_context)

        assert str(exc_info.value) == 'Unauthorized'

    @patch('src.handlers.auth.APIKeyRepository')
    def test_inactive_api_key(self, mock_repo_class, mock_event, mock_context, mock_api_key_record):
        """Test authorization fails when API key is inactive."""
        mock_api_key_record.is_active = False

        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = mock_api_key_record

        with pytest.raises(Exception) as exc_info:
            lambda_handler(mock_event, mock_context)

        assert str(exc_info.value) == 'Unauthorized'

    @patch('src.handlers.auth.APIKeyRepository')
    def test_expired_api_key(self, mock_repo_class, mock_event, mock_context, mock_api_key_record):
        """Test authorization fails when API key has expired."""
        # Set expiration to yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')
        mock_api_key_record.expires_at = yesterday

        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = mock_api_key_record

        with pytest.raises(Exception) as exc_info:
            lambda_handler(mock_event, mock_context)

        assert str(exc_info.value) == 'Unauthorized'

    @patch('src.handlers.auth.APIKeyRepository')
    def test_repository_initialization_error(self, mock_repo_class, mock_event, mock_context):
        """Test authorization fails when repository initialization fails."""
        mock_repo_class.side_effect = ValueError("API_KEYS_TABLE_NAME not set")

        with pytest.raises(Exception) as exc_info:
            lambda_handler(mock_event, mock_context)

        assert str(exc_info.value) == 'Unauthorized'

    @patch('src.handlers.auth.APIKeyRepository')
    def test_last_used_at_update_failure_does_not_break_auth(
        self, mock_repo_class, mock_event, mock_context, mock_api_key_record
    ):
        """Test that authorization succeeds even if last_used_at update fails."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_by_hash.return_value = mock_api_key_record
        mock_repo.update_last_used.return_value = False  # Update fails

        # Should not raise exception
        policy = lambda_handler(mock_event, mock_context)

        # Authorization should still succeed
        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'


class TestExtractApiKeyFromHeaders:
    """Tests for extract_api_key_from_headers function."""

    def test_extract_x_api_key(self):
        """Test extraction with X-API-Key header."""
        headers = {'X-API-Key': 'test-key-123'}
        api_key = extract_api_key_from_headers(headers)
        assert api_key == 'test-key-123'

    def test_extract_lowercase_x_api_key(self):
        """Test extraction with lowercase x-api-key header."""
        headers = {'x-api-key': 'test-key-456'}
        api_key = extract_api_key_from_headers(headers)
        assert api_key == 'test-key-456'

    def test_extract_mixed_case_x_api_key(self):
        """Test extraction with X-Api-Key header."""
        headers = {'X-Api-Key': 'test-key-789'}
        api_key = extract_api_key_from_headers(headers)
        assert api_key == 'test-key-789'

    def test_extract_missing_header(self):
        """Test extraction when header is missing."""
        headers = {'Authorization': 'Bearer token'}
        api_key = extract_api_key_from_headers(headers)
        assert api_key is None

    def test_extract_empty_headers(self):
        """Test extraction with empty headers."""
        api_key = extract_api_key_from_headers({})
        assert api_key is None


class TestIsKeyExpired:
    """Tests for is_key_expired function."""

    def test_no_expiration(self):
        """Test key with no expiration is not expired."""
        assert is_key_expired(None) is False

    def test_future_expiration(self):
        """Test key with future expiration is not expired."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        assert is_key_expired(future) is False

    def test_past_expiration(self):
        """Test key with past expiration is expired."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')
        assert is_key_expired(past) is True

    def test_invalid_timestamp_format(self):
        """Test invalid timestamp format is treated as not expired."""
        assert is_key_expired('not-a-timestamp') is False

    def test_edge_case_just_expired(self):
        """Test key that just expired."""
        # Create a timestamp 1 second in the past
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
        assert is_key_expired(past) is True


class TestLogAuthEvent:
    """Tests for log_auth_event function."""

    @patch('builtins.print')
    def test_log_auth_event(self, mock_print):
        """Test logging auth event."""
        log_auth_event('corr-123', 'AUTHORIZED', 'User authorized successfully')

        # Verify print was called with JSON
        mock_print.assert_called_once()
        log_output = mock_print.call_args[0][0]
        log_data = json.loads(log_output)

        assert log_data['correlation_id'] == 'corr-123'
        assert log_data['event_type'] == 'AUTHORIZED'
        assert log_data['message'] == 'User authorized successfully'
        assert 'timestamp' in log_data


class TestGeneratePolicy:
    """Tests for generate_policy function."""

    def test_generate_allow_policy(self):
        """Test policy generation with Allow effect."""
        policy = generate_policy(
            principal_id='user-123',
            effect='Allow',
            resource='arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events',
            context={'user_id': 'user-123', 'key_id': 'key-456'}
        )

        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1

        statement = policy['policyDocument']['Statement'][0]
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Effect'] == 'Allow'
        assert statement['Resource'] == 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'

        assert policy['context']['user_id'] == 'user-123'
        assert policy['context']['key_id'] == 'key-456'

    def test_generate_deny_policy(self):
        """Test policy generation with Deny effect."""
        policy = generate_policy(
            principal_id='user-123',
            effect='Deny',
            resource='arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events',
            context={'user_id': 'user-123'}
        )

        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_generate_policy_with_additional_context(self):
        """Test policy generation with additional context fields."""
        policy = generate_policy(
            principal_id='user-456',
            effect='Allow',
            resource='arn:aws:execute-api:us-east-1:123456789012:abc123/prod/GET/inbox',
            context={
                'user_id': 'user-456',
                'key_id': 'key-789',
                'correlation_id': 'corr-xyz',
                'scopes': 'events:read'
            }
        )

        assert policy['context']['correlation_id'] == 'corr-xyz'
        assert policy['context']['scopes'] == 'events:read'
