"""
Unit tests for pagination utility.

Tests cursor encoding, decoding, validation, and security features.
"""

import pytest
import base64
import json
from utils.pagination import PaginationCursor, create_pagination_cursor, parse_pagination_cursor


class TestPaginationCursor:
    """Test cases for PaginationCursor class."""

    def test_encode_cursor_success(self):
        """Test successful cursor encoding."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        assert cursor is not None
        assert isinstance(cursor, str)
        assert len(cursor) > 0

    def test_decode_cursor_success(self):
        """Test successful cursor decoding."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        # Encode cursor
        original_timestamp = "2025-11-11T09:15:00.123456Z"
        original_event_id = "evt-123"
        user_id = "user-456"

        cursor = cursor_util.encode_cursor(
            timestamp=original_timestamp,
            event_id=original_event_id,
            user_id=user_id
        )

        # Decode cursor
        timestamp, event_id = cursor_util.decode_cursor(cursor, user_id)

        assert timestamp == original_timestamp
        assert event_id == original_event_id

    def test_decode_cursor_with_wrong_user_id_fails(self):
        """Test that cursor decoding fails when user_id doesn't match."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        # Attempt to decode with different user_id
        with pytest.raises(ValueError, match="does not belong to this user"):
            cursor_util.decode_cursor(cursor, user_id="user-789")

    def test_decode_tampered_cursor_fails(self):
        """Test that decoding a tampered cursor fails."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        # Tamper with cursor by decoding, modifying, and re-encoding without signature
        decoded = base64.urlsafe_b64decode(cursor.encode('utf-8')).decode('utf-8')
        parts = decoded.rsplit('.', 1)
        payload_json = parts[0]

        # Modify the payload
        payload = json.loads(payload_json)
        payload['event_id'] = 'evt-tampered'
        tampered_payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)

        # Re-encode with original signature (will mismatch)
        tampered_cursor_data = f"{tampered_payload}.{parts[1]}"
        tampered_cursor = base64.urlsafe_b64encode(tampered_cursor_data.encode('utf-8')).decode('utf-8')

        # Attempt to decode tampered cursor
        with pytest.raises(ValueError, match="Invalid cursor signature"):
            cursor_util.decode_cursor(tampered_cursor, user_id="user-456")

    def test_decode_invalid_base64_fails(self):
        """Test that decoding invalid Base64 fails."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        invalid_cursor = "not-valid-base64!!!"

        with pytest.raises(ValueError, match="Invalid cursor"):
            cursor_util.decode_cursor(invalid_cursor, user_id="user-456")

    def test_decode_invalid_json_fails(self):
        """Test that decoding invalid JSON in cursor fails."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        # Create cursor with invalid JSON
        invalid_data = "not-json.signature"
        invalid_cursor = base64.urlsafe_b64encode(invalid_data.encode('utf-8')).decode('utf-8')

        with pytest.raises(ValueError, match="Invalid cursor"):
            cursor_util.decode_cursor(invalid_cursor, user_id="user-456")

    def test_decode_cursor_missing_fields_fails(self):
        """Test that cursor missing required fields fails validation."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        # Create cursor with missing fields
        payload = {"timestamp": "2025-11-11T09:15:00.123456Z"}  # Missing event_id and user_id
        payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = cursor_util._generate_signature(payload_json)
        cursor_data = f"{payload_json}.{signature}"
        cursor = base64.urlsafe_b64encode(cursor_data.encode('utf-8')).decode('utf-8')

        with pytest.raises(ValueError, match="missing required fields"):
            cursor_util.decode_cursor(cursor, user_id="user-456")

    def test_encode_decode_round_trip(self):
        """Test that encoding and decoding is reversible."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        test_cases = [
            {
                "timestamp": "2025-11-11T09:15:00.123456Z",
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-12345"
            },
            {
                "timestamp": "2025-01-01T00:00:00.000000Z",
                "event_id": "evt-abc-def-123",
                "user_id": "user-xyz"
            },
            {
                "timestamp": "2025-12-31T23:59:59.999999Z",
                "event_id": "evt-final",
                "user_id": "user-999"
            }
        ]

        for test_case in test_cases:
            cursor = cursor_util.encode_cursor(
                timestamp=test_case["timestamp"],
                event_id=test_case["event_id"],
                user_id=test_case["user_id"]
            )

            timestamp, event_id = cursor_util.decode_cursor(
                cursor,
                user_id=test_case["user_id"]
            )

            assert timestamp == test_case["timestamp"]
            assert event_id == test_case["event_id"]

    def test_different_secret_keys_produce_different_cursors(self):
        """Test that different secret keys produce different cursors."""
        cursor_util_1 = PaginationCursor(secret_key="secret-key-1")
        cursor_util_2 = PaginationCursor(secret_key="secret-key-2")

        cursor_1 = cursor_util_1.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        cursor_2 = cursor_util_2.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        assert cursor_1 != cursor_2

    def test_cursor_with_different_secret_key_fails_validation(self):
        """Test that cursor created with one key fails validation with different key."""
        cursor_util_1 = PaginationCursor(secret_key="secret-key-1")
        cursor_util_2 = PaginationCursor(secret_key="secret-key-2")

        cursor = cursor_util_1.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        # Attempt to decode with different secret key
        with pytest.raises(ValueError, match="Invalid cursor signature"):
            cursor_util_2.decode_cursor(cursor, user_id="user-456")

    def test_convenience_functions(self):
        """Test convenience functions for cursor creation and parsing."""
        timestamp = "2025-11-11T09:15:00.123456Z"
        event_id = "evt-123"
        user_id = "user-456"

        # Create cursor using convenience function
        cursor = create_pagination_cursor(timestamp, event_id, user_id)

        assert cursor is not None
        assert isinstance(cursor, str)

        # Parse cursor using convenience function
        parsed_timestamp, parsed_event_id = parse_pagination_cursor(cursor, user_id)

        assert parsed_timestamp == timestamp
        assert parsed_event_id == event_id

    def test_cursor_is_opaque(self):
        """Test that cursor is Base64-encoded and not easily readable."""
        cursor_util = PaginationCursor(secret_key="test-secret-key")

        cursor = cursor_util.encode_cursor(
            timestamp="2025-11-11T09:15:00.123456Z",
            event_id="evt-123",
            user_id="user-456"
        )

        # Cursor should not contain plain text values
        assert "2025-11-11" not in cursor
        assert "evt-123" not in cursor
        assert "user-456" not in cursor

        # Cursor should be Base64-encoded
        try:
            base64.urlsafe_b64decode(cursor.encode('utf-8'))
        except Exception:
            pytest.fail("Cursor is not valid Base64")
