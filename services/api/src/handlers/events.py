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

from models.event import EventInput, EventResponse, ErrorResponse, ErrorInfo, ErrorDetail
from services.event_service import EventService

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

# Initialize EventService (singleton pattern)
event_service = EventService()


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
