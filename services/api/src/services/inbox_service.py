"""
InboxService for event inbox retrieval.

Orchestrates business logic for querying undelivered events with pagination and filtering.
"""

from typing import List, Optional, Tuple
from aws_lambda_powertools import Logger

from models.inbox import EventItem, InboxResponse, PaginationInfo
from repositories.event_repository import EventRepository
from utils.pagination import PaginationCursor

logger = Logger(service="inbox_service")


class InboxService:
    """
    Service for inbox operations.

    Handles event retrieval with pagination, filtering, and cursor management.
    """

    def __init__(self, repository: Optional[EventRepository] = None):
        """
        Initialize InboxService.

        Args:
            repository: EventRepository instance (creates new one if not provided)
        """
        self.repository = repository or EventRepository()
        self.cursor_util = PaginationCursor()

    def get_inbox_events(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        status: str = 'received'
    ) -> InboxResponse:
        """
        Retrieve events for a user filtered by status.

        Args:
            user_id: User identifier
            limit: Maximum number of events to return (1-100)
            cursor: Pagination cursor from previous request
            event_types: Optional list of event types to filter
            status: Event status to filter ('received' or 'failed', default: 'received')

        Returns:
            InboxResponse with events and pagination metadata

        Raises:
            ValueError: If cursor is invalid or parameters are out of range
        """
        try:
            # Validate limit
            if limit < 1 or limit > 100:
                raise ValueError("limit must be between 1 and 100")

            # Validate status
            valid_statuses = ['received', 'failed', 'queued', 'delivered']
            if status not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")

            # Parse cursor if provided
            cursor_timestamp = None
            cursor_event_id = None
            if cursor:
                try:
                    cursor_timestamp, cursor_event_id = self.cursor_util.decode_cursor(
                        cursor,
                        user_id
                    )
                    logger.info(
                        "Cursor parsed successfully",
                        extra={
                            "user_id": user_id,
                            "cursor_timestamp": cursor_timestamp,
                            "cursor_event_id": cursor_event_id
                        }
                    )
                except ValueError as e:
                    logger.warning(
                        "Invalid cursor provided",
                        extra={"user_id": user_id, "error": str(e)}
                    )
                    raise ValueError(f"Invalid cursor: {str(e)}")

            # Query events from repository
            logger.info(
                "Querying inbox events",
                extra={
                    "user_id": user_id,
                    "status": status,
                    "limit": limit,
                    "has_cursor": cursor is not None,
                    "event_types": event_types
                }
            )

            events_data, has_more = self.repository.query_by_status_with_cursor(
                user_id=user_id,
                status=status,
                limit=limit,
                cursor_timestamp=cursor_timestamp,
                cursor_event_id=cursor_event_id,
                event_types=event_types
            )

            # Transform repository data to EventItem models
            events = self._transform_events(events_data)

            # Generate next cursor if there are more results
            next_cursor = None
            if has_more and len(events) > 0:
                last_event = events_data[-1]
                next_cursor = self.cursor_util.encode_cursor(
                    timestamp=last_event['timestamp'],
                    event_id=last_event['event_id'],
                    user_id=user_id
                )

            # Get total count (for now, use count of current result set)
            # In production, this could be cached or approximated for performance
            total_count = self.repository.count_events_by_status(
                user_id=user_id,
                status=status,
                event_types=event_types
            )

            # Build pagination info
            pagination = PaginationInfo(
                limit=limit,
                cursor=next_cursor,
                has_more=has_more,
                total_count=total_count
            )

            logger.info(
                "Inbox events retrieved successfully",
                extra={
                    "user_id": user_id,
                    "events_count": len(events),
                    "has_more": has_more,
                    "total_count": total_count
                }
            )

            return InboxResponse(
                events=events,
                pagination=pagination
            )

        except ValueError:
            # Re-raise validation errors
            raise

        except Exception as e:
            logger.error(
                "Failed to retrieve inbox events",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise

    def _transform_events(self, events_data: List[dict]) -> List[EventItem]:
        """
        Transform repository event data to EventItem models.

        Args:
            events_data: Raw event data from repository

        Returns:
            List of EventItem models with only public fields
        """
        events = []
        for event_data in events_data:
            event_item = EventItem(
                event_id=event_data['event_id'],
                event_type=event_data['event_type'],
                timestamp=event_data['timestamp'],
                payload=event_data['payload']
            )
            events.append(event_item)

        return events
