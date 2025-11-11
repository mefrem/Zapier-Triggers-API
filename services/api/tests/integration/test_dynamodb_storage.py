"""
Integration tests for DynamoDB Event Storage.

These tests validate:
- DynamoDB table schema and configuration
- Global Secondary Indexes (EventTypeIndex, StatusIndex)
- TTL configuration and behavior
- Query performance
- Data persistence and retrieval

Note: These tests require actual AWS credentials and DynamoDB tables.
Use with caution in CI/CD pipelines.
"""

import os
import time
import pytest
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
from repositories.event_repository import EventRepository


@pytest.fixture
def dynamodb_client():
    """Get DynamoDB client."""
    return boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


@pytest.fixture
def events_table_name():
    """Get events table name from environment."""
    table_name = os.environ.get('EVENTS_TABLE_NAME', 'zapier-triggers-api-dev-events')
    return table_name


@pytest.fixture
def repository(events_table_name):
    """Create EventRepository instance."""
    return EventRepository(table_name=events_table_name)


@pytest.mark.integration
class TestDynamoDBSchema:
    """Test DynamoDB table schema validation."""

    def test_table_exists(self, dynamodb_client, events_table_name):
        """Verify the Events table exists."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        assert response['Table']['TableName'] == events_table_name
        assert response['Table']['TableStatus'] == 'ACTIVE'

    def test_primary_key_schema(self, dynamodb_client, events_table_name):
        """Verify primary key schema (user_id, timestamp#event_id)."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        key_schema = response['Table']['KeySchema']

        assert len(key_schema) == 2

        # Verify partition key
        partition_key = next(k for k in key_schema if k['KeyType'] == 'HASH')
        assert partition_key['AttributeName'] == 'user_id'

        # Verify sort key
        sort_key = next(k for k in key_schema if k['KeyType'] == 'RANGE')
        assert sort_key['AttributeName'] == 'timestamp#event_id'

    def test_attribute_definitions(self, dynamodb_client, events_table_name):
        """Verify all required attribute definitions exist."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        attributes = response['Table']['AttributeDefinitions']

        attribute_names = {attr['AttributeName'] for attr in attributes}

        # Primary key attributes
        assert 'user_id' in attribute_names
        assert 'timestamp#event_id' in attribute_names

        # GSI attributes
        assert 'event_type#timestamp' in attribute_names
        assert 'status#timestamp' in attribute_names

    def test_global_secondary_indexes(self, dynamodb_client, events_table_name):
        """Verify both GSIs exist with correct configuration."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        gsis = response['Table'].get('GlobalSecondaryIndexes', [])

        assert len(gsis) == 2

        # Extract index names
        index_names = {gsi['IndexName'] for gsi in gsis}
        assert 'EventTypeIndex' in index_names
        assert 'StatusIndex' in index_names

        # Verify EventTypeIndex
        event_type_index = next(gsi for gsi in gsis if gsi['IndexName'] == 'EventTypeIndex')
        assert event_type_index['KeySchema'][0]['AttributeName'] == 'user_id'
        assert event_type_index['KeySchema'][1]['AttributeName'] == 'event_type#timestamp'
        assert event_type_index['Projection']['ProjectionType'] == 'ALL'
        assert event_type_index['IndexStatus'] == 'ACTIVE'

        # Verify StatusIndex
        status_index = next(gsi for gsi in gsis if gsi['IndexName'] == 'StatusIndex')
        assert status_index['KeySchema'][0]['AttributeName'] == 'user_id'
        assert status_index['KeySchema'][1]['AttributeName'] == 'status#timestamp'
        assert status_index['Projection']['ProjectionType'] == 'ALL'
        assert status_index['IndexStatus'] == 'ACTIVE'

    def test_billing_mode(self, dynamodb_client, events_table_name):
        """Verify billing mode is PAY_PER_REQUEST (on-demand)."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        billing_mode = response['Table'].get('BillingModeSummary', {}).get('BillingMode')

        # PAY_PER_REQUEST = on-demand
        assert billing_mode == 'PAY_PER_REQUEST'

    def test_ttl_configuration(self, dynamodb_client, events_table_name):
        """Verify TTL is enabled on the ttl attribute."""
        response = dynamodb_client.describe_time_to_live(TableName=events_table_name)
        ttl_spec = response['TimeToLiveDescription']

        assert ttl_spec['TimeToLiveStatus'] == 'ENABLED'
        assert ttl_spec['AttributeName'] == 'ttl'

    def test_point_in_time_recovery(self, dynamodb_client, events_table_name):
        """Verify Point-in-Time Recovery (PITR) is enabled."""
        response = dynamodb_client.describe_continuous_backups(TableName=events_table_name)
        pitr_status = response['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']

        assert pitr_status == 'ENABLED'

    def test_dynamodb_streams_enabled(self, dynamodb_client, events_table_name):
        """Verify DynamoDB Streams is enabled with NEW_IMAGE view type."""
        response = dynamodb_client.describe_table(TableName=events_table_name)
        stream_spec = response['Table'].get('StreamSpecification')

        assert stream_spec is not None
        assert stream_spec['StreamEnabled'] is True
        assert stream_spec['StreamViewType'] == 'NEW_IMAGE'

        # Verify stream ARN exists
        assert 'LatestStreamArn' in response['Table']
        assert response['Table']['LatestStreamArn'].startswith('arn:aws:dynamodb:')


@pytest.mark.integration
class TestEventPersistence:
    """Test event creation and persistence."""

    def test_create_and_retrieve_event(self, repository):
        """Test creating an event and retrieving it."""
        user_id = f"test-user-{int(time.time())}"
        event_id = f"evt-{int(time.time())}"
        event_type = "integration.test"
        payload = {"test": "data", "number": 42}
        timestamp = datetime.utcnow().isoformat() + "Z"
        metadata = {"source_ip": "127.0.0.1", "api_version": "v1"}

        # Create event
        created = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            metadata=metadata
        )

        assert created['user_id'] == user_id
        assert created['event_id'] == event_id
        assert created['event_type'] == event_type
        assert created['status'] == 'received'
        assert 'ttl' in created

        # Retrieve event
        timestamp_event_id = f"{timestamp}#{event_id}"
        retrieved = repository.get_event(user_id, timestamp_event_id)

        assert retrieved is not None
        assert retrieved['event_id'] == event_id
        assert retrieved['payload'] == payload

    def test_ttl_field_set_correctly(self, repository):
        """Test that TTL field is set to 30 days from now."""
        user_id = f"test-user-ttl-{int(time.time())}"
        event_id = f"evt-ttl-{int(time.time())}"

        current_time = int(time.time())
        expected_ttl = current_time + (30 * 24 * 60 * 60)

        created = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="ttl.test",
            payload={},
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        ttl = created['ttl']

        # TTL should be approximately 30 days from now (allow 10 seconds tolerance)
        assert abs(ttl - expected_ttl) < 10

    def test_gsi_composite_keys_created(self, repository):
        """Test that GSI composite keys are properly created."""
        user_id = f"test-user-gsi-{int(time.time())}"
        event_id = f"evt-gsi-{int(time.time())}"
        event_type = "order.completed"
        timestamp = datetime.utcnow().isoformat() + "Z"

        created = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type=event_type,
            payload={"order_id": "12345"},
            timestamp=timestamp
        )

        # Verify GSI keys
        assert created['event_type#timestamp'] == f"{event_type}#{timestamp}"
        assert created['status#timestamp'] == f"received#{timestamp}"


@pytest.mark.integration
class TestGlobalSecondaryIndexQueries:
    """Test GSI query operations."""

    def test_query_by_event_type(self, repository, dynamodb_client, events_table_name):
        """Test querying events by event_type using EventTypeIndex."""
        user_id = f"test-user-query-{int(time.time())}"
        event_type = "user.created"

        # Create multiple events with same event_type
        for i in range(3):
            event_id = f"evt-query-{i}-{int(time.time())}"
            timestamp = datetime.utcnow().isoformat() + "Z"
            repository.create_event(
                user_id=user_id,
                event_id=event_id,
                event_type=event_type,
                payload={"index": i},
                timestamp=timestamp
            )
            time.sleep(0.1)  # Ensure unique timestamps

        # Query using EventTypeIndex
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(events_table_name)

        response = table.query(
            IndexName='EventTypeIndex',
            KeyConditionExpression='user_id = :uid AND begins_with(#et, :et_val)',
            ExpressionAttributeNames={'#et': 'event_type#timestamp'},
            ExpressionAttributeValues={
                ':uid': user_id,
                ':et_val': event_type
            }
        )

        items = response['Items']
        assert len(items) >= 3

        # Verify all items match the event_type
        for item in items:
            assert item['event_type'] == event_type
            assert item['user_id'] == user_id

    def test_query_by_status(self, repository, dynamodb_client, events_table_name):
        """Test querying events by status using StatusIndex."""
        user_id = f"test-user-status-{int(time.time())}"
        status = "received"

        # Create events
        for i in range(2):
            event_id = f"evt-status-{i}-{int(time.time())}"
            timestamp = datetime.utcnow().isoformat() + "Z"
            repository.create_event(
                user_id=user_id,
                event_id=event_id,
                event_type="test.event",
                payload={"index": i},
                timestamp=timestamp
            )
            time.sleep(0.1)

        # Query using StatusIndex
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(events_table_name)

        response = table.query(
            IndexName='StatusIndex',
            KeyConditionExpression='user_id = :uid AND begins_with(#st, :st_val)',
            ExpressionAttributeNames={'#st': 'status#timestamp'},
            ExpressionAttributeValues={
                ':uid': user_id,
                ':st_val': status
            }
        )

        items = response['Items']
        assert len(items) >= 2

        # Verify all items match the status
        for item in items:
            assert item['status'] == status
            assert item['user_id'] == user_id


@pytest.mark.integration
@pytest.mark.slow
class TestTTLDeletion:
    """Test TTL deletion behavior.

    Note: These tests verify TTL configuration but don't wait for actual deletion
    as TTL cleanup can take up to 48 hours in production.
    """

    def test_create_event_with_expired_ttl(self, repository):
        """Test creating an event with an already-expired TTL.

        This event should be deleted by DynamoDB's background TTL process
        within minutes to hours.
        """
        user_id = f"test-user-expired-ttl-{int(time.time())}"
        event_id = f"evt-expired-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create event
        created = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="ttl.expired.test",
            payload={"note": "This event should be deleted by TTL"},
            timestamp=timestamp
        )

        # Manually set expired TTL
        dynamodb = boto3.resource('dynamodb')
        table_name = repository.table_name
        table = dynamodb.Table(table_name)

        expired_ttl = int(time.time()) - 1000  # Expired 1000 seconds ago

        table.update_item(
            Key={
                'user_id': user_id,
                'timestamp#event_id': f"{timestamp}#{event_id}"
            },
            UpdateExpression='SET #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={':ttl': expired_ttl}
        )

        # Verify event exists (before TTL deletion)
        retrieved = repository.get_event(user_id, f"{timestamp}#{event_id}")
        assert retrieved is not None
        assert retrieved['ttl'] == expired_ttl

        # Note: TTL deletion is asynchronous and may take minutes to hours
        # In production, verify deletion after waiting period
        print(f"TTL test event created: user_id={user_id}, event_id={event_id}")
        print("Check CloudWatch TTLDeletedItemCount metric to verify deletion")

    def test_ttl_configuration_allows_future_expiration(self, repository):
        """Verify that events with future TTL are not immediately deleted."""
        user_id = f"test-user-future-ttl-{int(time.time())}"
        event_id = f"evt-future-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create event (TTL defaults to 30 days from now)
        created = repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="ttl.future.test",
            payload={},
            timestamp=timestamp
        )

        # Verify event persists
        time.sleep(1)
        retrieved = repository.get_event(user_id, f"{timestamp}#{event_id}")
        assert retrieved is not None
        assert retrieved['event_id'] == event_id

        # Verify TTL is in the future
        assert retrieved['ttl'] > int(time.time())


@pytest.mark.integration
class TestEventUpdates:
    """Test event update operations."""

    def test_update_event_status(self, repository):
        """Test updating event status."""
        user_id = f"test-user-update-{int(time.time())}"
        event_id = f"evt-update-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create event
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.update",
            payload={},
            timestamp=timestamp
        )

        # Update status
        timestamp_event_id = f"{timestamp}#{event_id}"
        updated = repository.update_event_status(
            user_id=user_id,
            timestamp_event_id=timestamp_event_id,
            status="delivered"
        )

        assert updated['status'] == 'delivered'
        assert updated['event_id'] == event_id

    def test_update_retry_count(self, repository):
        """Test updating retry count."""
        user_id = f"test-user-retry-{int(time.time())}"
        event_id = f"evt-retry-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create event
        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="test.retry",
            payload={},
            timestamp=timestamp
        )

        # Update with retry count
        timestamp_event_id = f"{timestamp}#{event_id}"
        updated = repository.update_event_status(
            user_id=user_id,
            timestamp_event_id=timestamp_event_id,
            status="retrying",
            retry_count=3
        )

        assert updated['status'] == 'retrying'
        assert updated['retry_count'] == 3
