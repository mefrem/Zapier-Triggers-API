"""
API Key Data Model

Pydantic models for API key management.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class APIKey(BaseModel):
    """
    API Key model for authentication.

    Attributes:
        key_id: Unique identifier (UUID)
        user_id: Zapier developer/integration ID
        key_hash: SHA-256 hash of the API key (never store plaintext)
        name: Human-readable name for the key
        created_at: ISO 8601 timestamp of key creation
        last_used_at: ISO 8601 timestamp of last use (optional)
        expires_at: ISO 8601 timestamp of expiration (optional)
        rate_limit: Maximum requests per minute (default: 1000)
        is_active: Whether the key is active
        scopes: List of permissions (e.g., ["events:write", "events:read"])
    """

    key_id: str = Field(..., description="Unique key identifier (UUID)")
    user_id: str = Field(..., description="Zapier developer/integration ID")
    key_hash: str = Field(..., description="SHA-256 hash of the API key")
    name: str = Field(..., description="Human-readable key name", min_length=1, max_length=255)
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")
    last_used_at: Optional[str] = Field(None, description="ISO 8601 timestamp of last use")
    expires_at: Optional[str] = Field(None, description="ISO 8601 timestamp of expiration")
    rate_limit: int = Field(1000, description="Requests per minute", ge=1, le=10000)
    is_active: bool = Field(True, description="Whether the key is active")
    scopes: List[str] = Field(default_factory=lambda: ["events:write"], description="Permission scopes")

    @field_validator('created_at', 'last_used_at', 'expires_at')
    @classmethod
    def validate_iso8601_timestamp(cls, v: Optional[str]) -> Optional[str]:
        """Validate that timestamp is ISO 8601 format."""
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")

    @field_validator('key_hash')
    @classmethod
    def validate_key_hash(cls, v: str) -> str:
        """Validate that key_hash is SHA-256 (64 hex characters)."""
        if len(v) != 64 or not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError("key_hash must be a valid SHA-256 hash (64 hex characters)")
        return v.lower()

    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate that scopes are valid."""
        valid_scopes = {"events:write", "events:read", "keys:manage"}
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f"Invalid scope: {scope}. Valid scopes: {valid_scopes}")
        return v

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "key_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "zapier_dev_12345",
                "key_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
                "name": "Production API Key",
                "created_at": "2025-11-11T00:00:00Z",
                "last_used_at": "2025-11-11T12:00:00Z",
                "expires_at": None,
                "rate_limit": 1000,
                "is_active": True,
                "scopes": ["events:write", "events:read"]
            }
        }


class APIKeyCreate(BaseModel):
    """
    Request model for creating a new API key.
    """

    name: str = Field(..., description="Human-readable key name", min_length=1, max_length=255)
    rate_limit: int = Field(1000, description="Requests per minute", ge=1, le=10000)
    expires_at: Optional[str] = Field(None, description="ISO 8601 timestamp of expiration")
    scopes: List[str] = Field(default_factory=lambda: ["events:write"], description="Permission scopes")

    @field_validator('expires_at')
    @classmethod
    def validate_iso8601_timestamp(cls, v: Optional[str]) -> Optional[str]:
        """Validate that timestamp is ISO 8601 format."""
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")

    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate that scopes are valid."""
        valid_scopes = {"events:write", "events:read", "keys:manage"}
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f"Invalid scope: {scope}. Valid scopes: {valid_scopes}")
        return v


class APIKeyUpdate(BaseModel):
    """
    Request model for updating an API key.
    """

    name: Optional[str] = Field(None, description="Human-readable key name", min_length=1, max_length=255)
    rate_limit: Optional[int] = Field(None, description="Requests per minute", ge=1, le=10000)
    is_active: Optional[bool] = Field(None, description="Whether the key is active")


class APIKeyResponse(BaseModel):
    """
    Response model for API key operations (without exposing the actual key).
    """

    key_id: str
    user_id: str
    name: str
    created_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    rate_limit: int
    is_active: bool
    scopes: List[str]

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "key_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "zapier_dev_12345",
                "name": "Production API Key",
                "created_at": "2025-11-11T00:00:00Z",
                "last_used_at": "2025-11-11T12:00:00Z",
                "expires_at": None,
                "rate_limit": 1000,
                "is_active": True,
                "scopes": ["events:write", "events:read"]
            }
        }


class APIKeyCreateResponse(APIKeyResponse):
    """
    Response model for API key creation (includes the actual key, shown only once).
    """

    api_key: str = Field(..., description="The actual API key (shown only once)")

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "key_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "zapier_dev_12345",
                "name": "Production API Key",
                "created_at": "2025-11-11T00:00:00Z",
                "last_used_at": None,
                "expires_at": None,
                "rate_limit": 1000,
                "is_active": True,
                "scopes": ["events:write", "events:read"],
                "api_key": "zap_1234567890abcdefghijklmnopqrstuv"
            }
        }
