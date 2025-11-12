"""
Cursor-based pagination utilities.

Provides secure cursor generation and parsing with HMAC signature validation
to prevent tampering attacks.
"""

import os
import json
import hmac
import hashlib
import base64
from typing import Dict, Any, Optional, Tuple
from aws_lambda_powertools import Logger

logger = Logger(service="pagination")


class PaginationCursor:
    """
    Secure cursor-based pagination implementation.

    Cursors are Base64-encoded JSON objects with HMAC-SHA256 signatures
    to prevent tampering. Format: base64(json_payload + "." + signature)
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize PaginationCursor.

        Args:
            secret_key: Secret key for HMAC signing (defaults to PAGINATION_SECRET env var)
        """
        self.secret_key = secret_key or os.environ.get(
            'PAGINATION_SECRET',
            'default-secret-key-change-in-production'
        )
        if not self.secret_key:
            raise ValueError("PAGINATION_SECRET must be set")

    def encode_cursor(
        self,
        timestamp: str,
        event_id: str,
        user_id: str
    ) -> str:
        """
        Encode pagination cursor with HMAC signature.

        Args:
            timestamp: ISO 8601 timestamp of last event
            event_id: UUID of last event
            user_id: User ID (for validation)

        Returns:
            Base64-encoded cursor string

        Example:
            cursor = encode_cursor("2025-11-11T09:15:00.123456Z", "evt-123", "user-456")
            # Returns: "eyJ0aW1lc3RhbXAiOiAiMjAyNS0xMS0xMVQwOToxNTowMCIsICJldmVudF9pZCI6ICJldnQtMTIzIn0.abc123def456"
        """
        try:
            # Create payload
            payload = {
                "timestamp": timestamp,
                "event_id": event_id,
                "user_id": user_id
            }

            # Serialize payload to JSON
            payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)

            # Generate HMAC signature
            signature = self._generate_signature(payload_json)

            # Combine payload and signature
            cursor_data = f"{payload_json}.{signature}"

            # Base64 encode
            encoded = base64.urlsafe_b64encode(cursor_data.encode('utf-8')).decode('utf-8')

            logger.debug(
                "Cursor encoded",
                extra={
                    "timestamp": timestamp,
                    "event_id": event_id,
                    "cursor_length": len(encoded)
                }
            )

            return encoded

        except Exception as e:
            logger.error(
                "Failed to encode cursor",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise ValueError(f"Failed to encode cursor: {str(e)}")

    def decode_cursor(
        self,
        cursor: str,
        user_id: str
    ) -> Tuple[str, str]:
        """
        Decode and validate pagination cursor.

        Args:
            cursor: Base64-encoded cursor string
            user_id: User ID (must match cursor's user_id)

        Returns:
            Tuple of (timestamp, event_id)

        Raises:
            ValueError: If cursor is invalid, tampered with, or belongs to different user
        """
        try:
            # Base64 decode
            decoded = base64.urlsafe_b64decode(cursor.encode('utf-8')).decode('utf-8')

            # Split payload and signature
            parts = decoded.rsplit('.', 1)
            if len(parts) != 2:
                raise ValueError("Invalid cursor format")

            payload_json, signature = parts

            # Verify signature
            expected_signature = self._generate_signature(payload_json)
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning(
                    "Cursor signature mismatch - possible tampering",
                    extra={"user_id": user_id}
                )
                raise ValueError("Invalid cursor signature")

            # Parse payload
            payload = json.loads(payload_json)

            # Validate required fields
            if 'timestamp' not in payload or 'event_id' not in payload or 'user_id' not in payload:
                raise ValueError("Cursor missing required fields")

            # Validate user_id matches
            if payload['user_id'] != user_id:
                logger.warning(
                    "Cursor user_id mismatch",
                    extra={
                        "expected_user_id": user_id,
                        "cursor_user_id": payload['user_id']
                    }
                )
                raise ValueError("Cursor does not belong to this user")

            logger.debug(
                "Cursor decoded successfully",
                extra={
                    "timestamp": payload['timestamp'],
                    "event_id": payload['event_id'],
                    "user_id": user_id
                }
            )

            return payload['timestamp'], payload['event_id']

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse cursor JSON",
                extra={"error": str(e)}
            )
            raise ValueError("Invalid cursor format")

        except base64.binascii.Error as e:
            logger.warning(
                "Failed to decode cursor Base64",
                extra={"error": str(e)}
            )
            raise ValueError("Invalid cursor encoding")

        except Exception as e:
            logger.error(
                "Failed to decode cursor",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise ValueError(f"Invalid cursor: {str(e)}")

    def _generate_signature(self, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.

        Args:
            payload: JSON payload string

        Returns:
            Hex-encoded HMAC signature
        """
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature


def create_pagination_cursor(
    timestamp: str,
    event_id: str,
    user_id: str
) -> str:
    """
    Convenience function to create a pagination cursor.

    Args:
        timestamp: ISO 8601 timestamp of last event
        event_id: UUID of last event
        user_id: User ID

    Returns:
        Encoded cursor string
    """
    cursor_util = PaginationCursor()
    return cursor_util.encode_cursor(timestamp, event_id, user_id)


def parse_pagination_cursor(
    cursor: str,
    user_id: str
) -> Tuple[str, str]:
    """
    Convenience function to parse a pagination cursor.

    Args:
        cursor: Encoded cursor string
        user_id: User ID (must match cursor)

    Returns:
        Tuple of (timestamp, event_id)

    Raises:
        ValueError: If cursor is invalid
    """
    cursor_util = PaginationCursor()
    return cursor_util.decode_cursor(cursor, user_id)
