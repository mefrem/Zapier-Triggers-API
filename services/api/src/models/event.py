"""
Pydantic models for event ingestion API.

Defines request and response schemas for the POST /events endpoint.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EventInput(BaseModel):
    """
    Request model for POST /events endpoint.

    Attributes:
        event_type: Non-empty string identifying the event type (e.g., "user.created")
        payload: JSON object containing event data (cannot be null or empty)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "user.created",
                "payload": {
                    "user_id": "usr_12345",
                    "email": "newuser@example.com",
                    "name": "Jane Doe",
                    "created_at": "2025-11-11T10:00:00Z"
                }
            }
        }
    )

    event_type: str = Field(
        ...,
        min_length=1,
        description="Event type identifier (e.g., 'user.created', 'order.completed')"
    )
    payload: Dict[str, Any] = Field(
        ...,
        description="Event payload as JSON object"
    )

    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event_type is a non-empty string."""
        if not v or not v.strip():
            raise ValueError("event_type must be a non-empty string")
        return v.strip()

    @field_validator('payload')
    @classmethod
    def validate_payload(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload is not empty, is a valid object, and within size limits."""
        if v is None:
            raise ValueError("payload cannot be null")
        if not isinstance(v, dict):
            raise ValueError("payload must be a JSON object")
        if len(v) == 0:
            raise ValueError("payload cannot be empty")

        # Validate payload size (1MB max to prevent DoS and DynamoDB write failures)
        payload_size = len(json.dumps(v))
        max_size = 1024 * 1024  # 1MB
        if payload_size > max_size:
            raise ValueError(
                f"payload exceeds maximum size of 1MB (current size: {payload_size} bytes)"
            )

        return v


class EventResponse(BaseModel):
    """
    Response model for successful event ingestion (201 Created).

    Attributes:
        event_id: Unique UUID v4 identifier for the event
        status: Event status ("received" or "queued")
        timestamp: ISO 8601 timestamp when event was received
        message: Confirmation message
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "received",
                "timestamp": "2025-11-11T10:00:00.123456Z",
                "message": "Event successfully created and queued for processing"
            }
        }
    )

    event_id: str = Field(..., description="Unique event identifier (UUID v4)")
    status: str = Field(..., description="Event status: 'received' or 'queued'")
    timestamp: str = Field(..., description="ISO 8601 timestamp (UTC)")
    message: str = Field(..., description="Confirmation message")


class ErrorDetail(BaseModel):
    """
    Detailed error information for a specific field.

    Attributes:
        field: Field name that caused the error
        message: Error message explaining what went wrong
    """
    field: str = Field(..., description="Field name with validation error")
    message: str = Field(..., description="Error message")


class ErrorInfo(BaseModel):
    """
    Error information container.

    Attributes:
        code: Error code (e.g., "VALIDATION_ERROR", "INTERNAL_ERROR")
        message: Human-readable error message
        details: List of detailed field-level errors (for validation errors)
        timestamp: ISO 8601 timestamp when error occurred
        request_id: Correlation ID for tracking and debugging
    """
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detailed field-level errors"
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp (UTC)")
    request_id: str = Field(..., description="Correlation ID")


class ErrorResponse(BaseModel):
    """
    Response model for error responses (400, 500, etc.).

    Attributes:
        error: Error information object
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload",
                    "details": [
                        {
                            "field": "event_type",
                            "message": "Field required"
                        }
                    ],
                    "timestamp": "2025-11-11T10:00:00Z",
                    "request_id": "correlation-id-123"
                }
            }
        }
    )

    error: ErrorInfo = Field(..., description="Error information")
