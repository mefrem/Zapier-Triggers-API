"""
EventRepository for DynamoDB operations.

Handles persistence and retrieval of events in DynamoDB.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

logger = Logger(service="event_repository")


class EventRepository:
    """
    Repository for event persistence in DynamoDB.

    Handles all DynamoDB operations for events including create, read, update.
    """

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize EventRepository.

        Args:
            table_name: DynamoDB table name (defaults to EVENTS_TABLE_NAME env var)
        """
        self.table_name = table_name or os.environ.get('EVENTS_TABLE_NAME')
        if not self.table_name:
            raise ValueError("EVENTS_TABLE_NAME must be set")

        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(self.table_name)

    def create_event(
        self,
        user_id: str,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        timestamp: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new event in DynamoDB.

        Args:
            user_id: User identifier (partition key)
            event_id: Unique event identifier (UUID v4)
            event_type: Event type identifier
            payload: Event payload data
            timestamp: ISO 8601 timestamp
            metadata: Optional metadata (source_ip, api_version, correlation_id)

        Returns:
            Created event item

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # Calculate TTL (30 days from now)
            ttl = int(time.time()) + (30 * 24 * 60 * 60)

            # Construct composite sort key
            timestamp_event_id = f"{timestamp}#{event_id}"

            # Construct item
            item = {
                'user_id': user_id,
                'timestamp#event_id': timestamp_event_id,
                'event_id': event_id,
                'event_type': event_type,
                'payload': payload,
                'status': 'received',
                'timestamp': timestamp,
                'ttl': ttl,
                'retry_count': 0,
                'metadata': metadata or {},
                'event_type#timestamp': f"{event_type}#{timestamp}",
                'status#timestamp': f"received#{timestamp}"
            }

            # Write to DynamoDB
            self.table.put_item(Item=item)

            logger.info(
                "Event created in DynamoDB",
                extra={
                    "event_id": event_id,
                    "user_id": user_id,
                    "event_type": event_type
                }
            )

            return item

        except ClientError as e:
            logger.error(
                "Failed to create event in DynamoDB",
                extra={
                    "event_id": event_id,
                    "error_code": e.response['Error']['Code'],
                    "error_message": e.response['Error']['Message']
                }
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error creating event",
                extra={"event_id": event_id, "error": str(e)}
            )
            raise

    def get_event(self, user_id: str, timestamp_event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an event by user_id and composite sort key.

        Args:
            user_id: User identifier
            timestamp_event_id: Composite sort key (timestamp#event_id)

        Returns:
            Event item or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'user_id': user_id,
                    'timestamp#event_id': timestamp_event_id
                }
            )
            return response.get('Item')

        except ClientError as e:
            logger.error(
                "Failed to get event from DynamoDB",
                extra={
                    "user_id": user_id,
                    "timestamp_event_id": timestamp_event_id,
                    "error_code": e.response['Error']['Code']
                }
            )
            raise

    def get_event_by_id(self, user_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an event by user_id and event_id.

        Since event_id is the suffix in the composite sort key (timestamp#event_id),
        we query by user_id and filter results in memory to find matching event_id.

        Args:
            user_id: User identifier
            event_id: Event UUID

        Returns:
            Event item or None if not found
        """
        try:
            # Query all events for user (we can't use begins_with since event_id is suffix)
            # In production, consider adding a GSI with event_id as partition key
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id),
                # Limit to recent 100 events; in practice, should find event quickly
                Limit=100
            )

            # Filter results to find matching event_id
            items = response.get('Items', [])
            for item in items:
                if item.get('event_id') == event_id:
                    return item

            # If not found in first batch and there's more data, continue querying
            while 'LastEvaluatedKey' in response and len(items) < 1000:
                response = self.table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id),
                    ExclusiveStartKey=response['LastEvaluatedKey'],
                    Limit=100
                )
                items = response.get('Items', [])
                for item in items:
                    if item.get('event_id') == event_id:
                        return item

            return None

        except ClientError as e:
            logger.error(
                "Failed to query event from DynamoDB",
                extra={
                    "user_id": user_id,
                    "event_id": event_id,
                    "error_code": e.response['Error']['Code']
                }
            )
            raise

    def update_event_status(
        self,
        user_id: str,
        timestamp_event_id: str,
        status: str,
        retry_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update event status and optionally retry count.

        Args:
            user_id: User identifier
            timestamp_event_id: Composite sort key
            status: New status value
            retry_count: Optional new retry count

        Returns:
            Updated event item

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            update_expression = "SET #status = :status"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {":status": status}

            if retry_count is not None:
                update_expression += ", retry_count = :retry_count"
                expression_attribute_values[":retry_count"] = retry_count

            response = self.table.update_item(
                Key={
                    'user_id': user_id,
                    'timestamp#event_id': timestamp_event_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )

            logger.info(
                "Event status updated",
                extra={
                    "user_id": user_id,
                    "timestamp_event_id": timestamp_event_id,
                    "status": status
                }
            )

            return response.get('Attributes', {})

        except ClientError as e:
            logger.error(
                "Failed to update event status",
                extra={
                    "user_id": user_id,
                    "timestamp_event_id": timestamp_event_id,
                    "error_code": e.response['Error']['Code']
                }
            )
            raise

    def query_by_status(
        self,
        user_id: str,
        status: str = 'received',
        limit: int = 50,
        last_evaluated_key: Optional[Dict[str, Any]] = None,
        event_types: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], int]:
        """
        Query events by user_id and status using StatusIndex GSI.

        Args:
            user_id: User identifier
            status: Event status (default: 'received')
            limit: Maximum number of items to return (1-100)
            last_evaluated_key: DynamoDB pagination key from previous query
            event_types: Optional list of event types to filter

        Returns:
            Tuple of (events list, last_evaluated_key for pagination, total_count)

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # Build query parameters
            query_params = {
                'IndexName': 'StatusIndex',
                'KeyConditionExpression': Key('user_id').eq(user_id) & Key('status#timestamp').begins_with(f'{status}#'),
                'Limit': limit + 1,  # Request one extra to determine if more results exist
                'ScanIndexForward': True,  # Ascending order (oldest first)
                'ProjectionExpression': 'event_id, event_type, #ts, payload',
                'ExpressionAttributeNames': {
                    '#ts': 'timestamp'
                }
            }

            # Add pagination key if provided
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key

            # Execute query
            response = self.table.query(**query_params)

            items = response.get('Items', [])

            # Check if there are more results
            has_more = len(items) > limit
            if has_more:
                items = items[:limit]  # Remove the extra item
                next_key = {
                    'user_id': items[-1]['user_id'],
                    'timestamp#event_id': items[-1]['timestamp#event_id'],
                    'status#timestamp': items[-1].get('status#timestamp', f"{status}#{items[-1]['timestamp']}")
                }
            else:
                next_key = None

            # Filter by event_types if provided
            if event_types:
                items = [item for item in items if item.get('event_type') in event_types]

            # Get total count (approximation for now)
            # For exact count, we'd need to scan entire result set which is expensive
            # For MVP, we return count of items in current page
            total_count = len(items)

            logger.info(
                "Queried events by status",
                extra={
                    "user_id": user_id,
                    "status": status,
                    "items_returned": len(items),
                    "has_more": has_more
                }
            )

            return items, next_key, total_count

        except ClientError as e:
            logger.error(
                "Failed to query events by status",
                extra={
                    "user_id": user_id,
                    "status": status,
                    "error_code": e.response['Error']['Code'],
                    "error_message": e.response['Error']['Message']
                }
            )
            raise

    def query_by_status_with_cursor(
        self,
        user_id: str,
        status: str = 'received',
        limit: int = 50,
        cursor_timestamp: Optional[str] = None,
        cursor_event_id: Optional[str] = None,
        event_types: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Query events by status with cursor-based pagination.

        Args:
            user_id: User identifier
            status: Event status (default: 'received')
            limit: Maximum number of items to return
            cursor_timestamp: Timestamp from pagination cursor
            cursor_event_id: Event ID from pagination cursor
            event_types: Optional list of event types to filter

        Returns:
            Tuple of (events list, has_more boolean)

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # Build last_evaluated_key from cursor if provided
            last_evaluated_key = None
            if cursor_timestamp and cursor_event_id:
                last_evaluated_key = {
                    'user_id': user_id,
                    'timestamp#event_id': f"{cursor_timestamp}#{cursor_event_id}",
                    'status#timestamp': f"{status}#{cursor_timestamp}"
                }

            # Query using existing method
            items, next_key, _ = self.query_by_status(
                user_id=user_id,
                status=status,
                limit=limit,
                last_evaluated_key=last_evaluated_key,
                event_types=event_types
            )

            has_more = next_key is not None

            return items, has_more

        except ClientError as e:
            logger.error(
                "Failed to query events with cursor",
                extra={
                    "user_id": user_id,
                    "status": status,
                    "error_code": e.response['Error']['Code']
                }
            )
            raise

    def count_events_by_status(
        self,
        user_id: str,
        status: str = 'received',
        event_types: Optional[List[str]] = None
    ) -> int:
        """
        Count total events for user with given status.

        Note: This performs a full query and counts items, which can be expensive.
        For large result sets, consider caching or approximating.

        Args:
            user_id: User identifier
            status: Event status
            event_types: Optional list of event types to filter

        Returns:
            Total count of matching events
        """
        try:
            count = 0
            last_evaluated_key = None

            while True:
                items, last_evaluated_key, _ = self.query_by_status(
                    user_id=user_id,
                    status=status,
                    limit=100,
                    last_evaluated_key=last_evaluated_key,
                    event_types=event_types
                )

                count += len(items)

                if not last_evaluated_key:
                    break

                # Safety limit to prevent infinite loops
                if count > 10000:
                    logger.warning(
                        "Count exceeded safety limit",
                        extra={"user_id": user_id, "status": status}
                    )
                    break

            return count

        except ClientError as e:
            logger.error(
                "Failed to count events",
                extra={
                    "user_id": user_id,
                    "status": status,
                    "error_code": e.response['Error']['Code']
                }
            )
            raise
