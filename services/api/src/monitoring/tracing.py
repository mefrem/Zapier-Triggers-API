"""
AWS X-Ray Distributed Tracing Configuration for Zapier Triggers API.

Enables distributed tracing across Lambda, API Gateway, DynamoDB, and SQS.
Captures request paths, service latencies, errors, and correlation IDs.

Sampling: 1% in prod (cost optimization), 100% in dev/staging (visibility).
"""

import os
from functools import wraps
from typing import Optional

try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False
    print("Warning: aws-xray-sdk not installed. X-Ray tracing disabled.")


def configure_xray(service_name: str = "zapier-triggers-api"):
    """
    Configure AWS X-Ray tracing for the application.

    Args:
        service_name: Name of the service for X-Ray service map
    """
    if not XRAY_AVAILABLE:
        return

    # Set service name
    xray_recorder.configure(service=service_name)

    # Automatically trace boto3 calls (DynamoDB, SQS, etc.)
    patch_all()

    # Set sampling rate based on environment
    environment = os.getenv('ENVIRONMENT', 'dev')
    if environment == 'prod':
        # 1% sampling in production
        sampling_rate = 0.01
    else:
        # 100% sampling in dev/staging
        sampling_rate = 1.0

    # Note: Actual sampling rules configured in X-Ray console or via API
    # This is just for local testing
    os.environ['AWS_XRAY_TRACING_NAME'] = service_name


def get_xray_recorder():
    """Get the X-Ray recorder instance."""
    if XRAY_AVAILABLE:
        return xray_recorder
    return None


def trace_operation(operation_name: Optional[str] = None):
    """
    Decorator to create X-Ray subsegment for a function.

    Args:
        operation_name: Name of the operation (defaults to function name)

    Usage:
        @trace_operation('authenticate_user')
        def authenticate_user(api_key: str):
            # Authentication logic
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not XRAY_AVAILABLE:
                return func(*args, **kwargs)

            name = operation_name or func.__name__

            with xray_recorder.capture(name) as subsegment:
                try:
                    # Add function metadata
                    subsegment.put_metadata('function', func.__name__)
                    subsegment.put_metadata('module', func.__module__)

                    # Execute function
                    result = func(*args, **kwargs)

                    # Mark as successful
                    subsegment.put_annotation('status', 'success')

                    return result

                except Exception as e:
                    # Mark as failed and capture error
                    subsegment.put_annotation('status', 'error')
                    subsegment.put_annotation('error_type', type(e).__name__)
                    subsegment.put_metadata('error_message', str(e))
                    raise

        return wrapper
    return decorator


def add_trace_annotation(key: str, value: str):
    """
    Add annotation to current X-Ray segment (searchable in X-Ray console).

    Args:
        key: Annotation key
        value: Annotation value
    """
    if XRAY_AVAILABLE:
        xray_recorder.put_annotation(key, value)


def add_trace_metadata(key: str, value):
    """
    Add metadata to current X-Ray segment (not searchable, but visible in trace).

    Args:
        key: Metadata key
        value: Metadata value (any JSON-serializable object)
    """
    if XRAY_AVAILABLE:
        xray_recorder.put_metadata(key, value)


def start_segment(name: str):
    """
    Manually start an X-Ray segment.

    Args:
        name: Segment name
    """
    if XRAY_AVAILABLE:
        return xray_recorder.begin_segment(name)
    return None


def end_segment():
    """Manually end the current X-Ray segment."""
    if XRAY_AVAILABLE:
        xray_recorder.end_segment()
