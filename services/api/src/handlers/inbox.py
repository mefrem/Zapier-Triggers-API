"""
Event Inbox Lambda Handler with FastAPI.

Implements GET /inbox endpoint for retrieving undelivered events with
pagination and filtering.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Query, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from mangum import Mangum
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from models.inbox import InboxResponse, InboxQueryParams
from models.event import ErrorResponse, ErrorInfo, ErrorDetail
from services.inbox_service import InboxService

# Initialize AWS Lambda Powertools
logger = Logger(service="inbox")
tracer = Tracer(service="inbox")
metrics = Metrics(namespace="ZapierTriggersAPI", service="inbox")

# Initialize FastAPI app
app = FastAPI(
    title="Zapier Triggers API - Inbox",
    description="Event inbox retrieval API for Zapier trigger workflows",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Initialize InboxService (singleton pattern)
inbox_service = InboxService()


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
        field = '.'.join(str(loc) for loc in error['loc'] if loc not in ['query', 'body'])
        message = error['msg']
        details.append(ErrorDetail(field=field, message=message))

    error_response = ErrorResponse(
        error=ErrorInfo(
            code="VALIDATION_ERROR",
            message="Invalid query parameters",
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


@app.get(
    "/inbox",
    response_model=InboxResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved inbox events",
            "model": InboxResponse
        },
        400: {
            "description": "Invalid query parameters",
            "model": ErrorResponse
        },
        401: {
            "description": "Unauthorized - invalid API key",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Retrieve undelivered events",
    description="Get list of undelivered events from inbox with pagination and optional filtering by event type."
)
@tracer.capture_method
@metrics.log_metrics(capture_cold_start_metric=True)
async def get_inbox(
    request: Request,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Number of events to return per page (1-100)"
    ),
    cursor: Optional[str] = Query(
        default=None,
        description="Pagination cursor from previous response"
    ),
    event_type: Optional[List[str]] = Query(
        default=None,
        description="Filter by event type(s)"
    )
) -> InboxResponse:
    """
    Retrieve undelivered events from inbox.

    Args:
        request: FastAPI request object
        limit: Number of events to return (1-100, default: 50)
        cursor: Pagination cursor for next page
        event_type: Optional event type filter(s)

    Returns:
        InboxResponse with events and pagination metadata

    Raises:
        HTTPException: If retrieval fails or validation errors occur
    """
    start_time = datetime.utcnow()

    # Extract correlation ID from headers or generate new one
    correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    # Extract user_id from request context (set by authorizer)
    # For now, use a placeholder until Story 1.3 (authentication) is implemented
    user_id = getattr(request.state, 'user_id', 'anonymous')

    # Check for authentication
    # In production, this would be handled by API Gateway Custom Authorizer
    # For now, we'll check if user_id is available in request state
    if not hasattr(request.state, 'user_id') or not request.state.user_id:
        # Check for X-API-Key header as fallback
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            logger.warning(
                "Unauthorized inbox access attempt",
                extra={"correlation_id": correlation_id}
            )

            metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)

            error_response = ErrorResponse(
                error=ErrorInfo(
                    code="UNAUTHORIZED",
                    message="Invalid or missing API key",
                    details=None,
                    timestamp=datetime.utcnow().isoformat() + 'Z',
                    request_id=correlation_id
                )
            )

            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_response.model_dump()
            )

        # For development, use a mock user_id based on API key
        user_id = f"user-{api_key[:8]}"
        request.state.user_id = user_id

    logger.info(
        "Processing inbox request",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "limit": limit,
            "has_cursor": cursor is not None,
            "event_types": event_type
        }
    )

    try:
        # Validate event_type if provided (filter empty strings)
        event_types_filtered = None
        if event_type:
            event_types_filtered = [et.strip() for et in event_type if et and et.strip()]
            if len(event_types_filtered) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="event_type must contain at least one non-empty value"
                )

        # Retrieve events from inbox service
        response = inbox_service.get_inbox_events(
            user_id=user_id,
            limit=limit,
            cursor=cursor,
            event_types=event_types_filtered
        )

        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Add metrics
        metrics.add_metric(name="InboxRequests", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name="InboxRequestDuration", unit=MetricUnit.Milliseconds, value=duration_ms)
        metrics.add_metric(name="EventsReturned", unit=MetricUnit.Count, value=len(response.events))

        logger.info(
            "Inbox events retrieved successfully",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "events_count": len(response.events),
                "has_more": response.pagination.has_more,
                "duration_ms": duration_ms
            }
        )

        return response

    except ValueError as e:
        # Handle validation errors (invalid cursor, invalid parameters)
        logger.warning(
            "Validation error in inbox request",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "error": str(e)
            }
        )

        metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)

        error_response = ErrorResponse(
            error=ErrorInfo(
                code="VALIDATION_ERROR",
                message=str(e),
                details=None,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                request_id=correlation_id
            )
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump()
        )

    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(
            "AWS service error",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "error_code": error_code,
                "error_message": e.response['Error']['Message']
            }
        )

        metrics.add_metric(name="AWSServiceErrors", unit=MetricUnit.Count, value=1)

        error_response = ErrorResponse(
            error=ErrorInfo(
                code="INTERNAL_ERROR",
                message="Service error occurred",
                details=None,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                request_id=correlation_id
            )
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )

    except Exception as e:
        logger.error(
            "Failed to retrieve inbox events",
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

        metrics.add_metric(name="InboxRequestErrors", unit=MetricUnit.Count, value=1)

        error_response = ErrorResponse(
            error=ErrorInfo(
                code="INTERNAL_ERROR",
                message="Failed to retrieve inbox events",
                details=None,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                request_id=correlation_id
            )
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
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
        "service": "inbox",
        "version": "1.0.0"
    }


# Mangum handler for AWS Lambda
lambda_handler = Mangum(app, lifespan="off")
