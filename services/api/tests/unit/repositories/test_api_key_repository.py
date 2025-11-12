"""
Unit tests for APIKeyRepository.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.repositories.api_key_repository import APIKeyRepository
from src.models.api_key import APIKey


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB client."""
    with patch('boto3.client') as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        yield mock_db


@pytest.fixture
def repository(mock_dynamodb):
    """Create APIKeyRepository with mocked DynamoDB."""
    with patch.dict('os.environ', {'API_KEYS_TABLE_NAME': 'test-api-keys'}):
        return APIKeyRepository()


class TestAPIKeyRepositoryInit:
    """Tests for APIKeyRepository initialization."""

    def test_init_with_table_name(self, mock_dynamodb):
        """Test initialization with explicit table name."""
        repo = APIKeyRepository(table_name='custom-table')
        assert repo.table_name == 'custom-table'

    def test_init_with_env_var(self, mock_dynamodb):
        """Test initialization with environment variable."""
        with patch.dict('os.environ', {'API_KEYS_TABLE_NAME': 'env-table'}):
            repo = APIKeyRepository()
            assert repo.table_name == 'env-table'

    def test_init_without_table_name_raises_error(self, mock_dynamodb):
        """Test initialization fails without table name."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="API_KEYS_TABLE_NAME"):
                APIKeyRepository()


class TestAPIKeyRepositoryCreate:
    """Tests for APIKeyRepository.create()."""

    def test_create_api_key_success(self, repository, mock_dynamodb):
        """Test creating a new API key."""
        mock_dynamodb.put_item.return_value = {}

        api_key_model, api_key = repository.create(
            user_id='user123',
            name='Test Key',
            rate_limit=2000,
            scopes=['events:write', 'events:read']
        )

        # Verify the model
        assert api_key_model.user_id == 'user123'
        assert api_key_model.name == 'Test Key'
        assert api_key_model.rate_limit == 2000
        assert api_key_model.is_active is True
        assert api_key_model.scopes == ['events:write', 'events:read']
        assert len(api_key_model.key_hash) == 64  # SHA-256 hash

        # Verify the API key format
        assert api_key.startswith('zap_')
        assert len(api_key) == 36  # 'zap_' + 32 hex characters

        # Verify DynamoDB was called
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'test-api-keys'
        assert call_args[1]['Item']['user_id']['S'] == 'user123'
        assert call_args[1]['Item']['name']['S'] == 'Test Key'
        assert call_args[1]['Item']['rate_limit']['N'] == '2000'

    def test_create_api_key_with_defaults(self, repository, mock_dynamodb):
        """Test creating API key with default values."""
        mock_dynamodb.put_item.return_value = {}

        api_key_model, api_key = repository.create(
            user_id='user123',
            name='Default Key'
        )

        assert api_key_model.rate_limit == 1000
        assert api_key_model.scopes == ['events:write']
        assert api_key_model.expires_at is None

    def test_create_api_key_with_expiration(self, repository, mock_dynamodb):
        """Test creating API key with expiration."""
        mock_dynamodb.put_item.return_value = {}
        expires_at = '2026-11-11T00:00:00Z'

        api_key_model, api_key = repository.create(
            user_id='user123',
            name='Expiring Key',
            expires_at=expires_at
        )

        assert api_key_model.expires_at == expires_at

        # Verify expires_at was included in DynamoDB item
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['Item']['expires_at']['S'] == expires_at

    def test_create_api_key_duplicate_raises_error(self, repository, mock_dynamodb):
        """Test creating duplicate API key raises error."""
        mock_dynamodb.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'PutItem'
        )

        with pytest.raises(ValueError, match="API key already exists"):
            repository.create(user_id='user123', name='Duplicate Key')

    def test_create_api_key_other_error_propagates(self, repository, mock_dynamodb):
        """Test other DynamoDB errors propagate."""
        mock_dynamodb.put_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'PutItem'
        )

        with pytest.raises(ClientError):
            repository.create(user_id='user123', name='Error Key')


class TestAPIKeyRepositoryGetByHash:
    """Tests for APIKeyRepository.get_by_hash()."""

    def test_get_by_hash_found(self, repository, mock_dynamodb):
        """Test getting API key by hash when it exists."""
        mock_dynamodb.query.return_value = {
            'Items': [{
                'key_id': {'S': '123e4567-e89b-12d3-a456-426614174000'},
                'user_id': {'S': 'user123'},
                'key_hash': {'S': 'a' * 64},
                'name': {'S': 'Test Key'},
                'created_at': {'S': '2025-11-11T00:00:00Z'},
                'rate_limit': {'N': '1000'},
                'is_active': {'BOOL': True},
                'scopes': {'SS': ['events:write']}
            }]
        }

        api_key = repository.get_by_hash('a' * 64)

        assert api_key is not None
        assert api_key.key_id == '123e4567-e89b-12d3-a456-426614174000'
        assert api_key.user_id == 'user123'
        assert api_key.key_hash == 'a' * 64
        assert api_key.name == 'Test Key'

        # Verify query was called correctly
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['IndexName'] == 'KeyHashIndex'

    def test_get_by_hash_not_found(self, repository, mock_dynamodb):
        """Test getting API key by hash when it doesn't exist."""
        mock_dynamodb.query.return_value = {'Items': []}

        api_key = repository.get_by_hash('nonexistent')

        assert api_key is None

    def test_get_by_hash_error_returns_none(self, repository, mock_dynamodb):
        """Test error during query returns None."""
        mock_dynamodb.query.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'Query'
        )

        api_key = repository.get_by_hash('errorkey')

        assert api_key is None


