"""
Event Ingestion Lambda Handler with FastAPI.

Implements POST /events endpoint for event ingestion with validation,
persistence, and queuing.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from mangum import Mangum
from pydantic import ValidationError
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from models.event import (
    EventInput, EventResponse, EventAckResponse, EventStatusResponse,
    ErrorResponse, ErrorInfo, ErrorDetail
)
from services.event_service import EventService
from services.event_lifecycle_service import EventLifecycleService
from services.retry_service import RetryService

# Initialize AWS Lambda Powertools
logger = Logger(service="event_ingestion")
tracer = Tracer(service="event_ingestion")
metrics = Metrics(namespace="ZapierTriggersAPI", service="event_ingestion")

# Initialize FastAPI app
app = FastAPI(
    title="Zapier Triggers API",
    description="Event ingestion API for Zapier trigger workflows",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Initialize services (singleton pattern)
event_service = EventService()
lifecycle_service = EventLifecycleService()
retry_service = RetryService()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors.

    Returns 400 Bad Request with detailed field-level error information.
    """
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    # Extract field-level errors from Pydantic validation
    details = []
    for error in exc.errors():
        field = '.'.join(str(loc) for loc in error['loc'] if loc != 'body')
        message = error['msg']
        details.append(ErrorDetail(field=field, message=message))

    error_response = ErrorResponse(
        error=ErrorInfo(
            code="VALIDATION_ERROR",
            message="Invalid request payload",
            details=details,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            request_id=correlation_id
        )
    )

    logger.warning(
        "Validation error",
        extra={
            "correlation_id": correlation_id,
            "errors": [{"field": d.field, "message": d.message} for d in details]
        }
    )

    metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions.

    Returns 500 Internal Server Error with correlation ID for debugging.
    """
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    logger.error(
        "Unexpected error",
        extra={
            "correlation_id": correlation_id,
            "error": str(exc),
            "error_type": type(exc).__name__
        }
    )

    metrics.add_metric(name="InternalErrors", unit=MetricUnit.Count, value=1)

    error_response = ErrorResponse(
        error=ErrorInfo(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details=None,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            request_id=correlation_id
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )


@app.post(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Event successfully created",
            "model": EventResponse
        },
        400: {
            "description": "Validation error",
            "model": ErrorResponse
        },
        401: {
            "description": "Unauthorized - invalid API key",
            "model": ErrorResponse
        },
        415: {
            "description": "Unsupported Media Type - must be application/json",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Ingest a new event",
    description="Create a new event for triggering Zapier workflows. "
                "Event is persisted to DynamoDB and queued for processing."
)
@tracer.capture_method
@metrics.log_metrics(capture_cold_start_metric=True)
async def create_event(
    event_input: EventInput,
    request: Request
) -> EventResponse:
    """
    Create a new event.

    Args:
        event_input: Validated event input (event_type and payload)
        request: FastAPI request object

    Returns:
        EventResponse with event_id, status, timestamp, and message

    Raises:
        HTTPException: If event creation fails
    """
    start_time = datetime.utcnow()

    # Validate Content-Type header (must be application/json)
    content_type = request.headers.get('content-type', '').lower()
    # Handle content-type with charset (e.g., "application/json; charset=utf-8")
    if not content_type.startswith('application/json'):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json"
        )

    # Extract correlation ID from headers or generate new one
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    # Extract user_id from request context (set by authorizer)
    # For now, use a placeholder until Story 1.3 (authentication) is implemented
    user_id = getattr(request.state, 'user_id', 'anonymous')

    # Extract metadata
    metadata = {
        'source_ip': request.client.host if request.client else 'unknown',
        'user_agent': request.headers.get('User-Agent', 'unknown'),
        'api_version': 'v1'
    }

    logger.info(
        "Processing event ingestion request",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "event_type": event_input.event_type
        }
    )

    try:
        # Create event via service layer
        response = event_service.create_event(
            event_input=event_input,
            user_id=user_id,
            correlation_id=correlation_id,
            metadata=metadata
        )

        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Add metrics
        metrics.add_metric(name="EventsCreated", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name="EventCreationDuration", unit=MetricUnit.Milliseconds, value=duration_ms)

        logger.info(
            "Event created successfully",
            extra={
                "correlation_id": correlation_id,
                "event_id": response.event_id,
                "duration_ms": duration_ms
            }
        )

        return response

    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(
            "AWS service error",
            extra={
                "correlation_id": correlation_id,
                "error_code": error_code,
                "error_message": e.response['Error']['Message']
            }
        )

        metrics.add_metric(name="AWSServiceErrors", unit=MetricUnit.Count, value=1)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service error: {error_code}"
        )

    except Exception as e:
        logger.error(
            "Failed to create event",
            extra={
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

        metrics.add_metric(name="EventCreationErrors", unit=MetricUnit.Count, value=1)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event"
        )


@app.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {
            "description": "Event successfully deleted (no content)"
        },
        401: {
            "description": "Unauthorized - invalid API key",
            "model": ErrorResponse
        },
        404: {
            "description": "Event not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Delete an event",
    description="Permanently delete an event. Requires user ownership verification."
)
@tracer.capture_method
@metrics.log_metrics
async def delete_event(
    event_id: str,
    request: Request
):
    """
    Delete an event permanently.

    Args:
        event_id: Event UUID to delete
        request: FastAPI request object

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 404 if event not found, 401 if unauthorized, 500 on error
    """
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    user_id = getattr(request.state, 'user_id', 'anonymous')

    logger.info(
        "Processing event deletion request",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "event_id": event_id
        }
    )

    try:
        # Delete event via lifecycle service
        deleted = lifecycle_service.delete_event(user_id, event_id)

        if not deleted:
            # Event not found or not owned by user
            logger.warning(
                "Event not found for deletion",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "event_id": event_id
                }
            )

            metrics.add_metric(name="EventNotFound", unit=MetricUnit.Count, value=1)

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Success - log audit trail
        logger.info(
            "Event deleted successfully",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "operation": "event_deleted"
            }
        )

        metrics.add_metric(name="EventsDeleted", unit=MetricUnit.Count, value=1)

        # Return 204 No Content (no response body)
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Failed to delete event",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "error": str(e)
            }
        )

        metrics.add_metric(name="EventDeletionErrors", unit=MetricUnit.Count, value=1)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete event"
        )


@app.post(
    "/events/{event_id}/ack",
    response_model=EventAckResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Event successfully acknowledged",
            "model": EventAckResponse
        },
        401: {
            "description": "Unauthorized - invalid API key",
            "model": ErrorResponse
        },
        404: {
            "description": "Event not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Acknowledge an event",
    description="Mark an event as delivered. Operation is idempotent."
)
@tracer.capture_method
@metrics.log_metrics
async def acknowledge_event(
    event_id: str,
    request: Request
) -> EventAckResponse:
    """
    Acknowledge an event (mark as delivered).

    Args:
        event_id: Event UUID to acknowledge
        request: FastAPI request object

    Returns:
        EventAckResponse with updated event including status='delivered'

    Raises:
        HTTPException: 404 if event not found, 401 if unauthorized, 500 on error
    """
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    user_id = getattr(request.state, 'user_id', 'anonymous')

    logger.info(
        "Processing event acknowledgment request",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "event_id": event_id
        }
    )

    try:
        # Acknowledge event via lifecycle service
        updated_event = lifecycle_service.acknowledge_event(user_id, event_id)

        if not updated_event:
            # Event not found or not owned by user
            logger.warning(
                "Event not found for acknowledgment",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "event_id": event_id
                }
            )

            metrics.add_metric(name="EventNotFound", unit=MetricUnit.Count, value=1)

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Success - log audit trail
        logger.info(
            "Event acknowledged successfully",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "operation": "event_acknowledged"
            }
        )

        metrics.add_metric(name="EventsAcknowledged", unit=MetricUnit.Count, value=1)

        # Return updated event
        return EventAckResponse(
            event_id=updated_event['event_id'],
            event_type=updated_event['event_type'],
            timestamp=updated_event['timestamp'],
            payload=updated_event['payload'],
            status=updated_event['status'],
            delivered_at=updated_event['delivered_at']
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Failed to acknowledge event",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "error": str(e)
            }
        )

        metrics.add_metric(name="EventAcknowledgmentErrors", unit=MetricUnit.Count, value=1)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge event"
        )


@app.get(
    "/events/{event_id}/status",
    response_model=EventStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Event status retrieved successfully",
            "model": EventStatusResponse
        },
        401: {
            "description": "Unauthorized - invalid API key",
            "model": ErrorResponse
        },
        404: {
            "description": "Event not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Get event status",
    description="Retrieve event delivery status and retry metadata"
)
@tracer.capture_method
@metrics.log_metrics
async def get_event_status(
    event_id: str,
    request: Request
) -> EventStatusResponse:
    """
    Get event status metadata.

    Args:
        event_id: Event UUID
        request: FastAPI request object

    Returns:
        EventStatusResponse with status metadata

    Raises:
        HTTPException: 404 if event not found, 401 if unauthorized, 500 on error
    """
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    user_id = getattr(request.state, 'user_id', 'anonymous')

    logger.info(
        "Processing event status request",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "event_id": event_id
        }
    )

    try:
        # Get event status via retry service
        status_info = retry_service.get_event_status(user_id, event_id)

        if not status_info:
            # Event not found or not owned by user
            logger.warning(
                "Event not found for status query",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "event_id": event_id
                }
            )

            metrics.add_metric(name="EventNotFound", unit=MetricUnit.Count, value=1)

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Calculate next_retry_at if event is queued for retry
        next_retry_at = None
        if status_info.get('status') == 'queued' and status_info.get('retry_attempts', 0) < 3:
            retry_attempts = status_info.get('retry_attempts', 0)
            next_delay = retry_service.get_retry_delay(retry_attempts)
            if next_delay and status_info.get('last_retry_at'):
                # Parse last_retry_at and add delay
                from datetime import datetime, timedelta
                try:
                    last_retry = datetime.fromisoformat(status_info['last_retry_at'].replace('Z', '+00:00'))
                    next_retry = last_retry + timedelta(seconds=next_delay)
                    next_retry_at = next_retry.isoformat().replace('+00:00', 'Z')
                except (ValueError, TypeError):
                    pass  # If parsing fails, leave next_retry_at as None

        logger.info(
            "Event status retrieved successfully",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "status": status_info.get('status')
            }
        )

        metrics.add_metric(name="EventStatusQueries", unit=MetricUnit.Count, value=1)

        # Return status response
        return EventStatusResponse(
            event_id=status_info['event_id'],
            status=status_info['status'],
            retry_attempts=status_info.get('retry_attempts', 0),
            last_retry_at=status_info.get('last_retry_at'),
            failed_at=status_info.get('failed_at'),
            delivered_at=status_info.get('delivered_at'),
            next_retry_at=next_retry_at
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Failed to get event status",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "event_id": event_id,
                "error": str(e)
            }
        )

        metrics.add_metric(name="EventStatusQueryErrors", unit=MetricUnit.Count, value=1)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event status"
        )


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns basic health status of the API.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "version": "1.0.0"
    }


# Mangum handler for AWS Lambda
lambda_handler = Mangum(app, lifespan="off")
