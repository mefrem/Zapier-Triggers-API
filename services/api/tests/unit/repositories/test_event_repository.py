"""
Unit tests for EventRepository.

Tests DynamoDB operations with moto mocking.
"""

import os
import pytest
import boto3
from datetime import datetime
from moto import mock_aws
from botocore.exceptions import ClientError
from repositories.event_repository import EventRepository


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Set environment variable
        os.environ['EVENTS_TABLE_NAME'] = 'test-events-table'

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
    """Create EventRepository instance with mocked DynamoDB."""
    return EventRepository(table_name='test-events-table')


class TestEventRepository:
    """Test EventRepository DynamoDB operations."""

    def test_initialization(self, repository):
        """Test repository initialization."""
        assert repository.table_name == 'test-events-table'
        assert repository.table is not None

    def test_initialization_without_table_name(self):
        """Test that initialization fails without table name."""
        # Clear environment variable
        original_value = os.environ.get('EVENTS_TABLE_NAME')
        if 'EVENTS_TABLE_NAME' in os.environ:
            del os.environ['EVENTS_TABLE_NAME']

        with pytest.raises(ValueError, match="EVENTS_TABLE_NAME must be set"):
            EventRepository()

        # Restore environment variable
        if original_value:
            os.environ['EVENTS_TABLE_NAME'] = original_value

    def test_create_event_success(self, repository):
        """Test successful event creation."""
        user_id = "user-123"
        event_id = "550e8400-e29b-41d4-a716-446655440000"
        event_type = "user.created"
        payload = {"user_id": "123", "email": "test@example.com"}
        timestamp = "2025-11-11T10:00:00.123456Z"
        metadata = {"source_ip": "192.168.1.1", "api_version": "v1"}

        result = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            metadata=metadata
        )

        # Verify returned item
        assert result['user_id'] == user_id
        assert result['event_id'] == event_id
        assert result['event_type'] == event_type
        assert result['payload'] == payload
        assert result['status'] == 'received'
        assert result['timestamp'] == timestamp
        assert result['retry_count'] == 0
        assert result['metadata'] == metadata
        assert 'ttl' in result
        assert result['ttl'] > 0

    def test_create_event_with_composite_sort_key(self, repository):
        """Test that composite sort key is created correctly."""
        user_id = "user-123"
        event_id = "evt-456"
        timestamp = "2025-11-11T10:00:00.123456Z"

        result = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.event",
            payload={"test": "data"},
            timestamp=timestamp
        )

        assert result['timestamp#event_id'] == f"{timestamp}#{event_id}"

    def test_create_event_with_gsi_keys(self, repository):
        """Test that GSI keys are created correctly."""
        user_id = "user-123"
        event_id = "evt-456"
        event_type = "order.completed"
        timestamp = "2025-11-11T10:00:00.123456Z"

        result = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type=event_type,
            payload={"order_id": "123"},
            timestamp=timestamp
        )

        assert result['event_type#timestamp'] == f"{event_type}#{timestamp}"
        assert result['status#timestamp'] == f"received#{timestamp}"

    def test_create_event_without_metadata(self, repository):
        """Test event creation without metadata."""
        result = repository.create_event(
            user_id="user-123",
            event_id="evt-789",
            event_type="test.event",
            payload={"test": "data"},
            timestamp="2025-11-11T10:00:00Z"
        )

        assert result['metadata'] == {}

    def test_get_event_success(self, repository):
        """Test successful event retrieval."""
        user_id = "user-123"
        event_id = "evt-retrieve"
        timestamp = "2025-11-11T10:00:00Z"

        # Create event first
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.event",
            payload={"test": "data"},
            timestamp=timestamp
        )

        # Retrieve event
        timestamp_event_id = f"{timestamp}#{event_id}"
        result = repository.get_event(user_id, timestamp_event_id)

        assert result is not None
        assert result['user_id'] == user_id
        assert result['event_id'] == event_id

    def test_get_event_not_found(self, repository):
        """Test retrieving non-existent event."""
        result = repository.get_event("user-999", "2025-11-11T10:00:00Z#evt-nonexistent")
        assert result is None

    def test_get_event_by_id_success(self, repository):
        """Test retrieving event by ID."""
        user_id = "user-123"
        event_id = "evt-by-id"
        timestamp = "2025-11-11T10:00:00Z"

        # Create event
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.event",
            payload={"test": "data"},
            timestamp=timestamp
        )

        # Retrieve by ID
        result = repository.get_event_by_id(user_id, event_id)

        assert result is not None
        assert result['event_id'] == event_id
        assert result['user_id'] == user_id

    def test_get_event_by_id_not_found(self, repository):
        """Test retrieving non-existent event by ID."""
        result = repository.get_event_by_id("user-999", "evt-nonexistent")
        assert result is None

    def test_update_event_status_success(self, repository):
        """Test updating event status."""
        user_id = "user-123"
        event_id = "evt-update"
        timestamp = "2025-11-11T10:00:00Z"

        # Create event
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.event",
            payload={"test": "data"},
            timestamp=timestamp
        )

        # Update status
        timestamp_event_id = f"{timestamp}#{event_id}"
        result = repository.update_event_status(
            user_id=user_id,
            timestamp_event_id=timestamp_event_id,
            status="delivered"
        )

        assert result['status'] == 'delivered'
        assert result['event_id'] == event_id

    def test_update_event_status_with_retry_count(self, repository):
        """Test updating event status and retry count."""
        user_id = "user-123"
        event_id = "evt-retry"
        timestamp = "2025-11-11T10:00:00Z"

        # Create event
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.event",
            payload={"test": "data"},
            timestamp=timestamp
        )

        # Update with retry count
        timestamp_event_id = f"{timestamp}#{event_id}"
        result = repository.update_event_status(
            user_id=user_id,
            timestamp_event_id=timestamp_event_id,
            status="retrying",
            retry_count=3
        )

        assert result['status'] == 'retrying'
        assert result['retry_count'] == 3

    def test_ttl_calculation(self, repository):
        """Test that TTL is set to 30 days from creation."""
        import time

        current_time = time.time()

        result = repository.create_event(
            user_id="user-123",
            event_id="evt-ttl",
            event_type="test.event",
            payload={"test": "data"},
            timestamp="2025-11-11T10:00:00Z"
        )

        ttl = result['ttl']
        expected_ttl = current_time + (30 * 24 * 60 * 60)

        # Allow 5 seconds tolerance
        assert abs(ttl - expected_ttl) < 5
