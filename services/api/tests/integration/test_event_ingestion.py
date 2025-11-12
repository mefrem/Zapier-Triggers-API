"""
Integration tests for event ingestion flow.

Tests complete end-to-end event ingestion with real DynamoDB and SQS (mocked).
"""

import os
import pytest
import boto3
from datetime import datetime
from moto import mock_aws
from fastapi.testclient import TestClient
from handlers.events import app
from repositories.event_repository import EventRepository


@pytest.fixture(scope='function')
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture(scope='function')
def dynamodb_table(aws_credentials):
    """Create mock DynamoDB table for integration testing."""
    with mock_aws():
        # Set environment variables
        os.environ['EVENTS_TABLE_NAME'] = 'test-events-table'
        os.environ['EVENT_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

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

        # Create SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
        os.environ['EVENT_QUEUE_URL'] = queue_url

        yield table


@pytest.fixture
def client(dynamodb_table):
    """Create FastAPI test client with real AWS services (mocked)."""
    return TestClient(app)


class TestEventIngestionIntegration:
    """Integration tests for complete event ingestion flow."""

    def test_end_to_end_event_ingestion(self, client, dynamodb_table):
        """Test complete event ingestion flow from API to DynamoDB."""
        # Make POST request
        response = client.post(
            '/events',
            json={
                'event_type': 'user.created',
                'payload': {
                    'user_id': 'usr_12345',
                    'email': 'test@example.com',
                    'name': 'Jane Doe'
                }
            },
            headers={'X-Request-ID': 'integration-test-123'}
        )

        # Verify API response
        assert response.status_code == 201
        data = response.json()
        assert 'event_id' in data
        assert data['status'] == 'received'
        assert 'timestamp' in data
        assert 'successfully' in data['message'].lower()

        event_id = data['event_id']
        timestamp = data['timestamp']

        # Verify event was persisted to DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-events-table')

        # Query by user_id and timestamp#event_id
        db_response = table.get_item(
            Key={
                'user_id': 'anonymous',  # Default user_id until auth is implemented
                'timestamp#event_id': f"{timestamp}#{event_id}"
            }
        )

        assert 'Item' in db_response
        item = db_response['Item']
        assert item['event_id'] == event_id
        assert item['event_type'] == 'user.created'
        assert item['payload']['user_id'] == 'usr_12345'
        assert item['payload']['email'] == 'test@example.com'
        assert item['status'] == 'received'
        assert item['retry_count'] == 0
        assert 'ttl' in item
        assert 'metadata' in item

    def test_event_queued_to_sqs(self, client, dynamodb_table):
        """Test that events are queued to SQS."""
        import json

        # Make POST request
        response = client.post(
            '/events',
            json={
                'event_type': 'order.completed',
                'payload': {
                    'order_id': 'ord_98765',
                    'total': 99.99
                }
            }
        )

        assert response.status_code == 201
        event_id = response.json()['event_id']

        # Verify message was sent to SQS
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = os.environ['EVENT_QUEUE_URL']

        messages = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1
        )

        assert 'Messages' in messages
        assert len(messages['Messages']) > 0

        # Find our message
        message_found = False
        for message in messages['Messages']:
            body = json.loads(message['Body'])
            if body['event_id'] == event_id:
                message_found = True
                assert body['user_id'] == 'anonymous'
                assert body['event_type'] == 'order.completed'
                assert 'correlation_id' in body
                break

        assert message_found, "Event message not found in SQS queue"

    def test_multiple_events_from_same_user(self, client, dynamodb_table):
        """Test creating multiple events from the same user."""
        event_ids = []

        # Create 3 events
        for i in range(3):
            response = client.post(
                '/events',
                json={
                    'event_type': f'test.event.{i}',
                    'payload': {'index': i, 'data': f'test-{i}'}
                }
            )
            assert response.status_code == 201
            event_ids.append(response.json()['event_id'])

        # Verify all events are in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-events-table')

        # Query all events for user
        db_response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq('anonymous')
        )

        assert db_response['Count'] >= 3
        stored_event_ids = [item['event_id'] for item in db_response['Items']]

        for event_id in event_ids:
            assert event_id in stored_event_ids

    def test_event_with_large_payload(self, client, dynamodb_table):
        """Test event with large nested payload."""
        large_payload = {
            'transaction_id': 'txn_large_123',
            'items': [
                {
                    'sku': f'ITEM-{i}',
                    'name': f'Product {i}',
                    'quantity': i,
                    'price': 19.99 + i
                }
                for i in range(50)
            ],
            'customer': {
                'id': 'cust_123',
                'name': 'John Doe',
                'email': 'john@example.com',
                'addresses': [
                    {
                        'type': 'shipping',
                        'street': '123 Main St',
                        'city': 'Anytown',
                        'state': 'CA',
                        'zip': '12345'
                    },
                    {
                        'type': 'billing',
                        'street': '456 Oak Ave',
                        'city': 'Other City',
                        'state': 'NY',
                        'zip': '67890'
                    }
                ]
            },
            'metadata': {
                'source': 'web',
                'device': 'mobile',
                'session_id': 'sess_xyz789'
            }
        }

        response = client.post(
            '/events',
            json={
                'event_type': 'order.large',
                'payload': large_payload
            }
        )

        assert response.status_code == 201
        event_id = response.json()['event_id']

        # Verify payload was stored correctly
        repository = EventRepository(table_name='test-events-table')
        event = repository.get_event_by_id('anonymous', event_id)

        assert event is not None
        assert len(event['payload']['items']) == 50
        assert event['payload']['customer']['name'] == 'John Doe'

    def test_validation_error_does_not_persist_event(self, client, dynamodb_table):
        """Test that validation errors don't persist events to DynamoDB."""
        # Make invalid request
        response = client.post(
            '/events',
            json={
                'event_type': 'test.event'
                # Missing payload
            }
        )

        assert response.status_code == 400

        # Verify no event was created in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-events-table')

        db_response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq('anonymous')
        )

        assert db_response['Count'] == 0

    def test_concurrent_event_creation(self, client, dynamodb_table):
        """Test concurrent event creation (simulated)."""
        import concurrent.futures

        def create_event(index):
            response = client.post(
                '/events',
                json={
                    'event_type': 'concurrent.test',
                    'payload': {'index': index}
                }
            )
            return response.status_code, response.json()

        # Create 10 events concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_event, i) for i in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Verify all succeeded
        for status_code, data in results:
            assert status_code == 201
            assert 'event_id' in data

        # Verify all are in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-events-table')

        db_response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq('anonymous')
        )

        assert db_response['Count'] >= 10

    def test_event_ttl_is_set(self, client, dynamodb_table):
        """Test that TTL attribute is set correctly."""
        import time

        current_time = time.time()

        response = client.post(
            '/events',
            json={
                'event_type': 'ttl.test',
                'payload': {'test': 'data'}
            }
        )

        assert response.status_code == 201
        event_id = response.json()['event_id']

        # Retrieve from DynamoDB
        repository = EventRepository(table_name='test-events-table')
        event = repository.get_event_by_id('anonymous', event_id)

        # Verify TTL is ~30 days from now
        expected_ttl = current_time + (30 * 24 * 60 * 60)
        assert 'ttl' in event
        # Allow 10 seconds tolerance
        assert abs(event['ttl'] - expected_ttl) < 10

    def test_metadata_captured_correctly(self, client, dynamodb_table):
        """Test that request metadata is captured."""
        response = client.post(
            '/events',
            json={
                'event_type': 'metadata.test',
                'payload': {'test': 'data'}
            },
            headers={
                'X-Request-ID': 'custom-correlation-456',
                'User-Agent': 'CustomClient/2.0'
            }
        )

        assert response.status_code == 201
        event_id = response.json()['event_id']

        # Retrieve from DynamoDB
        repository = EventRepository(table_name='test-events-table')
        event = repository.get_event_by_id('anonymous', event_id)

        assert 'metadata' in event
        assert event['metadata']['correlation_id'] == 'custom-correlation-456'
        assert event['metadata']['api_version'] == 'v1'
        assert 'source_ip' in event['metadata']
