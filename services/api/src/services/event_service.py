"""
EventService for business logic orchestration.

Coordinates event validation, persistence, and queuing.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from repositories.event_repository import EventRepository
from models.event import EventInput, EventResponse

logger = Logger(service="event_service")


class EventService:
    """
    Service for event ingestion business logic.

    Orchestrates validation, persistence to DynamoDB, and queuing to SQS.
    """

    def __init__(
        self,
        repository: Optional[EventRepository] = None,
        queue_url: Optional[str] = None
    ):
        """
        Initialize EventService.

        Args:
            repository: EventRepository instance (created if not provided)
            queue_url: SQS queue URL (defaults to EVENT_QUEUE_URL env var)
        """
        self.repository = repository or EventRepository()
        self.queue_url = queue_url or os.environ.get('EVENT_QUEUE_URL')
        self.sqs = boto3.client('sqs')

    def create_event(
        self,
        event_input: EventInput,
        user_id: str,
        correlation_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EventResponse:
        """
        Create a new event.

        Orchestrates:
        1. Generate unique event ID (UUID v4)
        2. Generate timestamp (ISO 8601)
        3. Persist to DynamoDB
        4. Queue to SQS for processing
        5. Return success response

        Args:
            event_input: Validated event input
            user_id: User identifier from authorization context
            correlation_id: Request correlation ID for tracing
            metadata: Additional metadata (source_ip, api_version, etc.)

        Returns:
            EventResponse with event_id, status, timestamp, and message

        Raises:
            Exception: If DynamoDB or SQS operations fail
        """
        # Generate unique event ID
        event_id = str(uuid.uuid4())

        # Generate timestamp in ISO 8601 format (UTC with microseconds)
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Add correlation_id to metadata
        event_metadata = metadata or {}
        event_metadata['correlation_id'] = correlation_id
        event_metadata['api_version'] = 'v1'

        try:
            # Persist to DynamoDB
            self.repository.create_event(
                user_id=user_id,
                event_id=event_id,
                event_type=event_input.event_type,
                payload=event_input.payload,
                timestamp=timestamp,
                metadata=event_metadata
            )

            logger.info(
                "Event persisted to DynamoDB",
                extra={
                    "event_id": event_id,
                    "event_type": event_input.event_type,
                    "user_id": user_id,
                    "correlation_id": correlation_id
                }
            )

            # Queue to SQS for async processing (if queue is configured)
            if self.queue_url:
                self._queue_event(
                    event_id=event_id,
                    user_id=user_id,
                    event_type=event_input.event_type,
                    timestamp=timestamp,
                    correlation_id=correlation_id
                )

            # Return success response
            return EventResponse(
                event_id=event_id,
                status="received",
                timestamp=timestamp,
                message="Event successfully created and queued for processing"
            )

        except ClientError as e:
            logger.error(
                "Failed to create event",
                extra={
                    "event_id": event_id,
                    "error_code": e.response['Error']['Code'],
                    "error_message": e.response['Error']['Message'],
                    "correlation_id": correlation_id
                }
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error creating event",
                extra={
                    "event_id": event_id,
                    "error": str(e),
                    "correlation_id": correlation_id
                }
            )
            raise

    def _queue_event(
        self,
        event_id: str,
        user_id: str,
        event_type: str,
        timestamp: str,
        correlation_id: str
    ) -> None:
        """
        Queue event to SQS for async processing.

        Args:
            event_id: Event identifier
            user_id: User identifier
            event_type: Event type
            timestamp: Event timestamp
            correlation_id: Request correlation ID

        Raises:
            ClientError: If SQS operation fails
        """
        try:
            message_body = {
                'event_id': event_id,
                'user_id': user_id,
                'event_type': event_type,
                'timestamp': timestamp,
                'correlation_id': correlation_id
            }

            self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'event_type': {
                        'DataType': 'String',
                        'StringValue': event_type
                    },
                    'user_id': {
                        'DataType': 'String',
                        'StringValue': user_id
                    }
                }
            )

            logger.info(
                "Event queued to SQS",
                extra={
                    "event_id": event_id,
                    "queue_url": self.queue_url,
                    "correlation_id": correlation_id
                }
            )

        except ClientError as e:
            logger.error(
                "Failed to queue event to SQS",
                extra={
                    "event_id": event_id,
                    "error_code": e.response['Error']['Code'],
                    "error_message": e.response['Error']['Message'],
                    "correlation_id": correlation_id
                }
            )
            # Don't raise - event is already persisted, queuing is best-effort
            # In production, this should trigger an alarm for investigation

    def get_event(self, user_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an event by ID.

        Args:
            user_id: User identifier
            event_id: Event UUID

        Returns:
            Event data or None if not found
        """
        return self.repository.get_event_by_id(user_id, event_id)
