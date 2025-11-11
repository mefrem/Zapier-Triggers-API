"""
Pydantic models for inbox retrieval API.

Defines request and response schemas for the GET /inbox endpoint.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class InboxQueryParams(BaseModel):
    """
    Query parameters for GET /inbox endpoint.

    Attributes:
        limit: Number of events to return per page (1-100, default: 50)
        cursor: Opaque pagination cursor for fetching next page
        event_type: Optional filter by event type (can specify multiple)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit": 50,
                "cursor": "eyJ0aW1lc3RhbXAiOiAiMjAyNS0xMS0xMVQwOToxNTowMC4xMjM0NTZaIiwgImV2ZW50X2lkIjogImV2dC0xMjMifQ==",
                "event_type": ["user.created", "order.completed"]
            }
        }
    )

    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of events to return (1-100, default: 50)"
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Opaque pagination cursor for next page"
    )
    event_type: Optional[List[str]] = Field(
        default=None,
        description="Filter by event type(s)"
    )

    @field_validator('event_type')
    @classmethod
    def validate_event_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate event_type list contains non-empty strings."""
        if v is not None:
            if not isinstance(v, list):
                # Handle single value
                v = [v]

            # Filter out empty strings
            non_empty = [et.strip() for et in v if et and et.strip()]
            if len(non_empty) == 0:
                raise ValueError("event_type must contain at least one non-empty value")
            return non_empty
        return v


class EventItem(BaseModel):
    """
    Event item in inbox response.

    Attributes:
        event_id: Unique event identifier (UUID)
        event_type: Event type identifier
        timestamp: ISO 8601 timestamp when event was received (UTC)
        payload: Event payload data
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "user.created",
                "timestamp": "2025-11-11T09:00:00.123456Z",
                "payload": {
                    "user_id": "usr_12345",
                    "email": "newuser@example.com",
                    "name": "Jane Doe"
                }
            }
        }
    )

    event_id: str = Field(..., description="Unique event identifier (UUID v4)")
    event_type: str = Field(..., description="Event type identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp (UTC)")
    payload: Dict[str, Any] = Field(..., description="Event payload data")


class PaginationInfo(BaseModel):
    """
    Pagination metadata for inbox response.

    Attributes:
        limit: Number of events requested
        cursor: Opaque cursor for fetching next page (null if no more results)
        has_more: Whether more results are available
        total_count: Total number of undelivered events matching filter criteria
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit": 50,
                "cursor": "eyJ0aW1lc3RhbXAiOiAiMjAyNS0xMS0xMVQwOToxNTowMC4xMjM0NTZaIiwgImV2ZW50X2lkIjogImV2dC0xMjMifQ==",
                "has_more": True,
                "total_count": 150
            }
        }
    )

    limit: int = Field(..., description="Number of events requested")
    cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page (null if no more results)"
    )
    has_more: bool = Field(..., description="Whether more results are available")
    total_count: int = Field(..., description="Total undelivered events")


class InboxResponse(BaseModel):
    """
    Response model for GET /inbox endpoint.

    Attributes:
        events: List of undelivered events
        pagination: Pagination metadata
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "event_type": "user.created",
                        "timestamp": "2025-11-11T09:00:00.123456Z",
                        "payload": {
                            "user_id": "usr_12345",
                            "email": "newuser@example.com",
                            "name": "Jane Doe"
                        }
                    }
                ],
                "pagination": {
                    "limit": 50,
                    "cursor": "eyJ0aW1lc3RhbXAiOiAiMjAyNS0xMS0xMVQwOToxNTowMC4xMjM0NTZaIiwgImV2ZW50X2lkIjogImV2dC0xMjMifQ==",
                    "has_more": True,
                    "total_count": 150
                }
            }
        }
    )

    events: List[EventItem] = Field(..., description="List of undelivered events")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