class TestAPIKeyRepositoryGetById:
    """Tests for APIKeyRepository.get_by_id()."""

    def test_get_by_id_found(self, repository, mock_dynamodb):
        """Test getting API key by ID when it exists."""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'key_id': {'S': 'key123'},
                'user_id': {'S': 'user123'},
                'key_hash': {'S': 'a' * 64},
                'name': {'S': 'Test Key'},
                'created_at': {'S': '2025-11-11T00:00:00Z'},
                'rate_limit': {'N': '1000'},
                'is_active': {'BOOL': True},
                'scopes': {'SS': ['events:write']}
            }
        }

        api_key = repository.get_by_id('user123', 'key123')

        assert api_key is not None
        assert api_key.key_id == 'key123'
        assert api_key.user_id == 'user123'

    def test_get_by_id_not_found(self, repository, mock_dynamodb):
        """Test getting API key by ID when it doesn't exist."""
        mock_dynamodb.get_item.return_value = {}

        api_key = repository.get_by_id('user123', 'nonexistent')

        assert api_key is None


class TestAPIKeyRepositoryUpdateLastUsed:
    """Tests for APIKeyRepository.update_last_used()."""

    def test_update_last_used_success(self, repository, mock_dynamodb):
        """Test updating last_used_at timestamp."""
        mock_dynamodb.update_item.return_value = {}

        result = repository.update_last_used('user123', 'key123')

        assert result is True
        mock_dynamodb.update_item.assert_called_once()

    def test_update_last_used_error(self, repository, mock_dynamodb):
        """Test error during update returns False."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'UpdateItem'
        )

        result = repository.update_last_used('user123', 'key123')

        assert result is False


class TestAPIKeyRepositoryListByUser:
    """Tests for APIKeyRepository.list_by_user()."""

    def test_list_by_user_success(self, repository, mock_dynamodb):
        """Test listing API keys for a user."""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'key_id': {'S': 'key1'},
                    'user_id': {'S': 'user123'},
                    'key_hash': {'S': 'a' * 64},
                    'name': {'S': 'Key 1'},
                    'created_at': {'S': '2025-11-11T00:00:00Z'},
                    'rate_limit': {'N': '1000'},
                    'is_active': {'BOOL': True},
                    'scopes': {'SS': ['events:write']}
                },
                {
                    'key_id': {'S': 'key2'},
                    'user_id': {'S': 'user123'},
                    'key_hash': {'S': 'b' * 64},
                    'name': {'S': 'Key 2'},
                    'created_at': {'S': '2025-11-11T00:00:00Z'},
                    'rate_limit': {'N': '2000'},
                    'is_active': {'BOOL': False},
                    'scopes': {'SS': ['events:read']}
                }
            ]
        }

        api_keys = repository.list_by_user('user123')

        assert len(api_keys) == 2
        assert api_keys[0].key_id == 'key1'
        assert api_keys[0].name == 'Key 1'
        assert api_keys[1].key_id == 'key2'
        assert api_keys[1].name == 'Key 2'

    def test_list_by_user_empty(self, repository, mock_dynamodb):
        """Test listing API keys returns empty list when none exist."""
        mock_dynamodb.query.return_value = {'Items': []}

        api_keys = repository.list_by_user('user123')

        assert api_keys == []

    def test_list_by_user_error_returns_empty(self, repository, mock_dynamodb):
        """Test error during query returns empty list."""
        mock_dynamodb.query.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'Query'
        )

        api_keys = repository.list_by_user('user123')

        assert api_keys == []


class TestAPIKeyRepositoryRevoke:
    """Tests for APIKeyRepository.revoke()."""

    def test_revoke_success(self, repository, mock_dynamodb):
        """Test revoking an API key."""
        mock_dynamodb.update_item.return_value = {}

        result = repository.revoke('user123', 'key123')

        assert result is True
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        assert call_args[1]['UpdateExpression'] == 'SET is_active = :inactive'

    def test_revoke_not_found(self, repository, mock_dynamodb):
        """Test revoking non-existent API key."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'UpdateItem'
        )

        result = repository.revoke('user123', 'nonexistent')

        assert result is False

    def test_revoke_error(self, repository, mock_dynamodb):
        """Test error during revoke returns False."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'UpdateItem'
        )

        result = repository.revoke('user123', 'key123')

        assert result is False


class TestAPIKeyRepositoryUpdate:
    """Tests for APIKeyRepository.update()."""

    def test_update_name(self, repository, mock_dynamodb):
        """Test updating API key name."""
        mock_dynamodb.update_item.return_value = {}

        result = repository.update('user123', 'key123', name='New Name')

        assert result is True
        call_args = mock_dynamodb.update_item.call_args
        assert 'name = :name' in call_args[1]['UpdateExpression']

    def test_update_rate_limit(self, repository, mock_dynamodb):
        """Test updating API key rate limit."""
        mock_dynamodb.update_item.return_value = {}

        result = repository.update('user123', 'key123', rate_limit=5000)

        assert result is True
        call_args = mock_dynamodb.update_item.call_args
        assert 'rate_limit = :rate_limit' in call_args[1]['UpdateExpression']

    def test_update_both(self, repository, mock_dynamodb):
        """Test updating both name and rate limit."""
        mock_dynamodb.update_item.return_value = {}

        result = repository.update('user123', 'key123', name='New Name', rate_limit=5000)

        assert result is True
        call_args = mock_dynamodb.update_item.call_args
        assert 'name = :name' in call_args[1]['UpdateExpression']
        assert 'rate_limit = :rate_limit' in call_args[1]['UpdateExpression']

    def test_update_nothing(self, repository, mock_dynamodb):
        """Test update with no changes."""
        result = repository.update('user123', 'key123')

        assert result is True
        mock_dynamodb.update_item.assert_not_called()

    def test_update_not_found(self, repository, mock_dynamodb):
        """Test updating non-existent API key."""
        mock_dynamodb.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'UpdateItem'
        )

        result = repository.update('user123', 'nonexistent', name='New Name')

        assert result is False


class TestAPIKeyRepositoryParseDynamoDBItem:
    """Tests for APIKeyRepository._parse_dynamodb_item()."""

    def test_parse_item_with_all_fields(self, repository):
        """Test parsing DynamoDB item with all fields."""
        item = {
            'key_id': {'S': 'key123'},
            'user_id': {'S': 'user123'},
            'key_hash': {'S': 'a' * 64},
            'name': {'S': 'Test Key'},
            'created_at': {'S': '2025-11-11T00:00:00Z'},
            'last_used_at': {'S': '2025-11-11T12:00:00Z'},
            'expires_at': {'S': '2026-11-11T00:00:00Z'},
            'rate_limit': {'N': '2000'},
            'is_active': {'BOOL': True},
            'scopes': {'SS': ['events:write', 'events:read']}
        }

        api_key = repository._parse_dynamodb_item(item)

        assert api_key.key_id == 'key123'
        assert api_key.user_id == 'user123'
        assert api_key.name == 'Test Key'
        assert api_key.last_used_at == '2025-11-11T12:00:00Z'
        assert api_key.expires_at == '2026-11-11T00:00:00Z'
        assert api_key.rate_limit == 2000
        assert api_key.is_active is True
        assert api_key.scopes == ['events:write', 'events:read']

    def test_parse_item_with_optional_fields_missing(self, repository):
        """Test parsing DynamoDB item with optional fields missing."""
        item = {
            'key_id': {'S': 'key123'},
            'user_id': {'S': 'user123'},
            'key_hash': {'S': 'a' * 64},
            'name': {'S': 'Test Key'},
            'created_at': {'S': '2025-11-11T00:00:00Z'},
            'rate_limit': {'N': '1000'},
            'is_active': {'BOOL': True},
            'scopes': {'SS': ['events:write']}
        }

        api_key = repository._parse_dynamodb_item(item)

        assert api_key.last_used_at is None
        assert api_key.expires_at is None

    def test_parse_item_with_list_scopes(self, repository):
        """Test parsing DynamoDB item with scopes as list (L type)."""
        item = {
            'key_id': {'S': 'key123'},
            'user_id': {'S': 'user123'},
            'key_hash': {'S': 'a' * 64},
            'name': {'S': 'Test Key'},
            'created_at': {'S': '2025-11-11T00:00:00Z'},
            'rate_limit': {'N': '1000'},
            'is_active': {'BOOL': True},
            'scopes': {'L': [{'S': 'events:write'}, {'S': 'events:read'}]}
        }

        api_key = repository._parse_dynamodb_item(item)

        assert api_key.scopes == ['events:write', 'events:read']
