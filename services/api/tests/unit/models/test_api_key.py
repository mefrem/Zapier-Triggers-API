"""
Unit tests for APIKey model.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from src.models.api_key import (
    APIKey,
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyCreateResponse
)


class TestAPIKeyModel:
    """Tests for APIKey Pydantic model."""

    def test_valid_api_key(self):
        """Test creating a valid API key."""
        api_key = APIKey(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            name="Production API Key",
            created_at="2025-11-11T00:00:00Z",
            last_used_at="2025-11-11T12:00:00Z",
            expires_at=None,
            rate_limit=1000,
            is_active=True,
            scopes=["events:write", "events:read"]
        )

        assert api_key.key_id == "123e4567-e89b-12d3-a456-426614174000"
        assert api_key.user_id == "zapier_dev_12345"
        assert api_key.key_hash == "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        assert api_key.name == "Production API Key"
        assert api_key.rate_limit == 1000
        assert api_key.is_active is True
        assert api_key.scopes == ["events:write", "events:read"]

    def test_api_key_with_defaults(self):
        """Test API key with default values."""
        api_key = APIKey(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            name="Test Key",
            created_at="2025-11-11T00:00:00Z"
        )

        assert api_key.last_used_at is None
        assert api_key.expires_at is None
        assert api_key.rate_limit == 1000
        assert api_key.is_active is True
        assert api_key.scopes == ["events:write"]

    def test_invalid_key_hash_length(self):
        """Test validation fails for invalid key hash length."""
        with pytest.raises(ValidationError) as exc_info:
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="tooshort",
                name="Test Key",
                created_at="2025-11-11T00:00:00Z"
            )

        assert "key_hash must be a valid SHA-256 hash" in str(exc_info.value)

    def test_invalid_key_hash_characters(self):
        """Test validation fails for non-hex characters in hash."""
        with pytest.raises(ValidationError) as exc_info:
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="z" * 64,  # Invalid hex characters
                name="Test Key",
                created_at="2025-11-11T00:00:00Z"
            )

        assert "key_hash must be a valid SHA-256 hash" in str(exc_info.value)

    def test_invalid_timestamp_format(self):
        """Test validation fails for invalid timestamp format."""
        with pytest.raises(ValidationError) as exc_info:
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="Test Key",
                created_at="not-a-timestamp"
            )

        assert "Invalid ISO 8601 timestamp" in str(exc_info.value)

    def test_invalid_scope(self):
        """Test validation fails for invalid scope."""
        with pytest.raises(ValidationError) as exc_info:
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="Test Key",
                created_at="2025-11-11T00:00:00Z",
                scopes=["invalid:scope"]
            )

        assert "Invalid scope" in str(exc_info.value)

    def test_rate_limit_boundaries(self):
        """Test rate limit validation boundaries."""
        # Valid minimum
        api_key = APIKey(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            name="Test Key",
            created_at="2025-11-11T00:00:00Z",
            rate_limit=1
        )
        assert api_key.rate_limit == 1

        # Valid maximum
        api_key = APIKey(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            name="Test Key",
            created_at="2025-11-11T00:00:00Z",
            rate_limit=10000
        )
        assert api_key.rate_limit == 10000

        # Invalid: below minimum
        with pytest.raises(ValidationError):
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="Test Key",
                created_at="2025-11-11T00:00:00Z",
                rate_limit=0
            )

        # Invalid: above maximum
        with pytest.raises(ValidationError):
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="Test Key",
                created_at="2025-11-11T00:00:00Z",
                rate_limit=10001
            )

    def test_name_validation(self):
        """Test name length validation."""
        # Valid name
        api_key = APIKey(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            name="A",
            created_at="2025-11-11T00:00:00Z"
        )
        assert api_key.name == "A"

        # Invalid: empty name
        with pytest.raises(ValidationError):
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="",
                created_at="2025-11-11T00:00:00Z"
            )

        # Invalid: name too long
        with pytest.raises(ValidationError):
            APIKey(
                key_id="123e4567-e89b-12d3-a456-426614174000",
                user_id="zapier_dev_12345",
                key_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                name="A" * 256,
                created_at="2025-11-11T00:00:00Z"
            )


class TestAPIKeyCreateModel:
    """Tests for APIKeyCreate model."""

    def test_valid_api_key_create(self):
        """Test creating a valid API key create request."""
        request = APIKeyCreate(
            name="Production Key",
            rate_limit=2000,
            expires_at="2026-11-11T00:00:00Z",
            scopes=["events:write", "events:read"]
        )

        assert request.name == "Production Key"
        assert request.rate_limit == 2000
        assert request.expires_at == "2026-11-11T00:00:00Z"
        assert request.scopes == ["events:write", "events:read"]

    def test_api_key_create_defaults(self):
        """Test API key create with default values."""
        request = APIKeyCreate(name="Test Key")

        assert request.name == "Test Key"
        assert request.rate_limit == 1000
        assert request.expires_at is None
        assert request.scopes == ["events:write"]

    def test_api_key_create_invalid_scope(self):
        """Test validation fails for invalid scope."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreate(
                name="Test Key",
                scopes=["invalid:scope"]
            )

        assert "Invalid scope" in str(exc_info.value)


class TestAPIKeyUpdateModel:
    """Tests for APIKeyUpdate model."""

    def test_valid_api_key_update(self):
        """Test creating a valid API key update request."""
        request = APIKeyUpdate(
            name="Updated Key",
            rate_limit=500,
            is_active=False
        )

        assert request.name == "Updated Key"
        assert request.rate_limit == 500
        assert request.is_active is False

    def test_api_key_update_partial(self):
        """Test partial update."""
        request = APIKeyUpdate(name="Updated Key")

        assert request.name == "Updated Key"
        assert request.rate_limit is None
        assert request.is_active is None


class TestAPIKeyResponseModel:
    """Tests for APIKeyResponse model."""

    def test_valid_api_key_response(self):
        """Test creating a valid API key response."""
        response = APIKeyResponse(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            name="Production Key",
            created_at="2025-11-11T00:00:00Z",
            last_used_at="2025-11-11T12:00:00Z",
            expires_at=None,
            rate_limit=1000,
            is_active=True,
            scopes=["events:write", "events:read"]
        )

        assert response.key_id == "123e4567-e89b-12d3-a456-426614174000"
        assert response.user_id == "zapier_dev_12345"
        assert response.name == "Production Key"
        # Response should not expose key_hash or actual api_key


class TestAPIKeyCreateResponseModel:
    """Tests for APIKeyCreateResponse model."""

    def test_valid_api_key_create_response(self):
        """Test creating a valid API key create response."""
        response = APIKeyCreateResponse(
            key_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="zapier_dev_12345",
            name="Production Key",
            created_at="2025-11-11T00:00:00Z",
            last_used_at=None,
            expires_at=None,
            rate_limit=1000,
            is_active=True,
            scopes=["events:write", "events:read"],
            api_key="zap_1234567890abcdefghijklmnopqrstuv"
        )

        assert response.api_key == "zap_1234567890abcdefghijklmnopqrstuv"
        assert response.key_id == "123e4567-e89b-12d3-a456-426614174000"
