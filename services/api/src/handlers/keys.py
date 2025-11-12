"""
API Key Management Lambda Handler

Endpoints for creating, listing, updating, and revoking API keys.
"""

import json
import os
from typing import Dict, Any, Optional
from pydantic import ValidationError

from src.models.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse, APIKeyCreateResponse
from src.repositories.api_key_repository import APIKeyRepository
from src.utils.response import (
    success_response,
    error_response,
    unauthorized_response,
    forbidden_response,
    not_found_response,
    bad_request_response,
    validation_error_response,
    internal_server_error_response
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for API key management endpoints.

    Routes requests to appropriate handlers based on HTTP method and path.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        HTTP response
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    path_parameters = event.get('pathParameters') or {}

    # Extract user_id from authorizer context
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    user_id = authorizer.get('user_id')

    if not user_id:
        return unauthorized_response(message="User authentication required")

    # Route to appropriate handler
    try:
        if http_method == 'POST' and path.endswith('/keys'):
            return create_api_key(event, user_id)
        elif http_method == 'GET' and path.endswith('/keys'):
            return list_api_keys(event, user_id)
        elif http_method == 'GET' and 'key_id' in path_parameters:
            return get_api_key(event, user_id, path_parameters['key_id'])
        elif http_method == 'DELETE' and 'key_id' in path_parameters:
            return delete_api_key(event, user_id, path_parameters['key_id'])
        elif http_method == 'PATCH' and 'key_id' in path_parameters:
            return update_api_key(event, user_id, path_parameters['key_id'])
        else:
            return not_found_response(message=f"Endpoint not found: {http_method} {path}")

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return internal_server_error_response(message="An unexpected error occurred")


def create_api_key(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    POST /keys - Create a new API key.

    Args:
        event: API Gateway event
        user_id: Authenticated user ID

    Returns:
        HTTP response with new API key (shown only once)
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate input
        try:
            key_request = APIKeyCreate(**body)
        except ValidationError as e:
            return validation_error_response(
                errors=[{'field': err['loc'][0], 'message': err['msg']} for err in e.errors()],
                message="Invalid request data"
            )

        # Create API key
        repository = APIKeyRepository()
        api_key_model, api_key = repository.create(
            user_id=user_id,
            name=key_request.name,
            rate_limit=key_request.rate_limit,
            expires_at=key_request.expires_at,
            scopes=key_request.scopes
        )

        # Create response with actual API key (shown only once)
        response_data = APIKeyCreateResponse(
            key_id=api_key_model.key_id,
            user_id=api_key_model.user_id,
            name=api_key_model.name,
            created_at=api_key_model.created_at,
            last_used_at=api_key_model.last_used_at,
            expires_at=api_key_model.expires_at,
            rate_limit=api_key_model.rate_limit,
            is_active=api_key_model.is_active,
            scopes=api_key_model.scopes,
            api_key=api_key  # The actual key, shown only once
        )

        return success_response(response_data.model_dump(), status_code=201)

    except ValueError as e:
        return bad_request_response(message=str(e))
    except Exception as e:
        print(f"Error creating API key: {str(e)}")
        return internal_server_error_response()


def list_api_keys(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    GET /keys - List all API keys for the user.

    Args:
        event: API Gateway event
        user_id: Authenticated user ID

    Returns:
        HTTP response with list of API keys (without key values)
    """
    try:
        repository = APIKeyRepository()
        api_keys = repository.list_by_user(user_id)

        # Convert to response models (without exposing key values)
        response_data = [
            APIKeyResponse(
                key_id=key.key_id,
                user_id=key.user_id,
                name=key.name,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
                rate_limit=key.rate_limit,
                is_active=key.is_active,
                scopes=key.scopes
            ).model_dump()
            for key in api_keys
        ]

        return success_response({'keys': response_data, 'count': len(response_data)})

    except Exception as e:
        print(f"Error listing API keys: {str(e)}")
        return internal_server_error_response()


def get_api_key(event: Dict[str, Any], user_id: str, key_id: str) -> Dict[str, Any]:
    """
    GET /keys/{key_id} - Get details of a specific API key.

    Args:
        event: API Gateway event
        user_id: Authenticated user ID
        key_id: API key ID

    Returns:
        HTTP response with API key details (without key value)
    """
    try:
        repository = APIKeyRepository()
        api_key = repository.get_by_id(user_id, key_id)

        if not api_key:
            return not_found_response(message=f"API key not found: {key_id}")

        # Verify ownership
        if api_key.user_id != user_id:
            return forbidden_response(message="Access denied to this API key")

        # Convert to response model
        response_data = APIKeyResponse(
            key_id=api_key.key_id,
            user_id=api_key.user_id,
            name=api_key.name,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            rate_limit=api_key.rate_limit,
            is_active=api_key.is_active,
            scopes=api_key.scopes
        )

        return success_response(response_data.model_dump())

    except Exception as e:
        print(f"Error getting API key: {str(e)}")
        return internal_server_error_response()


def delete_api_key(event: Dict[str, Any], user_id: str, key_id: str) -> Dict[str, Any]:
    """
    DELETE /keys/{key_id} - Revoke an API key (soft delete).

    Args:
        event: API Gateway event
        user_id: Authenticated user ID
        key_id: API key ID

    Returns:
        HTTP response confirming deletion
    """
    try:
        repository = APIKeyRepository()

        # Verify key exists and belongs to user
        api_key = repository.get_by_id(user_id, key_id)
        if not api_key:
            return not_found_response(message=f"API key not found: {key_id}")

        if api_key.user_id != user_id:
            return forbidden_response(message="Access denied to this API key")

        # Revoke the key
        success = repository.revoke(user_id, key_id)

        if not success:
            return internal_server_error_response(message="Failed to revoke API key")

        return success_response({
            'message': 'API key revoked successfully',
            'key_id': key_id
        })

    except Exception as e:
        print(f"Error deleting API key: {str(e)}")
        return internal_server_error_response()


def update_api_key(event: Dict[str, Any], user_id: str, key_id: str) -> Dict[str, Any]:
    """
    PATCH /keys/{key_id} - Update API key metadata.

    Args:
        event: API Gateway event
        user_id: Authenticated user ID
        key_id: API key ID

    Returns:
        HTTP response with updated API key
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate input
        try:
            update_request = APIKeyUpdate(**body)
        except ValidationError as e:
            return validation_error_response(
                errors=[{'field': err['loc'][0], 'message': err['msg']} for err in e.errors()],
                message="Invalid request data"
            )

        repository = APIKeyRepository()

        # Verify key exists and belongs to user
        api_key = repository.get_by_id(user_id, key_id)
        if not api_key:
            return not_found_response(message=f"API key not found: {key_id}")

        if api_key.user_id != user_id:
            return forbidden_response(message="Access denied to this API key")

        # Update the key
        success = repository.update(
            user_id=user_id,
            key_id=key_id,
            name=update_request.name,
            rate_limit=update_request.rate_limit
        )

        if not success:
            return internal_server_error_response(message="Failed to update API key")

        # Get updated key
        updated_key = repository.get_by_id(user_id, key_id)

        response_data = APIKeyResponse(
            key_id=updated_key.key_id,
            user_id=updated_key.user_id,
            name=updated_key.name,
            created_at=updated_key.created_at,
            last_used_at=updated_key.last_used_at,
            expires_at=updated_key.expires_at,
            rate_limit=updated_key.rate_limit,
            is_active=updated_key.is_active,
            scopes=updated_key.scopes
        )

        return success_response(response_data.model_dump())

    except json.JSONDecodeError:
        return bad_request_response(message="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating API key: {str(e)}")
        return internal_server_error_response()
