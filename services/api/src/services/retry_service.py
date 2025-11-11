"""
RetryService for managing event retry logic and status tracking.

Handles retry scheduling, failure marking, and status queries with exponential backoff.
"""

import os
from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger

from repositories.event_repository import EventRepository

logger = Logger(service="retry_service")


class RetryService:
    """
    Service for event retry and status tracking.

    Implements exponential backoff (1min, 5min, 15min) and permanent failure marking.
    """

    # Retry delays in seconds: [1 minute, 5 minutes, 15 minutes]
    RETRY_DELAYS = [60, 300, 900]
    MAX_RETRY_ATTEMPTS = 3

    def __init__(self, repository: Optional[EventRepository] = None):
        """
        Initialize RetryService.

        Args:
            repository: EventRepository instance (optional, creates new if not provided)
        """
        self.repository = repository or EventRepository()

    def get_retry_delay(self, retry_attempts: int) -> Optional[int]:
        """
        Calculate retry delay based on attempt count (exponential backoff).

        Args:
            retry_attempts: Current retry attempt count (0-indexed)

        Returns:
            Delay in seconds, or None if max attempts exceeded
        """
        if retry_attempts >= self.MAX_RETRY_ATTEMPTS:
            return None

        return self.RETRY_DELAYS[retry_attempts]

    def schedule_retry(
        self,
        user_id: str,
        event_id: str,
        error_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Schedule a retry for a failed event delivery attempt.

        Increments retry_attempts counter and determines next action:
        - If retry_attempts < 3: Update retry metadata and return delay
        - If retry_attempts >= 3: Mark event as permanently failed

        Args:
            user_id: User identifier
            event_id: Event UUID
            error_message: Optional error message from failed delivery

        Returns:
            Dict with retry info, or None if event not found
            Format: {
                'event_id': str,
                'retry_attempts': int,
                'next_retry_delay': int (seconds) or None if max attempts,
                'status': 'queued' or 'failed'
            }

        Raises:
            Exception: If DynamoDB operation fails
        """
        try:
            logger.info(
                "Scheduling retry for event",
                extra={"user_id": user_id, "event_id": event_id}
            )

            # Get current event to determine retry attempts
            status_info = self.repository.get_event_status(user_id, event_id)

            if not status_info:
                logger.warning(
                    "Event not found for retry scheduling",
                    extra={"user_id": user_id, "event_id": event_id}
                )
                return None

            current_attempts = status_info.get('retry_attempts', 0)
            new_attempts = current_attempts + 1

            # Check if max retries exceeded
            if new_attempts >= self.MAX_RETRY_ATTEMPTS:
                logger.info(
                    "Max retries exceeded, marking event as failed",
                    extra={
                        "user_id": user_id,
                        "event_id": event_id,
                        "retry_attempts": new_attempts
                    }
                )

                # Mark as permanently failed
                updated_event = self.mark_failed(
                    user_id=user_id,
                    event_id=event_id,
                    failure_reason=error_message or "Max retry attempts exceeded"
                )

                if not updated_event:
                    return None

                return {
                    'event_id': event_id,
                    'retry_attempts': new_attempts,
                    'next_retry_delay': None,
                    'status': 'failed'
                }

            # Update retry attempts and schedule next retry
            updated_event = self.repository.update_retry_attempts(
                user_id=user_id,
                event_id=event_id,
                retry_attempts=new_attempts,
                last_error=error_message
            )

            if not updated_event:
                return None

            next_delay = self.get_retry_delay(new_attempts)

            logger.info(
                "Retry scheduled successfully",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "retry_attempts": new_attempts,
                    "next_retry_delay_seconds": next_delay,
                    "event": "delivery_failure"
                }
            )

            return {
                'event_id': event_id,
                'retry_attempts': new_attempts,
                'next_retry_delay': next_delay,
                'status': 'queued'
            }

        except Exception as e:
            logger.error(
                "Failed to schedule retry",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error": str(e)
                }
            )
            raise

    def mark_failed(
        self,
        user_id: str,
        event_id: str,
        failure_reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Mark an event as permanently failed.

        Sets status to 'failed' and records failure timestamp.

        Args:
            user_id: User identifier
            event_id: Event UUID
            failure_reason: Optional reason for permanent failure

        Returns:
            Updated event dict with status='failed', or None if event not found

        Raises:
            Exception: If DynamoDB operation fails
        """
        try:
            logger.info(
                "Marking event as permanently failed",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "failure_reason": failure_reason
                }
            )

            updated_event = self.repository.mark_as_failed(
                user_id=user_id,
                event_id=event_id,
                failure_reason=failure_reason
            )

            if not updated_event:
                logger.warning(
                    "Event not found for failure marking",
                    extra={"user_id": user_id, "event_id": event_id}
                )
                return None

            logger.info(
                "Event marked as failed successfully",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "status": "failed"
                }
            )

            return updated_event

        except Exception as e:
            logger.error(
                "Failed to mark event as failed",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error": str(e)
                }
            )
            raise

    def get_event_status(
        self,
        user_id: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get event status metadata.

        Args:
            user_id: User identifier
            event_id: Event UUID

        Returns:
            Dict with status info, or None if event not found
            Format: {
                'event_id': str,
                'status': str,
                'retry_attempts': int,
                'last_retry_at': str (ISO 8601) or None,
                'failed_at': str (ISO 8601) or None,
                'delivered_at': str (ISO 8601) or None,
                'last_error': str or None
            }

        Raises:
            Exception: If DynamoDB operation fails
        """
        try:
            logger.info(
                "Getting event status",
                extra={"user_id": user_id, "event_id": event_id}
            )

            status_info = self.repository.get_event_status(user_id, event_id)

            if not status_info:
                logger.info(
                    "Event not found for status query",
                    extra={"user_id": user_id, "event_id": event_id}
                )
                return None

            logger.info(
                "Retrieved event status",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "status": status_info.get('status')
                }
            )

            return status_info

        except Exception as e:
            logger.error(
                "Failed to get event status",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error": str(e)
                }
            )
            raise
