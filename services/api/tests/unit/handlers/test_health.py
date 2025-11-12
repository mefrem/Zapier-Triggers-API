"""
Unit tests for health check Lambda handler.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError


# Mock environment variables
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv('ENVIRONMENT', 'test')
    monkeypatch.setenv('EVENTS_TABLE_NAME', 'zapier-triggers-api-events-test')
    monkeypatch.setenv('API_KEYS_TABLE_NAME', 'zapier-triggers-api-keys-test')


@pytest.fixture
def health_handler():
    """Import health handler after environment is mocked."""
    import sys
    from pathlib import Path
    # Add src/handlers to path
    handlers_path = Path(__file__).parent.parent.parent.parent / 'src' / 'handlers'
    sys.path.insert(0, str(handlers_path))
    import health
    return health


def test_health_check_success(health_handler):
    """Test successful health check."""
    with patch('health.check_dynamodb_connectivity', return_value=True):
        event = {}
        context = MagicMock()

        response = health_handler.lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert 'application/json' in response['headers']['Content-Type']

        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['version'] == '1.0.0'
        assert body['environment'] == 'test'
        assert body['checks']['dynamodb'] is True
        assert body['checks']['environment_config'] is True
        assert 'timestamp' in body


def test_health_check_dynamodb_failure(health_handler):
    """Test health check when DynamoDB is unavailable."""
    with patch('health.check_dynamodb_connectivity', return_value=False):
        event = {}
        context = MagicMock()

        response = health_handler.lambda_handler(event, context)

        assert response['statusCode'] == 503

        body = json.loads(response['body'])
        assert body['status'] == 'unhealthy'
        assert body['checks']['dynamodb'] is False


def test_health_check_missing_env_vars(health_handler, monkeypatch):
    """Test health check with missing environment variables."""
    monkeypatch.delenv('EVENTS_TABLE_NAME', raising=False)
    monkeypatch.delenv('API_KEYS_TABLE_NAME', raising=False)

    with patch('health.check_dynamodb_connectivity', return_value=True):
        event = {}
        context = MagicMock()

        response = health_handler.lambda_handler(event, context)

        assert response['statusCode'] == 503

        body = json.loads(response['body'])
        assert body['status'] == 'unhealthy'
        assert body['checks']['environment_config'] is False


def test_health_check_exception_handling(health_handler):
    """Test health check handles exceptions gracefully."""
    with patch('health.check_dynamodb_connectivity', side_effect=Exception('Test error')):
        event = {}
        context = MagicMock()

        response = health_handler.lambda_handler(event, context)

        assert response['statusCode'] == 500

        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'Internal server error' in body['message']


def test_check_dynamodb_connectivity_success(health_handler):
    """Test DynamoDB connectivity check success."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        mock_dynamodb.describe_table.return_value = {'Table': {'TableName': 'test-table'}}

        result = health_handler.check_dynamodb_connectivity('test-table')

        assert result is True
        mock_dynamodb.describe_table.assert_called_once_with(TableName='test-table')


def test_check_dynamodb_connectivity_client_error(health_handler):
    """Test DynamoDB connectivity check with ClientError."""
    with patch('boto3.client') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_boto3.return_value = mock_dynamodb
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}}
        mock_dynamodb.describe_table.side_effect = ClientError(error_response, 'DescribeTable')

        result = health_handler.check_dynamodb_connectivity('test-table')

        assert result is False


def test_check_dynamodb_connectivity_no_table_name(health_handler):
    """Test DynamoDB connectivity check with no table name."""
    result = health_handler.check_dynamodb_connectivity('')

    assert result is False


def test_health_check_cors_headers(health_handler):
    """Test health check includes CORS headers."""
    with patch('health.check_dynamodb_connectivity', return_value=True):
        event = {}
        context = MagicMock()

        response = health_handler.lambda_handler(event, context)

        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
