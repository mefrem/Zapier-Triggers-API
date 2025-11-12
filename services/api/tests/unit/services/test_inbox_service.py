"""
Unit tests for InboxService.

Tests business logic for inbox retrieval with mocked repository.
"""

import pytest
from unittest.mock import Mock, MagicMock
from services.inbox_service import InboxService
from models.inbox import InboxResponse, PaginationInfo, EventItem


class TestInboxService:
    """Test cases for InboxService class."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock EventRepository."""
        return Mock()

    @pytest.fixture
    def service(self, mock_repository):
        """Create InboxService with mocked repository."""
        return InboxService(repository=mock_repository)

    def test_get_inbox_events_success(self, service, mock_repository):
        """Test successful inbox retrieval."""
        user_id = "user-123"

        # Mock repository response
        mock_events = [
            {
                "event_id": "evt-1",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:00:00.000000Z",
                "payload": {"test": "data1"}
            },
            {
                "event_id": "evt-2",
                "event_type": "order.completed",
                "timestamp": "2025-11-11T10:01:00.000000Z",
                "payload": {"test": "data2"}
            }
        ]

        mock_repository.query_by_status_with_cursor.return_value = (mock_events, False)
        mock_repository.count_events_by_status.return_value = 2

        # Call service
        response = service.get_inbox_events(user_id=user_id, limit=50)

        # Verify response
        assert isinstance(response, InboxResponse)
        assert len(response.events) == 2
        assert response.pagination.limit == 50
        assert response.pagination.has_more is False
        assert response.pagination.cursor is None
        assert response.pagination.total_count == 2

        # Verify repository was called correctly
        mock_repository.query_by_status_with_cursor.assert_called_once_with(
            user_id=user_id,
            status='received',
            limit=50,
            cursor_timestamp=None,
            cursor_event_id=None,
            event_types=None
        )

    def test_get_inbox_events_with_pagination(self, service, mock_repository):
        """Test inbox retrieval with pagination."""
        user_id = "user-123"

        # Mock repository response with more results
        mock_events = [
            {
                "event_id": "evt-1",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:00:00.000000Z",
                "payload": {"test": "data1"}
            }
        ]

        mock_repository.query_by_status_with_cursor.return_value = (mock_events, True)
        mock_repository.count_events_by_status.return_value = 100

        # Call service
        response = service.get_inbox_events(user_id=user_id, limit=1)

        # Verify pagination
        assert response.pagination.has_more is True
        assert response.pagination.cursor is not None
        assert response.pagination.total_count == 100

    def test_get_inbox_events_with_cursor(self, service, mock_repository):
        """Test inbox retrieval with cursor."""
        user_id = "user-123"

        # Create a valid cursor
        from utils.pagination import PaginationCursor
        cursor_util = PaginationCursor(secret_key="test-secret")
        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T10:00:00.000000Z",
            event_id="evt-1",
            user_id=user_id
        )

        # Mock repository response
        mock_events = [
            {
                "event_id": "evt-2",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:01:00.000000Z",
                "payload": {"test": "data2"}
            }
        ]

        mock_repository.query_by_status_with_cursor.return_value = (mock_events, False)
        mock_repository.count_events_by_status.return_value = 1

        # Override cursor_util in service with same secret
        service.cursor_util = cursor_util

        # Call service with cursor
        response = service.get_inbox_events(user_id=user_id, limit=50, cursor=cursor)

        # Verify repository was called with cursor parameters
        mock_repository.query_by_status_with_cursor.assert_called_once_with(
            user_id=user_id,
            status='received',
            limit=50,
            cursor_timestamp="2025-11-11T10:00:00.000000Z",
            cursor_event_id="evt-1",
            event_types=None
        )

    def test_get_inbox_events_with_event_type_filter(self, service, mock_repository):
        """Test inbox retrieval with event_type filter."""
        user_id = "user-123"

        # Mock repository response
        mock_events = [
            {
                "event_id": "evt-1",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:00:00.000000Z",
                "payload": {"test": "data1"}
            }
        ]

        mock_repository.query_by_status_with_cursor.return_value = (mock_events, False)
        mock_repository.count_events_by_status.return_value = 1

        # Call service with event_type filter
        response = service.get_inbox_events(
            user_id=user_id,
            limit=50,
            event_types=["user.created"]
        )

        # Verify repository was called with event_types
        mock_repository.query_by_status_with_cursor.assert_called_once_with(
            user_id=user_id,
            status='received',
            limit=50,
            cursor_timestamp=None,
            cursor_event_id=None,
            event_types=["user.created"]
        )

    def test_get_inbox_events_empty_inbox(self, service, mock_repository):
        """Test inbox retrieval when no events exist."""
        user_id = "user-123"

        # Mock empty repository response
        mock_repository.query_by_status_with_cursor.return_value = ([], False)
        mock_repository.count_events_by_status.return_value = 0

        # Call service
        response = service.get_inbox_events(user_id=user_id, limit=50)

        # Verify empty response
        assert len(response.events) == 0
        assert response.pagination.has_more is False
        assert response.pagination.cursor is None
        assert response.pagination.total_count == 0

    def test_get_inbox_events_invalid_limit_low(self, service, mock_repository):
        """Test that limit < 1 raises ValueError."""
        with pytest.raises(ValueError, match="limit must be between 1 and 100"):
            service.get_inbox_events(user_id="user-123", limit=0)

    def test_get_inbox_events_invalid_limit_high(self, service, mock_repository):
        """Test that limit > 100 raises ValueError."""
        with pytest.raises(ValueError, match="limit must be between 1 and 100"):
            service.get_inbox_events(user_id="user-123", limit=101)

    def test_get_inbox_events_invalid_cursor(self, service, mock_repository):
        """Test that invalid cursor raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cursor"):
            service.get_inbox_events(
                user_id="user-123",
                limit=50,
                cursor="invalid-cursor"
            )

    def test_get_inbox_events_cursor_user_mismatch(self, service, mock_repository):
        """Test that cursor from different user raises ValueError."""
        # Create cursor for different user
        from utils.pagination import PaginationCursor
        cursor_util = PaginationCursor(secret_key="test-secret")
        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T10:00:00.000000Z",
            event_id="evt-1",
            user_id="user-999"  # Different user
        )

        # Override cursor_util in service
        service.cursor_util = cursor_util

        # Attempt to use cursor with different user_id
        with pytest.raises(ValueError, match="does not belong to this user"):
            service.get_inbox_events(user_id="user-123", limit=50, cursor=cursor)

    def test_transform_events(self, service):
        """Test event transformation from repository format to EventItem."""
        events_data = [
            {
                "event_id": "evt-1",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:00:00.000000Z",
                "payload": {"test": "data1"},
                "user_id": "user-123",
                "status": "received",
                "ttl": 1234567890
            },
            {
                "event_id": "evt-2",
                "event_type": "order.completed",
                "timestamp": "2025-11-11T10:01:00.000000Z",
                "payload": {"test": "data2"},
                "user_id": "user-123",
                "status": "received",
                "ttl": 1234567890
            }
        ]

        events = service._transform_events(events_data)

        # Verify transformation
        assert len(events) == 2
        assert all(isinstance(event, EventItem) for event in events)

        # Verify first event
        assert events[0].event_id == "evt-1"
        assert events[0].event_type == "user.created"
        assert events[0].timestamp == "2025-11-11T10:00:00.000000Z"
        assert events[0].payload == {"test": "data1"}

        # Verify second event
        assert events[1].event_id == "evt-2"
        assert events[1].event_type == "order.completed"

    def test_get_inbox_events_repository_exception(self, service, mock_repository):
        """Test that repository exceptions are propagated."""
        from botocore.exceptions import ClientError

        # Mock repository to raise exception
        mock_repository.query_by_status_with_cursor.side_effect = ClientError(
            error_response={'Error': {'Code': 'InternalServerError', 'Message': 'Server error'}},
            operation_name='Query'
        )

        # Call service should raise exception
        with pytest.raises(ClientError):
            service.get_inbox_events(user_id="user-123", limit=50)

    def test_get_inbox_events_with_multiple_event_types(self, service, mock_repository):
        """Test inbox retrieval with multiple event_type filters."""
        user_id = "user-123"

        # Mock repository response
        mock_events = [
            {
                "event_id": "evt-1",
                "event_type": "user.created",
                "timestamp": "2025-11-11T10:00:00.000000Z",
                "payload": {"test": "data1"}
            },
            {
                "event_id": "evt-2",
                "event_type": "order.completed",
                "timestamp": "2025-11-11T10:01:00.000000Z",
                "payload": {"test": "data2"}
            }
        ]

        mock_repository.query_by_status_with_cursor.return_value = (mock_events, False)
        mock_repository.count_events_by_status.return_value = 2

        # Call service with multiple event_types
        response = service.get_inbox_events(
            user_id=user_id,
            limit=50,
            event_types=["user.created", "order.completed"]
        )

        # Verify repository was called with multiple event_types
        mock_repository.query_by_status_with_cursor.assert_called_once_with(
            user_id=user_id,
            status='received',
            limit=50,
            cursor_timestamp=None,
            cursor_event_id=None,
            event_types=["user.created", "order.completed"]
        )

        # Verify response
        assert len(response.events) == 2
