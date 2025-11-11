"""
HTTP Response Utilities

Standardized error and success response formatting.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List


def success_response(
    data: Any,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response data
        status_code: HTTP status code
        headers: Additional headers

    Returns:
        API Gateway response dict
    """
    response_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true'
    }

    if headers:
        response_headers.update(headers)

    return {
        'statusCode': status_code,
        'headers': response_headers,
        'body': json.dumps(data)
    }


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable error message",
            "details": {...} (optional),
            "timestamp": "2025-11-11T00:00:00Z",
            "request_id": "uuid"
        }
    }

    Args:
        code: Error code (e.g., "UNAUTHORIZED", "RATE_LIMIT_EXCEEDED")
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details (optional)
        request_id: Request correlation ID (optional)
        headers: Additional headers (optional)

    Returns:
        API Gateway response dict
    """
    response_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true'
    }

    if headers:
        response_headers.update(headers)

    error_body = {
        'error': {
            'code': code,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'request_id': request_id or str(uuid.uuid4())
        }
    }

    if details:
        error_body['error']['details'] = details

    return {
        'statusCode': status_code,
        'headers': response_headers,
        'body': json.dumps(error_body)
    }


def unauthorized_response(
    message: str = "Unauthorized: Invalid or missing API key",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 401 Unauthorized response.

    Args:
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='UNAUTHORIZED',
        message=message,
        status_code=401,
        request_id=request_id,
        headers={'WWW-Authenticate': 'X-API-Key'}
    )


def rate_limit_exceeded_response(
    retry_after: int = 60,
    message: str = "Rate limit exceeded",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 429 Too Many Requests response.

    Args:
        retry_after: Seconds until rate limit resets
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='RATE_LIMIT_EXCEEDED',
        message=message,
        status_code=429,
        request_id=request_id,
        details={'retry_after': retry_after},
        headers={'Retry-After': str(retry_after)}
    )


def forbidden_response(
    message: str = "Forbidden: Insufficient permissions",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 403 Forbidden response.

    Args:
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='FORBIDDEN',
        message=message,
        status_code=403,
        request_id=request_id
    )


def not_found_response(
    message: str = "Resource not found",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 404 Not Found response.

    Args:
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='NOT_FOUND',
        message=message,
        status_code=404,
        request_id=request_id
    )


def bad_request_response(
    message: str = "Bad request",
    details: Optional[Any] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 400 Bad Request response.

    Args:
        message: Error message
        details: Validation error details (optional)
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='BAD_REQUEST',
        message=message,
        status_code=400,
        details=details,
        request_id=request_id
    )


def validation_error_response(
    errors: List[Dict[str, Any]],
    message: str = "Validation failed",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 422 Unprocessable Entity response for validation errors.

    Args:
        errors: List of validation errors
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='VALIDATION_ERROR',
        message=message,
        status_code=422,
        details={'errors': errors},
        request_id=request_id
    )


def internal_server_error_response(
    message: str = "Internal server error",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a 500 Internal Server Error response.

    Args:
        message: Error message
        request_id: Request correlation ID (optional)

    Returns:
        API Gateway response dict
    """
    return error_response(
        code='INTERNAL_SERVER_ERROR',
        message=message,
        status_code=500,
        request_id=request_id
    )
