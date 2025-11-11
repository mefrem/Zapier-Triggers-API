"""
Unit tests for custom authorizer Lambda handler.
"""

import json
import pytest
import hashlib
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError


# Mock environment variables
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv('API_KEYS_TABLE_NAME', 'zapier-triggers-api-keys-test')


@pytest.fixture
def auth_handler():
    """Import auth handler after environment is mocked."""
    import sys
    from pathlib import Path
    # Add src/handlers to path
    handlers_path = Path(__file__).parent.parent.parent.parent / 'src' / 'handlers'
    sys.path.insert(0, str(handlers_path))
    import auth
    return auth


@pytest.fixture
def valid_api_key():
    """Return a valid test API key."""
    return "test-api-key-12345"


@pytest.fixture
def valid_api_key_hash(valid_api_key):
    """Return hash of valid API key."""
    return hashlib.sha256(valid_api_key.encode()).hexdigest()


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
def mock_dynamodb_response():
    """Create mock DynamoDB query response."""
    return {
        'Items': [{
            'user_id': {'S': 'user-123'},
            'key_id': {'S': 'key-456'},
            'key_hash': {'S': hashlib.sha256('test-api-key-12345'.encode()).hexdigest()},
            'is_active': {'BOOL': True},
            'created_at': {'S': '2025-01-01T00:00:00Z'}
        }]
    }


def test_valid_api_key_authorization(auth_handler, mock_event, mock_dynamodb_response):
    """Test successful authorization with valid API key."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = mock_dynamodb_response
        mock_dynamodb.update_item.return_value = {}

        context = MagicMock()
        policy = auth_handler.lambda_handler(mock_event, context)

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

        # Verify DynamoDB query was called correctly
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['TableName'] == 'zapier-triggers-api-keys-test'
        assert call_args[1]['IndexName'] == 'KeyHashIndex'


def test_missing_api_key_header(auth_handler):
    """Test authorization fails when API key header is missing."""
    event = {
        'headers': {},
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'
    }
    context = MagicMock()

    with pytest.raises(Exception) as exc_info:
        auth_handler.lambda_handler(event, context)

    assert str(exc_info.value) == 'Unauthorized'


def test_case_insensitive_api_key_header(auth_handler, mock_dynamodb_response):
    """Test authorization works with lowercase x-api-key header."""
    event = {
        'headers': {
            'x-api-key': 'test-api-key-12345'
        },
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events'
    }

    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = mock_dynamodb_response
        mock_dynamodb.update_item.return_value = {}

        context = MagicMock()
        policy = auth_handler.lambda_handler(event, context)

        assert policy['principalId'] == 'user-123'


def test_api_key_not_found_in_dynamodb(auth_handler, mock_event):
    """Test authorization fails when API key is not found in DynamoDB."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        # Empty Items array means key not found
        mock_dynamodb.query.return_value = {'Items': []}

        context = MagicMock()

        with pytest.raises(Exception) as exc_info:
            auth_handler.lambda_handler(mock_event, context)

        assert str(exc_info.value) == 'Unauthorized'


def test_inactive_api_key(auth_handler, mock_event):
    """Test authorization fails when API key is inactive."""
    inactive_response = {
        'Items': [{
            'user_id': {'S': 'user-123'},
            'key_id': {'S': 'key-456'},
            'key_hash': {'S': hashlib.sha256('test-api-key-12345'.encode()).hexdigest()},
            'is_active': {'BOOL': False},  # Inactive key
            'created_at': {'S': '2025-01-01T00:00:00Z'}
        }]
    }

    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = inactive_response

        context = MagicMock()

        with pytest.raises(Exception) as exc_info:
            auth_handler.lambda_handler(mock_event, context)

        assert str(exc_info.value) == 'Unauthorized'


def test_dynamodb_query_failure(auth_handler, mock_event):
    """Test authorization fails gracefully on DynamoDB errors."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        error_response = {'Error': {'Code': 'InternalServerError', 'Message': 'Service unavailable'}}
        mock_dynamodb.query.side_effect = ClientError(error_response, 'Query')

        context = MagicMock()

        with pytest.raises(Exception) as exc_info:
            auth_handler.lambda_handler(mock_event, context)

        assert str(exc_info.value) == 'Unauthorized'


def test_missing_environment_variable(auth_handler, mock_event, monkeypatch):
    """Test authorization fails when API_KEYS_TABLE_NAME is not set."""
    monkeypatch.delenv('API_KEYS_TABLE_NAME', raising=False)

    context = MagicMock()

    with pytest.raises(Exception) as exc_info:
        auth_handler.lambda_handler(mock_event, context)

    assert str(exc_info.value) == 'Unauthorized'


def test_last_used_at_update_success(auth_handler, mock_event, mock_dynamodb_response):
    """Test that last_used_at is updated on successful authorization."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = mock_dynamodb_response
        mock_dynamodb.update_item.return_value = {}

        context = MagicMock()
        policy = auth_handler.lambda_handler(mock_event, context)

        # Verify update_item was called
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args

        assert call_args[1]['TableName'] == 'zapier-triggers-api-keys-test'
        assert call_args[1]['Key']['user_id']['S'] == 'user-123'
        assert call_args[1]['Key']['key_id']['S'] == 'key-456'
        assert ':timestamp' in call_args[1]['ExpressionAttributeValues']

        # Authorization should still succeed
        assert policy['principalId'] == 'user-123'


def test_last_used_at_update_failure_does_not_break_authorization(auth_handler, mock_event, mock_dynamodb_response):
    """Test that authorization succeeds even if last_used_at update fails."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = mock_dynamodb_response
        # update_item fails but should be caught
        error_response = {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Update failed'}}
        mock_dynamodb.update_item.side_effect = ClientError(error_response, 'UpdateItem')

        context = MagicMock()
        # Should not raise exception
        policy = auth_handler.lambda_handler(mock_event, context)

        # Authorization should still succeed
        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'


def test_generate_policy(auth_handler):
    """Test policy generation with correct structure."""
    policy = auth_handler.generate_policy(
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


def test_generate_deny_policy(auth_handler):
    """Test policy generation with Deny effect."""
    policy = auth_handler.generate_policy(
        principal_id='user-123',
        effect='Deny',
        resource='arn:aws:execute-api:us-east-1:123456789012:abc123/prod/POST/events',
        context={'user_id': 'user-123'}
    )

    assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'


def test_api_key_hashing(auth_handler, mock_event, mock_dynamodb_response, valid_api_key_hash):
    """Test that API key is correctly hashed using SHA256."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.query.return_value = mock_dynamodb_response
        mock_dynamodb.update_item.return_value = {}

        context = MagicMock()
        auth_handler.lambda_handler(mock_event, context)

        # Verify the hash was used in query
        call_args = mock_dynamodb.query.call_args
        query_hash = call_args[1]['ExpressionAttributeValues'][':key_hash']['S']
        assert query_hash == valid_api_key_hash
