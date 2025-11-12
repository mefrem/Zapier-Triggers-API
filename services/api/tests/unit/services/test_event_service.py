"""
Unit tests for EventService.

Tests business logic with mocked repository and SQS.
"""

import os
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError
from models.event import EventInput, EventResponse
from services.event_service import EventService
from repositories.event_repository import EventRepository


@pytest.fixture
def mock_repository():
    """Create mock EventRepository."""
    return Mock(spec=EventRepository)


@pytest.fixture
def mock_sqs_client():
    """Create mock SQS client."""
    mock_client = MagicMock()
    mock_client.send_message.return_value = {
        'MessageId': 'test-message-id',
        'MD5OfMessageBody': 'test-md5'
    }
    return mock_client


@pytest.fixture
def event_service(mock_repository, mock_sqs_client):
    """Create EventService with mocked dependencies."""
    os.environ['EVENT_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

    with patch('services.event_service.boto3.client', return_value=mock_sqs_client):
        service = EventService(repository=mock_repository, queue_url='https://sqs.us-east-1.amazonaws.com/123456789/test-queue')
        service.sqs = mock_sqs_client
        return service


class TestEventService:
    """Test EventService business logic."""

    def test_initialization_with_defaults(self):
        """Test service initialization with default parameters."""
        os.environ['EVENTS_TABLE_NAME'] = 'test-table'
        os.environ['EVENT_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/queue'

        with patch('services.event_service.EventRepository'):
            service = EventService()
            assert service.queue_url == 'https://sqs.us-east-1.amazonaws.com/123456789/queue'

    def test_initialization_with_custom_params(self, mock_repository):
        """Test service initialization with custom parameters."""
        service = EventService(
            repository=mock_repository,
            queue_url='https://custom-queue-url'
        )
        assert service.repository == mock_repository
        assert service.queue_url == 'https://custom-queue-url'

    @patch('services.event_service.uuid.uuid4')
    @patch('services.event_service.datetime')
    def test_create_event_success(
        self,
        mock_datetime,
        mock_uuid,
        event_service,
        mock_repository
    ):
        """Test successful event creation."""
        # Setup mocks
        mock_uuid.return_value = '550e8400-e29b-41d4-a716-446655440000'
        mock_dt = Mock()
        mock_dt.isoformat.return_value = '2025-11-11T10:00:00.123456'
        mock_datetime.utcnow.return_value = mock_dt

        mock_repository.create_event.return_value = {
            'user_id': 'user-123',
            'event_id': '550e8400-e29b-41d4-a716-446655440000',
            'event_type': 'user.created',
            'payload': {'user_id': '123'},
            'status': 'received'
        }

        # Create event
        event_input = EventInput(
            event_type='user.created',
            payload={'user_id': '123', 'email': 'test@example.com'}
        )

        response = event_service.create_event(
            event_input=event_input,
            user_id='user-123',
            correlation_id='corr-123',
            metadata={'source_ip': '192.168.1.1'}
        )

        # Verify response
        assert isinstance(response, EventResponse)
        assert response.event_id == '550e8400-e29b-41d4-a716-446655440000'
        assert response.status == 'received'
        assert response.timestamp == '2025-11-11T10:00:00.123456Z'
        assert 'successfully' in response.message.lower()

        # Verify repository was called
        mock_repository.create_event.assert_called_once()
        call_args = mock_repository.create_event.call_args
        assert call_args.kwargs['user_id'] == 'user-123'
        assert call_args.kwargs['event_type'] == 'user.created'
        assert call_args.kwargs['metadata']['correlation_id'] == 'corr-123'

    @patch('services.event_service.uuid.uuid4')
    @patch('services.event_service.datetime')
    def test_create_event_queues_to_sqs(
        self,
        mock_datetime,
        mock_uuid,
        event_service,
        mock_repository,
        mock_sqs_client
    ):
        """Test that event is queued to SQS."""
        # Setup mocks
        mock_uuid.return_value = 'evt-123'
        mock_dt = Mock()
        mock_dt.isoformat.return_value = '2025-11-11T10:00:00'
        mock_datetime.utcnow.return_value = mock_dt

        mock_repository.create_event.return_value = {'event_id': 'evt-123'}

        # Create event
        event_input = EventInput(
            event_type='test.event',
            payload={'test': 'data'}
        )

        event_service.create_event(
            event_input=event_input,
            user_id='user-123',
            correlation_id='corr-123'
        )

        # Verify SQS was called
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args

        assert call_args.kwargs['QueueUrl'] == 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'

        message_body = json.loads(call_args.kwargs['MessageBody'])
        assert message_body['event_id'] == 'evt-123'
        assert message_body['user_id'] == 'user-123'
        assert message_body['event_type'] == 'test.event'

    @patch('services.event_service.uuid.uuid4')
    @patch('services.event_service.datetime')
    def test_create_event_without_queue_url(
        self,
        mock_datetime,
        mock_uuid,
        mock_repository,
        mock_sqs_client
    ):
        """Test event creation without SQS queue configured."""
        mock_uuid.return_value = 'evt-123'
        mock_dt = Mock()
        mock_dt.isoformat.return_value = '2025-11-11T10:00:00'
        mock_datetime.utcnow.return_value = mock_dt

        mock_repository.create_event.return_value = {'event_id': 'evt-123'}

        # Create service without queue URL
        service = EventService(repository=mock_repository, queue_url=None)
        service.sqs = mock_sqs_client

        event_input = EventInput(
            event_type='test.event',
            payload={'test': 'data'}
        )

        response = service.create_event(
            event_input=event_input,
            user_id='user-123',
            correlation_id='corr-123'
        )

        # Verify SQS was NOT called
        mock_sqs_client.send_message.assert_not_called()

        # But event was still created
        assert response.event_id == 'evt-123'

    def test_create_event_handles_repository_error(
        self,
        event_service,
        mock_repository
    ):
        """Test error handling for repository failures."""
        # Setup mock to raise error
        mock_repository.create_event.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Throttled'}},
            'PutItem'
        )

        event_input = EventInput(
            event_type='test.event',
            payload={'test': 'data'}
        )

        with pytest.raises(ClientError) as exc_info:
            event_service.create_event(
                event_input=event_input,
                user_id='user-123',
                correlation_id='corr-123'
            )

        assert exc_info.value.response['Error']['Code'] == 'ProvisionedThroughputExceededException'

    @patch('services.event_service.uuid.uuid4')
    @patch('services.event_service.datetime')
    def test_create_event_handles_sqs_error_gracefully(
        self,
        mock_datetime,
        mock_uuid,
        event_service,
        mock_repository,
        mock_sqs_client
    ):
        """Test that SQS errors don't fail the entire operation."""
        mock_uuid.return_value = 'evt-123'
        mock_dt = Mock()
        mock_dt.isoformat.return_value = '2025-11-11T10:00:00'
        mock_datetime.utcnow.return_value = mock_dt

        mock_repository.create_event.return_value = {'event_id': 'evt-123'}

        # Make SQS fail
        mock_sqs_client.send_message.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'SQS down'}},
            'SendMessage'
        )

        event_input = EventInput(
            event_type='test.event',
            payload={'test': 'data'}
        )

        # Should not raise exception
        response = event_service.create_event(
            event_input=event_input,
            user_id='user-123',
            correlation_id='corr-123'
        )

        # Event was still created successfully
        assert response.event_id == 'evt-123'
        assert response.status == 'received'

    @patch('services.event_service.uuid.uuid4')
    @patch('services.event_service.datetime')
    def test_create_event_adds_metadata(
        self,
        mock_datetime,
        mock_uuid,
        event_service,
        mock_repository
    ):
        """Test that correlation_id and api_version are added to metadata."""
        mock_uuid.return_value = 'evt-123'
        mock_dt = Mock()
        mock_dt.isoformat.return_value = '2025-11-11T10:00:00'
        mock_datetime.utcnow.return_value = mock_dt

        mock_repository.create_event.return_value = {'event_id': 'evt-123'}

        event_input = EventInput(
            event_type='test.event',
            payload={'test': 'data'}
        )

        event_service.create_event(
            event_input=event_input,
            user_id='user-123',
            correlation_id='corr-456',
            metadata={'source_ip': '192.168.1.1'}
        )

        # Verify metadata was enriched
        call_args = mock_repository.create_event.call_args
        metadata = call_args.kwargs['metadata']
        assert metadata['correlation_id'] == 'corr-456'
        assert metadata['api_version'] == 'v1'
        assert metadata['source_ip'] == '192.168.1.1'

    def test_get_event(self, event_service, mock_repository):
        """Test retrieving an event."""
        mock_repository.get_event_by_id.return_value = {
            'user_id': 'user-123',
            'event_id': 'evt-123',
            'event_type': 'test.event'
        }

        result = event_service.get_event('user-123', 'evt-123')

        assert result is not None
        assert result['event_id'] == 'evt-123'
        mock_repository.get_event_by_id.assert_called_once_with('user-123', 'evt-123')

    def test_get_event_not_found(self, event_service, mock_repository):
        """Test retrieving non-existent event."""
        mock_repository.get_event_by_id.return_value = None

        result = event_service.get_event('user-999', 'evt-nonexistent')

        assert result is None
