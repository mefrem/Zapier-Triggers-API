"""
Unit tests for API key management handler.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from src.handlers.keys import (
    lambda_handler,
    create_api_key,
    list_api_keys,
    get_api_key,
    delete_api_key,
    update_api_key
)
from src.models.api_key import APIKey


@pytest.fixture
def mock_repository():
    """Mock API key repository."""
    with patch('src.handlers.keys.APIKeyRepository') as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def base_event():
    """Base API Gateway event."""
    return {
        'httpMethod': 'GET',
        'path': '/keys',
        'pathParameters': None,
        'body': None,
        'requestContext': {
            'authorizer': {
                'user_id': 'user-123'
            }
        }
    }


@pytest.fixture
def mock_api_key():
    """Mock API key model."""
    return APIKey(
        key_id='key-456',
        user_id='user-123',
        key_hash='a' * 64,
        name='Test Key',
        created_at='2025-11-11T00:00:00Z',
        last_used_at=None,
        expires_at=None,
        rate_limit=1000,
        is_active=True,
        scopes=['events:write']
    )


class TestLambdaHandler:
    """Tests for main lambda_handler routing."""

    def test_missing_user_id(self, base_event):
        """Test request without user_id returns 401."""
        base_event['requestContext'] = {}

        response = lambda_handler(base_event, None)

        assert response['statusCode'] == 401

    def test_route_to_list_keys(self, base_event, mock_repository):
        """Test routing to list_api_keys."""
        base_event['httpMethod'] = 'GET'
        base_event['path'] = '/keys'
        mock_repository.list_by_user.return_value = []

        response = lambda_handler(base_event, None)

        assert response['statusCode'] == 200
        mock_repository.list_by_user.assert_called_once_with('user-123')

    def test_route_not_found(self, base_event):
        """Test invalid route returns 404."""
        base_event['httpMethod'] = 'PUT'
        base_event['path'] = '/invalid'

        response = lambda_handler(base_event, None)

        assert response['statusCode'] == 404


class TestCreateAPIKey:
    """Tests for create_api_key function."""

    def test_create_api_key_success(self, base_event, mock_repository):
        """Test successful API key creation."""
        base_event['body'] = json.dumps({
            'name': 'Production Key',
            'rate_limit': 2000,
            'scopes': ['events:write', 'events:read']
        })

        mock_api_key = APIKey(
            key_id='new-key-123',
            user_id='user-123',
            key_hash='b' * 64,
            name='Production Key',
            created_at='2025-11-11T00:00:00Z',
            last_used_at=None,
            expires_at=None,
            rate_limit=2000,
            is_active=True,
            scopes=['events:write', 'events:read']
        )

        mock_repository.create.return_value = (mock_api_key, 'zap_newkey123456789')

        response = create_api_key(base_event, 'user-123')

        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['api_key'] == 'zap_newkey123456789'
        assert body['key_id'] == 'new-key-123'
        assert body['name'] == 'Production Key'

    def test_create_api_key_validation_error(self, base_event, mock_repository):
        """Test validation error during key creation."""
        base_event['body'] = json.dumps({
            'name': '',  # Empty name should fail validation
            'rate_limit': 2000
        })

        response = create_api_key(base_event, 'user-123')

        assert response['statusCode'] == 422
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'

    def test_create_api_key_repository_error(self, base_event, mock_repository):
        """Test error from repository during creation."""
        base_event['body'] = json.dumps({
            'name': 'Test Key',
            'rate_limit': 1000
        })

        mock_repository.create.side_effect = Exception("Database error")

        response = create_api_key(base_event, 'user-123')

        assert response['statusCode'] == 500


class TestListAPIKeys:
    """Tests for list_api_keys function."""

    def test_list_api_keys_success(self, base_event, mock_repository, mock_api_key):
        """Test successful listing of API keys."""
        mock_repository.list_by_user.return_value = [mock_api_key]

        response = list_api_keys(base_event, 'user-123')

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['count'] == 1
        assert len(body['keys']) == 1
        assert body['keys'][0]['key_id'] == 'key-456'
        # Ensure api_key value is not exposed
        assert 'api_key' not in body['keys'][0]

    def test_list_api_keys_empty(self, base_event, mock_repository):
        """Test listing when user has no keys."""
        mock_repository.list_by_user.return_value = []

        response = list_api_keys(base_event, 'user-123')

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['count'] == 0
        assert body['keys'] == []

    def test_list_api_keys_error(self, base_event, mock_repository):
        """Test error during listing."""
        mock_repository.list_by_user.side_effect = Exception("Database error")

        response = list_api_keys(base_event, 'user-123')

        assert response['statusCode'] == 500


class TestGetAPIKey:
    """Tests for get_api_key function."""

    def test_get_api_key_success(self, base_event, mock_repository, mock_api_key):
        """Test successful retrieval of API key."""
        mock_repository.get_by_id.return_value = mock_api_key

        response = get_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['key_id'] == 'key-456'
        assert body['name'] == 'Test Key'

    def test_get_api_key_not_found(self, base_event, mock_repository):
        """Test getting non-existent API key."""
        mock_repository.get_by_id.return_value = None

        response = get_api_key(base_event, 'user-123', 'nonexistent')

        assert response['statusCode'] == 404

    def test_get_api_key_forbidden(self, base_event, mock_repository, mock_api_key):
        """Test accessing another user's API key."""
        mock_api_key.user_id = 'other-user'
        mock_repository.get_by_id.return_value = mock_api_key

        response = get_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 403


