"""
Structured JSON Logging Configuration for Zapier Triggers API.

Provides structured logging with correlation IDs for request tracing across services.
All log entries include:
- correlation_id: Request correlation ID (from header or generated)
- request_id: AWS API Gateway request ID
- timestamp: ISO 8601 UTC timestamp
- service: Service name
- path: API path
- method: HTTP method
- status_code: HTTP response code
- duration_ms: Request duration in milliseconds
- user_id: Authenticated user ID or "anonymous"
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps


class StructuredJSONFormatter(logging.Formatter):
    """Custom formatter for structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of log entry
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
            'service': 'zapier-triggers-api',
        }

        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id

        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id

        # Add API path if available
        if hasattr(record, 'path'):
            log_data['path'] = record.path

        # Add HTTP method if available
        if hasattr(record, 'method'):
            log_data['method'] = record.method

        # Add status code if available
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code

        # Add duration if available
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms

        # Add user ID if available
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id

        # Add event ID if available
        if hasattr(record, 'event_id'):
            log_data['event_id'] = record.event_id

        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(level: Optional[str] = None):
    """
    Configure structured JSON logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO in prod, DEBUG in dev.
    """
    # Determine log level
    if level is None:
        environment = os.getenv('ENVIRONMENT', 'dev')
        level = 'DEBUG' if environment == 'dev' else 'INFO'

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    logger.addHandler(handler)

    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class CorrelationIDMiddleware:
    """
    Middleware to extract/generate correlation ID for request tracing.

    Extracts X-Correlation-ID header or generates a new UUID.
    Stores correlation ID in context for use in all logs.
    """

    def __init__(self):
        self.correlation_id: Optional[str] = None
        self.request_id: Optional[str] = None

    def extract_correlation_id(self, headers: Dict[str, str]) -> str:
        """
        Extract correlation ID from headers or generate new one.

        Args:
            headers: HTTP request headers

        Returns:
            Correlation ID string
        """
        # Try to get from X-Correlation-ID header
        correlation_id = headers.get('X-Correlation-ID') or headers.get('x-correlation-id')

        # Generate if not present
        if not correlation_id:
            correlation_id = f"corr-{uuid.uuid4()}"

        self.correlation_id = correlation_id
        return correlation_id

    def extract_request_id(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract AWS request ID from headers.

        Args:
            headers: HTTP request headers

        Returns:
            Request ID or None
        """
        request_id = headers.get('X-Amzn-Request-Id') or headers.get('x-amzn-request-id')
        self.request_id = request_id
        return request_id

    def get_log_context(self) -> Dict[str, Any]:
        """
        Get current logging context with correlation and request IDs.

        Returns:
            Dictionary with correlation_id and request_id
        """
        context = {}
        if self.correlation_id:
            context['correlation_id'] = self.correlation_id
        if self.request_id:
            context['request_id'] = self.request_id
        return context


def with_logging(func):
    """
    Decorator to add structured logging to a function.

    Logs function entry/exit with correlation ID, duration, and any errors.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"Entering {func.__name__}",
                extra={'function': func.__name__}
            )
            result = func(*args, **kwargs)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(
                f"Exiting {func.__name__}",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration_ms, 2)
                }
            )

            return result

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration_ms, 2),
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            raise

    return wrapper
