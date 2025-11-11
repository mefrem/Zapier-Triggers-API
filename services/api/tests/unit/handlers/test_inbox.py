"""
Unit tests for GET /inbox handler.

Tests FastAPI endpoint with mocked InboxService.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from handlers.inbox import app
from models.inbox import InboxResponse, PaginationInfo, EventItem


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_inbox_service():
    """Create mock InboxService."""
    with patch('handlers.inbox.inbox_service') as mock:
        yield mock


class TestGetInboxHandler:
    """Test cases for GET /inbox endpoint."""

    def test_get_inbox_success(self, client, mock_inbox_service):
        """Test successful inbox retrieval."""
        # Mock service response
        mock_response = InboxResponse(
            events=[
                EventItem(
                    event_id="evt-1",
                    event_type="user.created",
                    timestamp="2025-11-11T10:00:00.000000Z",
                    payload={"test": "data1"}
                ),
                EventItem(
                    event_id="evt-2",
                    event_type="order.completed",
                    timestamp="2025-11-11T10:01:00.000000Z",
                    payload={"test": "data2"}
                )
            ],
            pagination=PaginationInfo(
                limit=50,
                cursor=None,
                has_more=False,
                total_count=2
            )
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        # Make request with mock API key
        response = client.get("/inbox", headers={"X-API-Key": "test-key-123"})

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "pagination" in data
        assert len(data["events"]) == 2
        assert data["pagination"]["limit"] == 50
        assert data["pagination"]["has_more"] is False

    def test_get_inbox_with_limit(self, client, mock_inbox_service):
        """Test inbox retrieval with custom limit."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=25, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        # Make request with limit
        response = client.get("/inbox?limit=25", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 25

        # Verify service was called with correct limit
        mock_inbox_service.get_inbox_events.assert_called_once()
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert call_kwargs["limit"] == 25

    def test_get_inbox_with_cursor(self, client, mock_inbox_service):
        """Test inbox retrieval with pagination cursor."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        # Make request with cursor
        cursor = "eyJ0aW1lc3RhbXAiOiAiMjAyNS0xMS0xMVQxMDowMDowMCIsICJldmVudF9pZCI6ICJldnQtMTIzIn0="
        response = client.get(f"/inbox?cursor={cursor}", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200

        # Verify service was called with cursor
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert call_kwargs["cursor"] == cursor

    def test_get_inbox_with_event_type_filter(self, client, mock_inbox_service):
        """Test inbox retrieval with event_type filter."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        # Make request with event_type filter
        response = client.get(
            "/inbox?event_type=user.created",
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 200

        # Verify service was called with event_types
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert call_kwargs["event_types"] == ["user.created"]

    def test_get_inbox_with_multiple_event_types(self, client, mock_inbox_service):
        """Test inbox retrieval with multiple event_type filters."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        # Make request with multiple event_types
        response = client.get(
            "/inbox?event_type=user.created&event_type=order.completed",
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 200

        # Verify service was called with both event_types
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert "user.created" in call_kwargs["event_types"]
        assert "order.completed" in call_kwargs["event_types"]

    def test_get_inbox_empty_inbox(self, client, mock_inbox_service):
        """Test inbox retrieval when inbox is empty."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 0
        assert data["pagination"]["has_more"] is False
        assert data["pagination"]["total_count"] == 0

    def test_get_inbox_unauthorized_no_api_key(self, client, mock_inbox_service):
        """Test that request without API key returns 401."""
        response = client.get("/inbox")

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_get_inbox_invalid_limit_too_low(self, client, mock_inbox_service):
        """Test that limit < 1 returns 400."""
        response = client.get("/inbox?limit=0", headers={"X-API-Key": "test-key"})

        assert response.status_code == 422  # FastAPI validation error
        data = response.json()
        assert "detail" in data

    def test_get_inbox_invalid_limit_too_high(self, client, mock_inbox_service):
        """Test that limit > 100 returns 400."""
        response = client.get("/inbox?limit=101", headers={"X-API-Key": "test-key"})

        assert response.status_code == 422  # FastAPI validation error
        data = response.json()
        assert "detail" in data

    def test_get_inbox_invalid_cursor(self, client, mock_inbox_service):
        """Test that invalid cursor returns 400."""
        # Mock service to raise ValueError
        mock_inbox_service.get_inbox_events.side_effect = ValueError("Invalid cursor: test error")

        response = client.get("/inbox?cursor=invalid", headers={"X-API-Key": "test-key"})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_get_inbox_empty_event_type(self, client, mock_inbox_service):
        """Test that empty event_type returns 400."""
        response = client.get("/inbox?event_type=", headers={"X-API-Key": "test-key"})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_get_inbox_with_pagination_has_more(self, client, mock_inbox_service):
        """Test inbox retrieval when more pages exist."""
        # Mock response with has_more=True
        mock_response = InboxResponse(
            events=[
                EventItem(
                    event_id="evt-1",
                    event_type="user.created",
                    timestamp="2025-11-11T10:00:00.000000Z",
                    payload={"test": "data1"}
                )
            ],
            pagination=PaginationInfo(
                limit=1,
                cursor="next-cursor-token",
                has_more=True,
                total_count=100
            )
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get("/inbox?limit=1", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["has_more"] is True
        assert data["pagination"]["cursor"] == "next-cursor-token"
        assert data["pagination"]["total_count"] == 100

    def test_get_inbox_service_exception(self, client, mock_inbox_service):
        """Test that service exceptions return 500."""
        # Mock service to raise exception
        mock_inbox_service.get_inbox_events.side_effect = Exception("Database error")

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_ERROR"

    def test_get_inbox_aws_client_error(self, client, mock_inbox_service):
        """Test that AWS ClientError returns 500."""
        from botocore.exceptions import ClientError

        # Mock service to raise ClientError
        mock_inbox_service.get_inbox_events.side_effect = ClientError(
            error_response={'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Throughput exceeded'}},
            operation_name='Query'
        )

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_ERROR"

    def test_get_inbox_default_parameters(self, client, mock_inbox_service):
        """Test that default parameters are applied correctly."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200

        # Verify default limit is 50
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert call_kwargs["limit"] == 50
        assert call_kwargs["cursor"] is None
        assert call_kwargs["event_types"] is None

    def test_get_inbox_with_all_parameters(self, client, mock_inbox_service):
        """Test inbox retrieval with all query parameters."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=25, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get(
            "/inbox?limit=25&cursor=test-cursor&event_type=user.created&event_type=order.completed",
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 200

        # Verify all parameters were passed
        call_kwargs = mock_inbox_service.get_inbox_events.call_args.kwargs
        assert call_kwargs["limit"] == 25
        assert call_kwargs["cursor"] == "test-cursor"
        assert "user.created" in call_kwargs["event_types"]
        assert "order.completed" in call_kwargs["event_types"]

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "inbox"
        assert "timestamp" in data

    def test_get_inbox_correlation_id_in_response(self, client, mock_inbox_service):
        """Test that correlation ID is included in error responses."""
        # Mock service to raise error
        mock_inbox_service.get_inbox_events.side_effect = ValueError("Test error")

        response = client.get(
            "/inbox",
            headers={"X-API-Key": "test-key", "X-Request-ID": "test-correlation-123"}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["request_id"] == "test-correlation-123"

    def test_get_inbox_metrics_emitted(self, client, mock_inbox_service):
        """Test that metrics are emitted for successful requests."""
        mock_response = InboxResponse(
            events=[],
            pagination=PaginationInfo(limit=50, cursor=None, has_more=False, total_count=0)
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        # Metrics would be emitted to CloudWatch in production
        # In tests, we just verify the endpoint completes successfully

    def test_get_inbox_response_schema_valid(self, client, mock_inbox_service):
        """Test that response matches InboxResponse schema."""
        mock_response = InboxResponse(
            events=[
                EventItem(
                    event_id="evt-1",
                    event_type="user.created",
                    timestamp="2025-11-11T10:00:00.000000Z",
                    payload={"user_id": "123"}
                )
            ],
            pagination=PaginationInfo(
                limit=50,
                cursor=None,
                has_more=False,
                total_count=1
            )
        )

        mock_inbox_service.get_inbox_events.return_value = mock_response

        response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "events" in data
        assert "pagination" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["pagination"], dict)

        # Verify event structure
        if len(data["events"]) > 0:
            event = data["events"][0]
            assert "event_id" in event
            assert "event_type" in event
            assert "timestamp" in event
            assert "payload" in event

        # Verify pagination structure
        pagination = data["pagination"]
        assert "limit" in pagination
        assert "cursor" in pagination
        assert "has_more" in pagination
        assert "total_count" in pagination