class TestDeleteAPIKey:
    """Tests for delete_api_key function."""

    def test_delete_api_key_success(self, base_event, mock_repository, mock_api_key):
        """Test successful API key deletion."""
        mock_repository.get_by_id.return_value = mock_api_key
        mock_repository.revoke.return_value = True

        response = delete_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'API key revoked successfully'
        assert body['key_id'] == 'key-456'

    def test_delete_api_key_not_found(self, base_event, mock_repository):
        """Test deleting non-existent API key."""
        mock_repository.get_by_id.return_value = None

        response = delete_api_key(base_event, 'user-123', 'nonexistent')

        assert response['statusCode'] == 404

    def test_delete_api_key_forbidden(self, base_event, mock_repository, mock_api_key):
        """Test deleting another user's API key."""
        mock_api_key.user_id = 'other-user'
        mock_repository.get_by_id.return_value = mock_api_key

        response = delete_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 403

    def test_delete_api_key_revoke_fails(self, base_event, mock_repository, mock_api_key):
        """Test when revoke operation fails."""
        mock_repository.get_by_id.return_value = mock_api_key
        mock_repository.revoke.return_value = False

        response = delete_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 500


class TestUpdateAPIKey:
    """Tests for update_api_key function."""

    def test_update_api_key_success(self, base_event, mock_repository, mock_api_key):
        """Test successful API key update."""
        base_event['body'] = json.dumps({
            'name': 'Updated Key',
            'rate_limit': 5000
        })

        mock_repository.get_by_id.return_value = mock_api_key
        mock_repository.update.return_value = True

        # After update, return updated key
        updated_key = APIKey(
            key_id='key-456',
            user_id='user-123',
            key_hash='a' * 64,
            name='Updated Key',
            created_at='2025-11-11T00:00:00Z',
            last_used_at=None,
            expires_at=None,
            rate_limit=5000,
            is_active=True,
            scopes=['events:write']
        )
        mock_repository.get_by_id.side_effect = [mock_api_key, updated_key]

        response = update_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['name'] == 'Updated Key'
        assert body['rate_limit'] == 5000

    def test_update_api_key_not_found(self, base_event, mock_repository):
        """Test updating non-existent API key."""
        base_event['body'] = json.dumps({'name': 'Updated Key'})
        mock_repository.get_by_id.return_value = None

        response = update_api_key(base_event, 'user-123', 'nonexistent')

        assert response['statusCode'] == 404

    def test_update_api_key_forbidden(self, base_event, mock_repository, mock_api_key):
        """Test updating another user's API key."""
        base_event['body'] = json.dumps({'name': 'Updated Key'})
        mock_api_key.user_id = 'other-user'
        mock_repository.get_by_id.return_value = mock_api_key

        response = update_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 403

    def test_update_api_key_validation_error(self, base_event, mock_repository):
        """Test validation error during update."""
        base_event['body'] = json.dumps({
            'rate_limit': 0  # Invalid rate limit
        })

        response = update_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 422

    def test_update_api_key_invalid_json(self, base_event, mock_repository):
        """Test invalid JSON in request body."""
        base_event['body'] = 'invalid json'

        response = update_api_key(base_event, 'user-123', 'key-456')

        assert response['statusCode'] == 400
