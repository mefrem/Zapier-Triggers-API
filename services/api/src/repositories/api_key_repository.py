"""
API Key Repository

Data access layer for API key management in DynamoDB.
"""

import os
import uuid
import secrets
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

from src.models.api_key import APIKey


class APIKeyRepository:
    """Repository for API key operations with DynamoDB."""

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize the API Key repository.

        Args:
            table_name: DynamoDB table name (defaults to environment variable)
        """
        self.table_name = table_name or os.environ.get('API_KEYS_TABLE_NAME', '')
        if not self.table_name:
            raise ValueError("API_KEYS_TABLE_NAME environment variable must be set")

        self.dynamodb = boto3.client('dynamodb')

    def create(
        self,
        user_id: str,
        name: str,
        rate_limit: int = 1000,
        expires_at: Optional[str] = None,
        scopes: Optional[List[str]] = None
    ) -> tuple[APIKey, str]:
        """
        Create a new API key.

        Args:
            user_id: Zapier developer/integration ID
            name: Human-readable key name
            rate_limit: Requests per minute
            expires_at: ISO 8601 expiration timestamp (optional)
            scopes: Permission scopes (optional)

        Returns:
            Tuple of (APIKey model, actual API key string)
            The actual key is returned only once and never stored
        """
        # Generate unique identifiers
        key_id = str(uuid.uuid4())

        # Generate random 32-character API key with prefix
        # Format: zap_<32 random hex characters>
        random_key = secrets.token_hex(16)  # 16 bytes = 32 hex characters
        api_key = f"zap_{random_key}"

        # Hash the API key (SHA-256)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Set defaults
        if scopes is None:
            scopes = ["events:write"]

        # Create timestamp
        created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Store in DynamoDB
        item = {
            'user_id': {'S': user_id},
            'key_id': {'S': key_id},
            'key_hash': {'S': key_hash},
            'name': {'S': name},
            'created_at': {'S': created_at},
            'rate_limit': {'N': str(rate_limit)},
            'is_active': {'BOOL': True},
            'scopes': {'SS': scopes}
        }

        if expires_at:
            item['expires_at'] = {'S': expires_at}

        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item=item,
                ConditionExpression='attribute_not_exists(user_id) AND attribute_not_exists(key_id)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"API key already exists: {key_id}")
            raise

        # Create APIKey model
        api_key_model = APIKey(
            key_id=key_id,
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            created_at=created_at,
            last_used_at=None,
            expires_at=expires_at,
            rate_limit=rate_limit,
            is_active=True,
            scopes=scopes
        )

        return api_key_model, api_key

    def get_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """
        Get API key by hash using KeyHashIndex GSI.

        Args:
            key_hash: SHA-256 hash of the API key

        Returns:
            APIKey model if found, None otherwise
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='KeyHashIndex',
                KeyConditionExpression='key_hash = :key_hash',
                ExpressionAttributeValues={
                    ':key_hash': {'S': key_hash}
                },
                Limit=1
            )

            items = response.get('Items', [])
            if not items:
                return None

            return self._parse_dynamodb_item(items[0])

        except ClientError as e:
            print(f"Error querying API key by hash: {e}")
            return None

    def get_by_id(self, user_id: str, key_id: str) -> Optional[APIKey]:
        """
        Get API key by user_id and key_id.

        Args:
            user_id: User identifier
            key_id: Key identifier

        Returns:
            APIKey model if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': user_id},
                    'key_id': {'S': key_id}
                }
            )

            item = response.get('Item')
            if not item:
                return None

            return self._parse_dynamodb_item(item)

        except ClientError as e:
            print(f"Error getting API key: {e}")
            return None

    def update_last_used(self, user_id: str, key_id: str) -> bool:
        """
        Update the last_used_at timestamp for an API key.

        Args:
            user_id: User identifier
            key_id: Key identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': user_id},
                    'key_id': {'S': key_id}
                },
                UpdateExpression='SET last_used_at = :timestamp',
                ExpressionAttributeValues={
                    ':timestamp': {'S': timestamp}
                }
            )
            return True

        except ClientError as e:
            print(f"Error updating last_used_at: {e}")
            return False

    def list_by_user(self, user_id: str) -> List[APIKey]:
        """
        List all API keys for a user.

        Args:
            user_id: User identifier

        Returns:
            List of APIKey models
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={
                    ':user_id': {'S': user_id}
                }
            )

            items = response.get('Items', [])
            return [self._parse_dynamodb_item(item) for item in items]

        except ClientError as e:
            print(f"Error listing API keys: {e}")
            return []

    def revoke(self, user_id: str, key_id: str) -> bool:
        """
        Revoke an API key (soft delete by setting is_active to False).

        Args:
            user_id: User identifier
            key_id: Key identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': user_id},
                    'key_id': {'S': key_id}
                },
                UpdateExpression='SET is_active = :inactive',
                ExpressionAttributeValues={
                    ':inactive': {'BOOL': False}
                },
                ConditionExpression='attribute_exists(user_id) AND attribute_exists(key_id)'
            )
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"API key not found: {key_id}")
                return False
            print(f"Error revoking API key: {e}")
            return False

    def update(self, user_id: str, key_id: str, name: Optional[str] = None, rate_limit: Optional[int] = None) -> bool:
        """
        Update API key metadata.

        Args:
            user_id: User identifier
            key_id: Key identifier
            name: New name (optional)
            rate_limit: New rate limit (optional)

        Returns:
            True if successful, False otherwise
        """
        update_expressions = []
        expression_values = {}

        if name is not None:
            update_expressions.append('name = :name')
            expression_values[':name'] = {'S': name}

        if rate_limit is not None:
            update_expressions.append('rate_limit = :rate_limit')
            expression_values[':rate_limit'] = {'N': str(rate_limit)}

        if not update_expressions:
            return True  # Nothing to update

        try:
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={
                    'user_id': {'S': user_id},
                    'key_id': {'S': key_id}
                },
                UpdateExpression='SET ' + ', '.join(update_expressions),
                ExpressionAttributeValues=expression_values,
                ConditionExpression='attribute_exists(user_id) AND attribute_exists(key_id)'
            )
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"API key not found: {key_id}")
                return False
            print(f"Error updating API key: {e}")
            return False

    def _parse_dynamodb_item(self, item: Dict[str, Any]) -> APIKey:
        """
        Parse DynamoDB item into APIKey model.

        Args:
            item: DynamoDB item

        Returns:
            APIKey model
        """
        # Parse scopes (handle both SS and L types)
        scopes_value = item.get('scopes', {})
        if 'SS' in scopes_value:
            scopes = list(scopes_value['SS'])
        elif 'L' in scopes_value:
            scopes = [s.get('S', '') for s in scopes_value['L']]
        else:
            scopes = ['events:write']

        return APIKey(
            key_id=item['key_id']['S'],
            user_id=item['user_id']['S'],
            key_hash=item['key_hash']['S'],
            name=item['name']['S'],
            created_at=item['created_at']['S'],
            last_used_at=item.get('last_used_at', {}).get('S'),
            expires_at=item.get('expires_at', {}).get('S'),
            rate_limit=int(item['rate_limit']['N']),
            is_active=item['is_active']['BOOL'],
            scopes=scopes
        )
