"""
Unit tests for events handler (FastAPI endpoint).

Tests POST /events endpoint with mocked service layer.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError
from models.event import EventResponse
from handlers.events import app


@pytest.fixture
def mock_event_service():
    """Create mock EventService."""
    with patch('handlers.events.event_service') as mock_service:
        yield mock_service


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestPostEventsEndpoint:
    """Test POST /events endpoint."""

    def test_create_event_success(self, client, mock_event_service):
        """Test successful event creation returns 201."""
        # Setup mock
        mock_event_service.create_event.return_value = EventResponse(
            event_id='550e8400-e29b-41d4-a716-446655440000',
            status='received',
            timestamp='2025-11-11T10:00:00.123456Z',
            message='Event successfully created and queued for processing'
        )

        # Make request
        response = client.post(
            '/events',
            json={
                'event_type': 'user.created',
                'payload': {
                    'user_id': 'usr_12345',
                    'email': 'test@example.com'
                }
            },
            headers={'X-Request-ID': 'test-correlation-id'}
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data['event_id'] == '550e8400-e29b-41d4-a716-446655440000'
        assert data['status'] == 'received'
        assert data['timestamp'] == '2025-11-11T10:00:00.123456Z'
        assert 'successfully' in data['message'].lower()

    def test_create_event_missing_event_type(self, client, mock_event_service):
        """Test validation error when event_type is missing."""
        response = client.post(
            '/events',
            json={
                'payload': {'user_id': '123'}
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert data['error']['message'] == 'Invalid request payload'
        assert any(d['field'] == 'event_type' for d in data['error']['details'])

    def test_create_event_missing_payload(self, client, mock_event_service):
        """Test validation error when payload is missing."""
        response = client.post(
            '/events',
            json={
                'event_type': 'user.created'
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['code'] == 'VALIDATION_ERROR'
        assert any(d['field'] == 'payload' for d in data['error']['details'])

    def test_create_event_empty_event_type(self, client, mock_event_service):
        """Test validation error for empty event_type."""
        response = client.post(
            '/events',
            json={
                'event_type': '',
                'payload': {'test': 'data'}
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['code'] == 'VALIDATION_ERROR'

    def test_create_event_empty_payload(self, client, mock_event_service):
        """Test validation error for empty payload."""
        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {}
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['code'] == 'VALIDATION_ERROR'

    def test_create_event_payload_not_object(self, client, mock_event_service):
        """Test validation error when payload is not an object."""
        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': 'not an object'
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['code'] == 'VALIDATION_ERROR'

    def test_create_event_malformed_json(self, client, mock_event_service):
        """Test error handling for malformed JSON."""
        response = client.post(
            '/events',
            data='{"invalid": json}',
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 422  # FastAPI returns 422 for JSON parse errors

    def test_create_event_with_correlation_id(self, client, mock_event_service):
        """Test that correlation ID from header is used."""
        mock_event_service.create_event.return_value = EventResponse(
            event_id='evt-123',
            status='received',
            timestamp='2025-11-11T10:00:00Z',
            message='Event created'
        )

        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            },
            headers={'X-Request-ID': 'custom-correlation-id'}
        )

        assert response.status_code == 201

        # Verify service was called with correlation ID
        call_args = mock_event_service.create_event.call_args
        assert call_args.kwargs['correlation_id'] == 'custom-correlation-id'

    def test_create_event_generates_correlation_id_if_missing(self, client, mock_event_service):
        """Test that correlation ID is generated if not provided."""
        mock_event_service.create_event.return_value = EventResponse(
            event_id='evt-123',
            status='received',
            timestamp='2025-11-11T10:00:00Z',
            message='Event created'
        )

        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            }
        )

        assert response.status_code == 201

        # Verify correlation ID was generated
        call_args = mock_event_service.create_event.call_args
        correlation_id = call_args.kwargs['correlation_id']
        assert correlation_id is not None
        assert len(correlation_id) > 0

    def test_create_event_includes_metadata(self, client, mock_event_service):
        """Test that metadata is collected from request."""
        mock_event_service.create_event.return_value = EventResponse(
            event_id='evt-123',
            status='received',
            timestamp='2025-11-11T10:00:00Z',
            message='Event created'
        )

        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            },
            headers={'User-Agent': 'TestClient/1.0'}
        )

        assert response.status_code == 201

        # Verify metadata was passed to service
        call_args = mock_event_service.create_event.call_args
        metadata = call_args.kwargs['metadata']
        assert 'source_ip' in metadata
        assert metadata['user_agent'] == 'TestClient/1.0'
        assert metadata['api_version'] == 'v1'

    def test_create_event_handles_service_error(self, client, mock_event_service):
        """Test error handling for service layer failures."""
        mock_event_service.create_event.side_effect = Exception('Service error')

        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            }
        )

        assert response.status_code == 500
        data = response.json()
        assert data['error']['code'] == 'INTERNAL_ERROR'

    def test_create_event_handles_dynamodb_error(self, client, mock_event_service):
        """Test error handling for DynamoDB errors."""
        mock_event_service.create_event.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Throttled'}},
            'PutItem'
        )

        response = client.post(
            '/events',
            json={
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            }
        )

        assert response.status_code == 500

    def test_create_event_with_complex_payload(self, client, mock_event_service):
        """Test event creation with complex nested payload."""
        mock_event_service.create_event.return_value = EventResponse(
            event_id='evt-complex',
            status='received',
            timestamp='2025-11-11T10:00:00Z',
            message='Event created'
        )

        response = client.post(
            '/events',
            json={
                'event_type': 'order.completed',
                'payload': {
                    'order_id': 'ord_123',
                    'customer': {
                        'id': 'cust_456',
                        'name': 'John Doe',
                        'email': 'john@example.com'
                    },
                    'items': [
                        {'sku': 'ITEM-1', 'quantity': 2, 'price': 29.99},
                        {'sku': 'ITEM-2', 'quantity': 1, 'price': 49.99}
                    ],
                    'total': 109.97
                }
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data['event_id'] == 'evt-complex'

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert data['version'] == '1.0.0'

    def test_openapi_docs_available(self, client):
        """Test that OpenAPI documentation is available."""
        response = client.get('/openapi.json')
        assert response.status_code == 200

        openapi_spec = response.json()
        assert openapi_spec['openapi'].startswith('3.')
        assert '/events' in openapi_spec['paths']
        assert 'post' in openapi_spec['paths']['/events']

    def test_swagger_ui_available(self, client):
        """Test that Swagger UI is available."""
        response = client.get('/docs')
        assert response.status_code == 200

    def test_redoc_available(self, client):
        """Test that ReDoc is available."""
        response = client.get('/redoc')
        assert response.status_code == 200

    def test_validation_error_includes_request_id(self, client, mock_event_service):
        """Test that validation errors include request_id."""
        response = client.post(
            '/events',
            json={'event_type': 'test'},  # Missing payload
            headers={'X-Request-ID': 'test-req-id'}
        )

        assert response.status_code == 400
        data = response.json()
        assert data['error']['request_id'] == 'test-req-id'

    def test_validation_error_includes_timestamp(self, client, mock_event_service):
        """Test that validation errors include timestamp."""
        response = client.post(
            '/events',
            json={'event_type': 'test'}  # Missing payload
        )

        assert response.status_code == 400
        data = response.json()
        assert 'timestamp' in data['error']
        assert data['error']['timestamp'].endswith('Z')

    def test_multiple_validation_errors(self, client, mock_event_service):
        """Test handling multiple validation errors at once."""
        response = client.post(
            '/events',
            json={}  # Missing both event_type and payload
        )

        assert response.status_code == 400
        data = response.json()
        assert len(data['error']['details']) >= 2
        fields = [d['field'] for d in data['error']['details']]
        assert 'event_type' in fields
        assert 'payload' in fields

    def test_content_type_validation_rejects_non_json(self, client, mock_event_service):
        """Test that non-JSON Content-Type is rejected.

        Note: FastAPI's request validation handles this at the framework level.
        Non-JSON Content-Types are rejected before the handler runs.
        """
        import json as json_module

        # Use content= with raw bytes and text/plain Content-Type
        # FastAPI will reject this with 400 (not 415) because the body can't be parsed as JSON
        response = client.post(
            '/events',
            content=json_module.dumps({
                'event_type': 'test.event',
                'payload': {'test': 'data'}
            }),
            headers={'Content-Type': 'text/plain'}
        )

        # FastAPI returns 400 when Content-Type doesn't match expected type
        # The handler's explicit 415 check only runs if the request makes it past FastAPI's validation
        assert response.status_code in [400, 415]  # Either is acceptable for Content-Type validation
