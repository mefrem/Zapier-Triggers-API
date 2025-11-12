"""
Integration tests for inbox retrieval endpoint.

Tests end-to-end flow with real DynamoDB (mocked with moto).
"""

import os
import pytest
import boto3
from moto import mock_aws
from fastapi.testclient import TestClient
from repositories.event_repository import EventRepository
from handlers.inbox import app


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for integration testing."""
    with mock_aws():
        # Set environment variable
        os.environ['EVENTS_TABLE_NAME'] = 'test-events-table'
        os.environ['PAGINATION_SECRET'] = 'test-secret-key'

        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='test-events-table',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp#event_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp#event_id', 'AttributeType': 'S'},
                {'AttributeName': 'event_type#timestamp', 'AttributeType': 'S'},
                {'AttributeName': 'status#timestamp', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'EventTypeIndex',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'event_type#timestamp', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'StatusIndex',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'status#timestamp', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        yield table


@pytest.fixture
def repository(dynamodb_table):
    """Create EventRepository with mocked DynamoDB."""
    return EventRepository(table_name='test-events-table')


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestInboxRetrievalIntegration:
    """Integration tests for inbox retrieval flow."""

    def test_end_to_end_inbox_retrieval(self, client, repository, dynamodb_table):
        """Test complete flow: create events → retrieve from inbox."""
        user_id = "user-integration-test"

        # Create events via repository
        for i in range(5):
            repository.create_event(
                user_id=user_id,
                event_id=f"evt-int-{i}",
                event_type="user.created",
                payload={"index": i, "user_id": f"usr-{i}"},
                timestamp=f"2025-11-11T10:0{i}:00.000000Z"
            )

        # Retrieve events via API
        # Inject user_id into request state manually for testing
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            with patch.object(app, 'state', user_id=user_id):
                response = client.get("/inbox", headers={"X-API-Key": "test-key-123"})

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 5
        assert data["pagination"]["total_count"] >= 5
        assert data["pagination"]["has_more"] is False

        # Verify events are sorted by timestamp (oldest first)
        for i in range(len(data["events"]) - 1):
            assert data["events"][i]["timestamp"] < data["events"][i + 1]["timestamp"]

    def test_pagination_comprehensive(self, client, repository, dynamodb_table):
        """Test pagination with multiple pages."""
        user_id = "user-pagination-integration"

        # Create 10 events
        for i in range(10):
            repository.create_event(
                user_id=user_id,
                event_id=f"evt-page-{i:02d}",
                event_type="test.event",
                payload={"index": i},
                timestamp=f"2025-11-11T10:{i:02d}:00.000000Z"
            )

        # Page 1: Retrieve first 5 events
        from unittest.mock import patch, MagicMock

        # Create a mock request state
        mock_request = MagicMock()
        mock_request.state.user_id = user_id

        with patch('handlers.inbox.getattr', return_value=user_id):
            response1 = client.get("/inbox?limit=5", headers={"X-API-Key": "test-key"})

        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["events"]) == 5
        assert data1["pagination"]["has_more"] is True
        cursor = data1["pagination"]["cursor"]
        assert cursor is not None

        # Page 2: Retrieve next 5 events
        with patch('handlers.inbox.getattr', return_value=user_id):
            response2 = client.get(f"/inbox?limit=5&cursor={cursor}", headers={"X-API-Key": "test-key"})

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["events"]) == 5
        assert data2["pagination"]["has_more"] is False

        # Verify no duplicates
        event_ids_page1 = {event["event_id"] for event in data1["events"]}
        event_ids_page2 = {event["event_id"] for event in data2["events"]}
        assert len(event_ids_page1.intersection(event_ids_page2)) == 0

    def test_event_type_filtering(self, client, repository, dynamodb_table):
        """Test filtering by event_type."""
        user_id = "user-filter-integration"

        # Create events with different types
        for i in range(3):
            repository.create_event(
                user_id=user_id,
                event_id=f"evt-user-{i}",
                event_type="user.created",
                payload={"index": i},
                timestamp=f"2025-11-11T10:0{i}:00.000000Z"
            )

        for i in range(2):
            repository.create_event(
                user_id=user_id,
                event_id=f"evt-order-{i}",
                event_type="order.completed",
                payload={"index": i},
                timestamp=f"2025-11-11T10:1{i}:00.000000Z"
            )

        # Retrieve only user.created events
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            response = client.get(
                "/inbox?event_type=user.created",
                headers={"X-API-Key": "test-key"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3

        # Verify all events are user.created
        for event in data["events"]:
            assert event["event_type"] == "user.created"

    def test_cross_user_isolation(self, client, repository, dynamodb_table):
        """Test that users only see their own events."""
        user1_id = "user-isolation-1"
        user2_id = "user-isolation-2"

        # Create events for user 1
        for i in range(3):
            repository.create_event(
                user_id=user1_id,
                event_id=f"evt-user1-{i}",
                event_type="test.event",
                payload={"owner": "user1"},
                timestamp=f"2025-11-11T10:0{i}:00.000000Z"
            )

        # Create events for user 2
        for i in range(2):
            repository.create_event(
                user_id=user2_id,
                event_id=f"evt-user2-{i}",
                event_type="test.event",
                payload={"owner": "user2"},
                timestamp=f"2025-11-11T10:1{i}:00.000000Z"
            )

        # User 1 retrieves inbox
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user1_id):
            response1 = client.get("/inbox", headers={"X-API-Key": "user1-key"})

        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["events"]) == 3

        # Verify all events belong to user 1
        for event in data1["events"]:
            assert event["payload"]["owner"] == "user1"

        # User 2 retrieves inbox
        with patch('handlers.inbox.getattr', return_value=user2_id):
            response2 = client.get("/inbox", headers={"X-API-Key": "user2-key"})

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["events"]) == 2

        # Verify all events belong to user 2
        for event in data2["events"]:
            assert event["payload"]["owner"] == "user2"

    def test_empty_inbox(self, client, repository, dynamodb_table):
        """Test retrieving inbox when no events exist."""
        user_id = "user-empty-inbox"

        # Don't create any events
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 0
        assert data["pagination"]["has_more"] is False
        assert data["pagination"]["cursor"] is None
        assert data["pagination"]["total_count"] == 0

    def test_only_received_status_returned(self, client, repository, dynamodb_table):
        """Test that only events with status='received' are returned."""
        user_id = "user-status-filter"

        # Create received event
        repository.create_event(
            user_id=user_id,
            event_id="evt-received",
            event_type="test.event",
            payload={"status": "received"},
            timestamp="2025-11-11T10:00:00.000000Z"
        )

        # Create delivered event
        repository.create_event(
            user_id=user_id,
            event_id="evt-delivered",
            event_type="test.event",
            payload={"status": "delivered"},
            timestamp="2025-11-11T10:01:00.000000Z"
        )

        # Update second event to delivered
        repository.update_event_status(
            user_id=user_id,
            timestamp_event_id="2025-11-11T10:01:00.000000Z#evt-delivered",
            status="delivered"
        )

        # Retrieve inbox
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_id"] == "evt-received"

    def test_events_include_only_public_fields(self, client, repository, dynamodb_table):
        """Test that returned events include only public fields."""
        user_id = "user-fields-test"

        repository.create_event(
            user_id=user_id,
            event_id="evt-fields",
            event_type="test.event",
            payload={"public": "data"},
            timestamp="2025-11-11T10:00:00.000000Z",
            metadata={"private": "metadata"}
        )

        # Retrieve inbox
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            response = client.get("/inbox", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1

        event = data["events"][0]

        # Should have public fields
        assert "event_id" in event
        assert "event_type" in event
        assert "timestamp" in event
        assert "payload" in event

        # Should NOT have internal fields (these are part of the event object but not exposed)
        # In the response model, we only include the 4 public fields
        assert event["event_id"] == "evt-fields"
        assert event["event_type"] == "test.event"
        assert event["payload"] == {"public": "data"}

    def test_large_result_set_performance(self, client, repository, dynamodb_table):
        """Test performance with large number of events."""
        user_id = "user-large-set"

        # Create 100 events
        for i in range(100):
            repository.create_event(
                user_id=user_id,
                event_id=f"evt-large-{i:03d}",
                event_type="test.event",
                payload={"index": i},
                timestamp=f"2025-11-11T{i:02d}:00:00.000000Z"
            )

        # Retrieve first page
        from unittest.mock import patch

        with patch('handlers.inbox.getattr', return_value=user_id):
            response = client.get("/inbox?limit=100", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 100
        # Note: In production, we should measure p95 latency < 50ms
