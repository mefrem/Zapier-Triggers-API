"""
CloudWatch Metrics Service for Zapier Triggers API.

Publishes custom metrics:
- EventsIngested: Count of events successfully ingested
- EventsDelivered: Count of events acknowledged
- EventsFailed: Count of events that failed processing
- EventRetries: Count of retry attempts

Metrics are batched for efficiency and published every 10 events or 30 seconds.
"""

import os
import time
from typing import Dict, List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


class MetricsService:
    """Service for publishing custom CloudWatch metrics."""

    NAMESPACE = "ZapierTriggersAPI"
    BATCH_SIZE = 10
    BATCH_TIMEOUT_SECONDS = 30

    def __init__(self, environment: Optional[str] = None):
        """
        Initialize Metrics Service.

        Args:
            environment: Environment name (dev, staging, prod). Defaults to ENV var.
        """
        self.cloudwatch = boto3.client('cloudwatch')
        self.environment = environment or os.getenv('ENVIRONMENT', 'dev')
        self.metric_batch: List[Dict] = []
        self.last_publish_time = time.time()

    def publish_event_ingested(
        self,
        endpoint: str = "POST /events",
        status: str = "success",
        count: int = 1
    ):
        """
        Publish EventsIngested metric.

        Args:
            endpoint: API endpoint (e.g., "POST /events")
            status: Operation status (success, failure)
            count: Number of events (default 1)
        """
        self._add_metric(
            metric_name="EventsIngested",
            value=count,
            endpoint=endpoint,
            status=status
        )

    def publish_event_delivered(
        self,
        endpoint: str = "POST /events/{id}/ack",
        count: int = 1
    ):
        """
        Publish EventsDelivered metric.

        Args:
            endpoint: API endpoint
            count: Number of events delivered
        """
        self._add_metric(
            metric_name="EventsDelivered",
            value=count,
            endpoint=endpoint,
            status="delivered"
        )

    def publish_event_failed(
        self,
        endpoint: str = "POST /events",
        error_type: str = "unknown",
        count: int = 1
    ):
        """
        Publish EventsFailed metric.

        Args:
            endpoint: API endpoint
            error_type: Type of error (e.g., "timeout", "validation")
            count: Number of events failed
        """
        self._add_metric(
            metric_name="EventsFailed",
            value=count,
            endpoint=endpoint,
            status="failed",
            error_type=error_type
        )

    def publish_event_retry(
        self,
        retry_attempt: int = 1,
        count: int = 1
    ):
        """
        Publish EventRetries metric.

        Args:
            retry_attempt: Which retry attempt (1, 2, 3, etc.)
            count: Number of retries
        """
        self._add_metric(
            metric_name="EventRetries",
            value=count,
            endpoint="Retry",
            status=f"attempt_{retry_attempt}"
        )

    def _add_metric(
        self,
        metric_name: str,
        value: float,
        endpoint: str,
        status: str,
        error_type: Optional[str] = None
    ):
        """
        Add metric to batch for publishing.

        Args:
            metric_name: Name of the metric
            value: Metric value
            endpoint: API endpoint
            status: Operation status
            error_type: Optional error type
        """
        dimensions = [
            {'Name': 'Environment', 'Value': self.environment},
            {'Name': 'Endpoint', 'Value': endpoint},
            {'Name': 'Status', 'Value': status}
        ]

        if error_type:
            dimensions.append({'Name': 'ErrorType', 'Value': error_type})

        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': 'Count',
            'Timestamp': datetime.utcnow(),
            'Dimensions': dimensions
        }

        self.metric_batch.append(metric_data)

        # Publish batch if size or timeout threshold reached
        if (len(self.metric_batch) >= self.BATCH_SIZE or
            time.time() - self.last_publish_time >= self.BATCH_TIMEOUT_SECONDS):
            self.flush()

    def flush(self):
        """Publish all batched metrics to CloudWatch."""
        if not self.metric_batch:
            return

        try:
            # CloudWatch allows max 20 metrics per request
            for i in range(0, len(self.metric_batch), 20):
                batch = self.metric_batch[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.NAMESPACE,
                    MetricData=batch
                )

            self.metric_batch = []
            self.last_publish_time = time.time()

        except ClientError as e:
            # Log error but don't fail request
            print(f"Error publishing metrics: {e}")

    def __del__(self):
        """Ensure metrics are flushed when service is destroyed."""
        self.flush()


# Global instance for easy access
_metrics_service = None


def get_metrics_service() -> MetricsService:
    """Get or create global MetricsService instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


def publish_metric(
    metric_name: str,
    value: float,
    endpoint: str = "Unknown",
    status: str = "success"
):
    """
    Convenience function to publish a single metric.

    Args:
        metric_name: Name of the metric
        value: Metric value
        endpoint: API endpoint
        status: Operation status
    """
    service = get_metrics_service()
    service._add_metric(metric_name, value, endpoint, status)
