"""
Unit tests for event Pydantic models.

Tests validation logic for EventInput, EventResponse, and ErrorResponse models.
"""

import pytest
from pydantic import ValidationError
from models.event import EventInput, EventResponse, ErrorResponse, ErrorInfo, ErrorDetail


class TestEventInput:
    """Test EventInput model validation."""

    def test_valid_event_input(self):
        """Test creation with valid data."""
        event_input = EventInput(
            event_type="user.created",
            payload={"user_id": "123", "email": "test@example.com"}
        )
        assert event_input.event_type == "user.created"
        assert event_input.payload == {"user_id": "123", "email": "test@example.com"}

    def test_event_type_required(self):
        """Test that event_type is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(payload={"test": "data"})

        errors = exc_info.value.errors()
        assert any(e['loc'] == ('event_type',) and e['type'] == 'missing' for e in errors)

    def test_event_type_empty_string(self):
        """Test that event_type cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="", payload={"test": "data"})

        errors = exc_info.value.errors()
        assert any('event_type' in str(e['loc']) for e in errors)

    def test_event_type_whitespace_only(self):
        """Test that event_type with only whitespace is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="   ", payload={"test": "data"})

        errors = exc_info.value.errors()
        assert any('event_type' in str(e['loc']) for e in errors)

    def test_event_type_trimmed(self):
        """Test that event_type is trimmed of whitespace."""
        event_input = EventInput(
            event_type="  user.created  ",
            payload={"test": "data"}
        )
        assert event_input.event_type == "user.created"

    def test_payload_required(self):
        """Test that payload is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="test.event")

        errors = exc_info.value.errors()
        assert any(e['loc'] == ('payload',) and e['type'] == 'missing' for e in errors)

    def test_payload_cannot_be_null(self):
        """Test that payload cannot be None."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="test.event", payload=None)

        errors = exc_info.value.errors()
        assert any('payload' in str(e['loc']) for e in errors)

    def test_payload_cannot_be_empty(self):
        """Test that payload cannot be empty dict."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="test.event", payload={})

        errors = exc_info.value.errors()
        assert any('payload' in str(e['loc']) for e in errors)

    def test_payload_must_be_dict(self):
        """Test that payload must be a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="test.event", payload="not a dict")

        errors = exc_info.value.errors()
        assert any('payload' in str(e['loc']) for e in errors)

    def test_payload_with_nested_objects(self):
        """Test payload with nested objects."""
        event_input = EventInput(
            event_type="order.completed",
            payload={
                "order_id": "ord_123",
                "customer": {
                    "id": "cust_456",
                    "name": "John Doe"
                },
                "items": [
                    {"sku": "ITEM-1", "quantity": 2},
                    {"sku": "ITEM-2", "quantity": 1}
                ]
            }
        )
        assert event_input.payload["order_id"] == "ord_123"
        assert event_input.payload["customer"]["name"] == "John Doe"
        assert len(event_input.payload["items"]) == 2

    def test_payload_exceeds_max_size(self):
        """Test that payload exceeding 1MB is rejected."""
        # Create a large payload (> 1MB)
        large_payload = {"data": "x" * (1024 * 1024 + 1000)}  # > 1MB

        with pytest.raises(ValidationError) as exc_info:
            EventInput(event_type="test.event", payload=large_payload)

        errors = exc_info.value.errors()
        assert any('payload' in str(e['loc']) and '1MB' in str(e['msg']) for e in errors)

    def test_payload_within_max_size(self):
        """Test that payload under 1MB is accepted."""
        # Create a payload that's large but under 1MB
        large_payload = {"data": "x" * (1024 * 500)}  # ~500KB

        event_input = EventInput(event_type="test.event", payload=large_payload)
        assert event_input.event_type == "test.event"
        assert len(event_input.payload["data"]) == 1024 * 500


class TestEventResponse:
    """Test EventResponse model."""

    def test_valid_event_response(self):
        """Test creation with valid data."""
        response = EventResponse(
            event_id="550e8400-e29b-41d4-a716-446655440000",
            status="received",
            timestamp="2025-11-11T10:00:00.123456Z",
            message="Event successfully created"
        )
        assert response.event_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status == "received"
        assert response.timestamp == "2025-11-11T10:00:00.123456Z"
        assert response.message == "Event successfully created"

    def test_event_id_required(self):
        """Test that event_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventResponse(
                status="received",
                timestamp="2025-11-11T10:00:00Z",
                message="Test"
            )

        errors = exc_info.value.errors()
        assert any(e['loc'] == ('event_id',) and e['type'] == 'missing' for e in errors)

    def test_all_fields_required(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            EventResponse(event_id="123")

        errors = exc_info.value.errors()
        assert len(errors) >= 3  # Missing status, timestamp, message


class TestErrorDetail:
    """Test ErrorDetail model."""

    def test_valid_error_detail(self):
        """Test creation with valid data."""
        detail = ErrorDetail(field="event_type", message="Field required")
        assert detail.field == "event_type"
        assert detail.message == "Field required"

    def test_fields_required(self):
        """Test that both fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            ErrorDetail()

        errors = exc_info.value.errors()
        assert len(errors) == 2  # field and message are missing


class TestErrorInfo:
    """Test ErrorInfo model."""

    def test_valid_error_info_without_details(self):
        """Test creation without details."""
        error_info = ErrorInfo(
            code="INTERNAL_ERROR",
            message="An error occurred",
            timestamp="2025-11-11T10:00:00Z",
            request_id="req_123"
        )
        assert error_info.code == "INTERNAL_ERROR"
        assert error_info.message == "An error occurred"
        assert error_info.details is None

    def test_valid_error_info_with_details(self):
        """Test creation with details."""
        error_info = ErrorInfo(
            code="VALIDATION_ERROR",
            message="Invalid request",
            details=[
                ErrorDetail(field="event_type", message="Field required"),
                ErrorDetail(field="payload", message="Cannot be empty")
            ],
            timestamp="2025-11-11T10:00:00Z",
            request_id="req_123"
        )
        assert error_info.code == "VALIDATION_ERROR"
        assert len(error_info.details) == 2
        assert error_info.details[0].field == "event_type"


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_valid_error_response(self):
        """Test creation with valid data."""
        error_response = ErrorResponse(
            error=ErrorInfo(
                code="VALIDATION_ERROR",
                message="Invalid request payload",
                details=[ErrorDetail(field="event_type", message="Field required")],
                timestamp="2025-11-11T10:00:00Z",
                request_id="correlation-id-123"
            )
        )
        assert error_response.error.code == "VALIDATION_ERROR"
        assert error_response.error.message == "Invalid request payload"
        assert len(error_response.error.details) == 1

    def test_error_required(self):
        """Test that error field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse()

        errors = exc_info.value.errors()
        assert any(e['loc'] == ('error',) and e['type'] == 'missing' for e in errors)

    def test_serialization(self):
        """Test model serialization to dict."""
        error_response = ErrorResponse(
            error=ErrorInfo(
                code="VALIDATION_ERROR",
                message="Invalid request",
                details=[ErrorDetail(field="event_type", message="Required")],
                timestamp="2025-11-11T10:00:00Z",
                request_id="req_123"
            )
        )
        data = error_response.model_dump()
        assert data['error']['code'] == "VALIDATION_ERROR"
        assert data['error']['details'][0]['field'] == "event_type"
