"""
EventLifecycleService for managing event acknowledgment and deletion.

Handles business logic for event lifecycle operations including acknowledgment
and deletion with user ownership verification.
"""

from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger

from repositories.event_repository import EventRepository

logger = Logger(service="event_lifecycle_service")


class EventLifecycleService:
    """
    Service for event lifecycle operations.

    Handles acknowledgment and deletion of events with user ownership checks.
    """

    def __init__(self, repository: Optional[EventRepository] = None):
        """
        Initialize EventLifecycleService.

        Args:
            repository: EventRepository instance (optional, creates new if not provided)
        """
        self.repository = repository or EventRepository()

    def acknowledge_event(
        self,
        user_id: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Acknowledge an event by marking it as delivered.

        This operation:
        - Verifies user ownership
        - Updates status to 'delivered'
        - Sets delivered_at timestamp
        - Is idempotent (safe to call multiple times)

        Args:
            user_id: Authenticated user ID
            event_id: Event UUID to acknowledge

        Returns:
            Updated event dict with status='delivered', or None if event not found

        Raises:
            Exception: If DynamoDB operation fails
        """
        try:
            logger.info(
                "Acknowledging event",
                extra={"user_id": user_id, "event_id": event_id}
            )

            # Repository method handles ownership verification and update
            updated_event = self.repository.acknowledge_event(user_id, event_id)

            if not updated_event:
                logger.warning(
                    "Event not found or not owned by user",
                    extra={"user_id": user_id, "event_id": event_id}
                )
                return None

            logger.info(
                "Event acknowledged successfully",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "status": updated_event.get('status')
                }
            )

            return updated_event

        except Exception as e:
            logger.error(
                "Failed to acknowledge event",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error": str(e)
                }
            )
            raise

    def delete_event(
        self,
        user_id: str,
        event_id: str
    ) -> bool:
        """
        Permanently delete an event.

        This operation:
        - Verifies user ownership
        - Permanently removes event from DynamoDB
        - Cannot be undone

        Args:
            user_id: Authenticated user ID
            event_id: Event UUID to delete

        Returns:
            True if event was deleted, False if event not found

        Raises:
            Exception: If DynamoDB operation fails
        """
        try:
            logger.info(
                "Deleting event",
                extra={"user_id": user_id, "event_id": event_id}
            )

            # Repository method handles ownership verification and deletion
            deleted = self.repository.delete_event(user_id, event_id)

            if not deleted:
                logger.warning(
                    "Event not found or not owned by user",
                    extra={"user_id": user_id, "event_id": event_id}
                )
                return False

            logger.info(
                "Event deleted successfully",
                extra={"user_id": user_id, "event_id": event_id}
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to delete event",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error": str(e)
                }
            )
            raise
