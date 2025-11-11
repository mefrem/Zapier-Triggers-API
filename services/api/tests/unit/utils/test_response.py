"""
Unit tests for response utilities.
"""

import json
import pytest
from datetime import datetime

from src.utils.response import (
    success_response,
    error_response,
    unauthorized_response,
    rate_limit_exceeded_response,
    forbidden_response,
    not_found_response,
    bad_request_response,
    validation_error_response,
    internal_server_error_response
)


class TestSuccessResponse:
    """Tests for success_response function."""

    def test_success_response_default(self):
        """Test success response with default parameters."""
        response = success_response({'result': 'success'})

        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'

        body = json.loads(response['body'])
        assert body['result'] == 'success'

    def test_success_response_custom_status(self):
        """Test success response with custom status code."""
        response = success_response({'created': True}, status_code=201)

        assert response['statusCode'] == 201

    def test_success_response_custom_headers(self):
        """Test success response with custom headers."""
        response = success_response(
            {'data': 'test'},
            headers={'X-Custom-Header': 'value'}
        )

        assert response['headers']['X-Custom-Header'] == 'value'
        # Default headers should still be present
        assert response['headers']['Content-Type'] == 'application/json'


class TestErrorResponse:
    """Tests for error_response function."""

    def test_error_response_basic(self):
        """Test basic error response."""
        response = error_response(
            code='TEST_ERROR',
            message='This is a test error',
            status_code=400
        )

        assert response['statusCode'] == 400
        body = json.loads(response['body'])

        assert body['error']['code'] == 'TEST_ERROR'
        assert body['error']['message'] == 'This is a test error'
        assert 'timestamp' in body['error']
        assert 'request_id' in body['error']

    def test_error_response_with_details(self):
        """Test error response with details."""
        details = {'field': 'email', 'issue': 'invalid format'}
        response = error_response(
            code='VALIDATION_ERROR',
            message='Validation failed',
            status_code=422,
            details=details
        )

        body = json.loads(response['body'])
        assert body['error']['details'] == details

    def test_error_response_with_request_id(self):
        """Test error response with custom request ID."""
        response = error_response(
            code='ERROR',
            message='Error',
            request_id='custom-request-123'
        )

        body = json.loads(response['body'])
        assert body['error']['request_id'] == 'custom-request-123'

    def test_error_response_with_custom_headers(self):
        """Test error response with custom headers."""
        response = error_response(
            code='ERROR',
            message='Error',
            headers={'X-Error-Code': '12345'}
        )

        assert response['headers']['X-Error-Code'] == '12345'


class TestUnauthorizedResponse:
    """Tests for unauthorized_response function."""

    def test_unauthorized_default(self):
        """Test 401 unauthorized response with default message."""
        response = unauthorized_response()

        assert response['statusCode'] == 401
        assert response['headers']['WWW-Authenticate'] == 'X-API-Key'

        body = json.loads(response['body'])
        assert body['error']['code'] == 'UNAUTHORIZED'
        assert 'Invalid or missing API key' in body['error']['message']

    def test_unauthorized_custom_message(self):
        """Test 401 unauthorized response with custom message."""
        response = unauthorized_response(message='API key has expired')

        body = json.loads(response['body'])
        assert body['error']['message'] == 'API key has expired'

    def test_unauthorized_with_request_id(self):
        """Test 401 unauthorized response with request ID."""
        response = unauthorized_response(request_id='req-123')

        body = json.loads(response['body'])
        assert body['error']['request_id'] == 'req-123'


