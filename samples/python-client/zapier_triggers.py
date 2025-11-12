"""
Zapier Triggers API Python Client

A production-ready client for the Zapier Triggers API with automatic retries,
rate limiting, and comprehensive error handling.

Usage:
    from zapier_triggers import TriggersAPI
    
    client = TriggersAPI(api_key="sk_live_abc123")
    
    event = client.ingest_event(
        event_type="user.created",
        payload={"user_id": "123", "email": "user@example.com"}
    )
    print(f"Event {event['event_id']} ingested successfully")
"""

import os
import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib


class TriggersAPIError(Exception):
    """Base exception for Triggers API errors."""
    pass


class AuthenticationError(TriggersAPIError):
    """Raised when API key is invalid or missing."""
    pass


class RateLimitError(TriggersAPIError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(TriggersAPIError):
    """Raised when request validation fails."""
    pass


class TriggersAPI:
    """Client for Zapier Triggers API."""
    
    DEFAULT_BASE_URL = "https://api.zapier.com/v1"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 5
    BACKOFF_FACTOR = 0.1
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize Triggers API client.
        
        Args:
            api_key: API key (or set ZAPIER_API_KEY env var)
            base_url: API base URL (defaults to production)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key or os.getenv('ZAPIER_API_KEY')
        if not self.api_key:
            raise AuthenticationError("API key required. Set ZAPIER_API_KEY or pass api_key parameter.")
        
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'zapier-triggers-python/1.0.0'
        })
    
    def ingest_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        timestamp: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict:
        """
        Ingest a new event.
        
        Args:
            event_type: Event type (format: 'domain.action')
            payload: Event data (max 1MB)
            timestamp: ISO 8601 timestamp (defaults to now)
            idempotency_key: UUID for idempotent requests
        
        Returns:
            Event response dict with event_id, status, etc.
        
        Raises:
            ValidationError: Invalid event data
            RateLimitError: Rate limit exceeded
            TriggersAPIError: Other API errors
        """
        data = {
            'event_type': event_type,
            'payload': payload
        }
        
        if timestamp:
            data['timestamp'] = timestamp
        else:
            data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        headers = {}
        if idempotency_key:
            headers['X-Idempotency-Key'] = idempotency_key
        
        return self._request('POST', '/events', json=data, headers=headers)
    
    def get_inbox(
        self,
        limit: int = 10,
        cursor: Optional[str] = None
    ) -> Dict:
        """
        Retrieve undelivered events from inbox.
        
        Args:
            limit: Maximum events to return (1-100)
            cursor: Pagination cursor
        
        Returns:
            Dict with 'events' list, 'cursor', and 'has_more' flag
        """
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        
        return self._request('GET', '/inbox', params=params)
    
    def acknowledge_event(self, event_id: str) -> Dict:
        """
        Acknowledge event delivery.
        
        Args:
            event_id: Event ID to acknowledge
        
        Returns:
            Event response dict
        """
        return self._request('POST', f'/events/{event_id}/ack')
    
    def delete_event(self, event_id: str) -> None:
        """
        Delete an event.
        
        Args:
            event_id: Event ID to delete
        """
        self._request('DELETE', f'/events/{event_id}')
    
    def health_check(self) -> Dict:
        """Check API health status."""
        return self._request('GET', '/health')
    
    def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Any:
        """
        Make HTTP request with automatic retries.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/events')
            **kwargs: Additional arguments for requests
        
        Returns:
            Response JSON data
        
        Raises:
            AuthenticationError: 401 response
            RateLimitError: 429 response
            ValidationError: 400 response
            TriggersAPIError: Other errors
        """
        url = f"{self.base_url}{path}"
        
        # Merge custom headers
        headers = kwargs.pop('headers', {})
        request_headers = {**self.session.headers, **headers}
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    timeout=self.timeout,
                    **kwargs
                )
                
                # Handle successful responses
                if response.status_code in (200, 201, 204):
                    if response.status_code == 204:
                        return None
                    return response.json()
                
                # Handle errors
                self._handle_error_response(response)
                
            except RateLimitError as e:
                # Retry with backoff for rate limits
                if attempt < self.max_retries - 1:
                    delay = e.retry_after or (2 ** attempt * self.BACKOFF_FACTOR)
                    time.sleep(delay)
                    continue
                raise
            
            except requests.exceptions.RequestException as e:
                # Retry on network errors
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt * self.BACKOFF_FACTOR)
                    continue
                raise TriggersAPIError(f"Request failed: {str(e)}")
    
    def _handle_error_response(self, response: requests.Response):
        """Parse and raise appropriate error for failed response."""
        try:
            error_data = response.json()
            error = error_data.get('error', {})
            message = error.get('message', 'Unknown error')
            code = error.get('code', 'UNKNOWN_ERROR')
        except:
            message = response.text or f"HTTP {response.status_code}"
            code = 'UNKNOWN_ERROR'
        
        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {message}")
        
        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                retry_after = int(retry_after)
            raise RateLimitError(f"Rate limit exceeded: {message}", retry_after=retry_after)
        
        elif response.status_code == 400:
            raise ValidationError(f"Validation error: {message}")
        
        elif response.status_code == 404:
            raise TriggersAPIError(f"Not found: {message}")
        
        else:
            raise TriggersAPIError(f"API error ({code}): {message}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()


# Example usage
if __name__ == '__main__':
    # Initialize client
    client = TriggersAPI(api_key=os.getenv('ZAPIER_API_KEY'))
    
    # Send event
    event = client.ingest_event(
        event_type='user.created',
        payload={
            'user_id': '12345',
            'email': 'user@example.com',
            'name': 'John Doe'
        }
    )
    print(f"Event ingested: {event['event_id']}")
    
    # Retrieve inbox
    inbox = client.get_inbox(limit=10)
    print(f"Inbox has {len(inbox['events'])} events")
    
    # Acknowledge events
    for event in inbox['events']:
        client.acknowledge_event(event['event_id'])
        print(f"Acknowledged: {event['event_id']}")