class TestRateLimitExceededResponse:
    """Tests for rate_limit_exceeded_response function."""

    def test_rate_limit_default(self):
        """Test 429 rate limit response with default retry_after."""
        response = rate_limit_exceeded_response()

        assert response['statusCode'] == 429
        assert response['headers']['Retry-After'] == '60'

        body = json.loads(response['body'])
        assert body['error']['code'] == 'RATE_LIMIT_EXCEEDED'
        assert body['error']['details']['retry_after'] == 60

    def test_rate_limit_custom_retry(self):
        """Test 429 rate limit response with custom retry_after."""
        response = rate_limit_exceeded_response(retry_after=120)

        assert response['headers']['Retry-After'] == '120'

        body = json.loads(response['body'])
        assert body['error']['details']['retry_after'] == 120

    def test_rate_limit_custom_message(self):
        """Test 429 rate limit response with custom message."""
        response = rate_limit_exceeded_response(
            message='Too many requests from this API key'
        )

        body = json.loads(response['body'])
        assert body['error']['message'] == 'Too many requests from this API key'


class TestForbiddenResponse:
    """Tests for forbidden_response function."""

    def test_forbidden_default(self):
        """Test 403 forbidden response."""
        response = forbidden_response()

        assert response['statusCode'] == 403

        body = json.loads(response['body'])
        assert body['error']['code'] == 'FORBIDDEN'
        assert 'Insufficient permissions' in body['error']['message']

    def test_forbidden_custom_message(self):
        """Test 403 forbidden response with custom message."""
        response = forbidden_response(message='Access denied to this resource')

        body = json.loads(response['body'])
        assert body['error']['message'] == 'Access denied to this resource'


class TestNotFoundResponse:
    """Tests for not_found_response function."""

    def test_not_found_default(self):
        """Test 404 not found response."""
        response = not_found_response()

        assert response['statusCode'] == 404

        body = json.loads(response['body'])
        assert body['error']['code'] == 'NOT_FOUND'
        assert body['error']['message'] == 'Resource not found'

    def test_not_found_custom_message(self):
        """Test 404 not found response with custom message."""
        response = not_found_response(message='API key not found')

        body = json.loads(response['body'])
        assert body['error']['message'] == 'API key not found'


class TestBadRequestResponse:
    """Tests for bad_request_response function."""

    def test_bad_request_default(self):
        """Test 400 bad request response."""
        response = bad_request_response()

        assert response['statusCode'] == 400

        body = json.loads(response['body'])
        assert body['error']['code'] == 'BAD_REQUEST'

    def test_bad_request_with_details(self):
        """Test 400 bad request response with details."""
        details = {'missing_field': 'name'}
        response = bad_request_response(
            message='Missing required field',
            details=details
        )

        body = json.loads(response['body'])
        assert body['error']['details'] == details


class TestValidationErrorResponse:
    """Tests for validation_error_response function."""

    def test_validation_error(self):
        """Test 422 validation error response."""
        errors = [
            {'field': 'email', 'message': 'Invalid email format'},
            {'field': 'age', 'message': 'Must be a positive number'}
        ]

        response = validation_error_response(errors)

        assert response['statusCode'] == 422

        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert body['error']['details']['errors'] == errors

    def test_validation_error_custom_message(self):
        """Test 422 validation error response with custom message."""
        errors = [{'field': 'name', 'message': 'Required'}]

        response = validation_error_response(
            errors,
            message='Request validation failed'
        )

        body = json.loads(response['body'])
        assert body['error']['message'] == 'Request validation failed'


class TestInternalServerErrorResponse:
    """Tests for internal_server_error_response function."""

    def test_internal_server_error_default(self):
        """Test 500 internal server error response."""
        response = internal_server_error_response()

        assert response['statusCode'] == 500

        body = json.loads(response['body'])
        assert body['error']['code'] == 'INTERNAL_SERVER_ERROR'
        assert body['error']['message'] == 'Internal server error'

    def test_internal_server_error_custom_message(self):
        """Test 500 internal server error response with custom message."""
        response = internal_server_error_response(
            message='Database connection failed'
        )

        body = json.loads(response['body'])
        assert body['error']['message'] == 'Database connection failed'

    def test_internal_server_error_with_request_id(self):
        """Test 500 internal server error response with request ID."""
        response = internal_server_error_response(request_id='req-error-123')

        body = json.loads(response['body'])
        assert body['error']['request_id'] == 'req-error-123'
