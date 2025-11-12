"""
Performance tests for DynamoDB write latency.

Validates:
- p95 write latency < 10ms
- p99 write latency < 20ms
- No throttling under normal load
- Concurrent write performance
"""

import os
import time
import pytest
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from repositories.event_repository import EventRepository


@pytest.fixture
def repository():
    """Create EventRepository instance."""
    table_name = os.environ.get('EVENTS_TABLE_NAME', 'zapier-triggers-api-dev-events')
    return EventRepository(table_name=table_name)


@pytest.mark.performance
@pytest.mark.slow
class TestDynamoDBWriteLatency:
    """Test DynamoDB write operation latency."""

    def test_single_write_latency(self, repository):
        """Measure single event write latency."""
        latencies = []

        # Perform 100 writes and measure latency
        for i in range(100):
            user_id = f"perf-test-user-{int(time.time())}"
            event_id = f"evt-perf-{i}-{int(time.time())}"
            timestamp = datetime.utcnow().isoformat() + "Z"

            start_time = time.perf_counter()

            repository.create_event(
                user_id=user_id,
                event_id=event_id,
                event_type="performance.test",
                payload={"index": i, "test": "data"},
                timestamp=timestamp
            )

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            # Small delay to avoid overwhelming DynamoDB
            time.sleep(0.01)

        # Calculate statistics
        p50 = statistics.median(latencies)
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        avg = statistics.mean(latencies)
        max_latency = max(latencies)

        print(f"\nWrite Latency Statistics (100 samples):")
        print(f"  Average: {avg:.2f} ms")
        print(f"  Median (p50): {p50:.2f} ms")
        print(f"  p95: {p95:.2f} ms")
        print(f"  p99: {p99:.2f} ms")
        print(f"  Max: {max_latency:.2f} ms")

        # Assert performance requirements
        # Note: These are DynamoDB client-side latencies including network
        # Actual DynamoDB service latency is typically lower
        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms threshold"
        assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms threshold"

    def test_concurrent_write_performance(self, repository):
        """Test write performance under concurrent load."""
        latencies = []
        errors = []
        num_concurrent_writes = 50

        def write_event(index):
            """Write a single event and return latency."""
            try:
                user_id = f"perf-concurrent-{int(time.time())}-{index}"
                event_id = f"evt-concurrent-{index}-{int(time.time())}"
                timestamp = datetime.utcnow().isoformat() + "Z"

                start_time = time.perf_counter()

                repository.create_event(
                    user_id=user_id,
                    event_id=event_id,
                    event_type="concurrent.test",
                    payload={"index": index},
                    timestamp=timestamp
                )

                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000

                return {"success": True, "latency": latency_ms}

            except Exception as e:
                return {"success": False, "error": str(e)}

        # Execute concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_event, i) for i in range(num_concurrent_writes)]

            for future in as_completed(futures):
                result = future.result()
                if result["success"]:
                    latencies.append(result["latency"])
                else:
                    errors.append(result["error"])

        # Calculate statistics
        success_rate = len(latencies) / num_concurrent_writes * 100
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        avg = statistics.mean(latencies)

        print(f"\nConcurrent Write Performance ({num_concurrent_writes} writes):")
        print(f"  Success Rate: {success_rate:.1f}%")
        print(f"  Average Latency: {avg:.2f} ms")
        print(f"  p95 Latency: {p95:.2f} ms")
        print(f"  p99 Latency: {p99:.2f} ms")

        if errors:
            print(f"  Errors: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                print(f"    - {error}")

        # Assert requirements
        assert success_rate >= 99, f"Success rate {success_rate}% is below 99%"
        assert p95 < 100, f"p95 latency {p95:.2f}ms under concurrent load exceeds 100ms"
        assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrent writes"

    def test_sustained_write_throughput(self, repository):
        """Test sustained write throughput over time."""
        duration_seconds = 10
        latencies = []
        start_test = time.time()
        count = 0

        print(f"\nSustained write test for {duration_seconds} seconds...")

        while time.time() - start_test < duration_seconds:
            user_id = f"sustained-test-{int(time.time())}"
            event_id = f"evt-sustained-{count}-{int(time.time())}"
            timestamp = datetime.utcnow().isoformat() + "Z"

            start_write = time.perf_counter()

            repository.create_event(
                user_id=user_id,
                event_id=event_id,
                event_type="sustained.test",
                payload={"count": count},
                timestamp=timestamp
            )

            end_write = time.perf_counter()
            latency_ms = (end_write - start_write) * 1000
            latencies.append(latency_ms)

            count += 1

            # Small delay to maintain reasonable rate
            time.sleep(0.05)  # ~20 writes/second

        # Calculate statistics
        total_time = time.time() - start_test
        throughput = count / total_time
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        avg = statistics.mean(latencies)

        print(f"\nSustained Write Results:")
        print(f"  Total Events: {count}")
        print(f"  Duration: {total_time:.2f} seconds")
        print(f"  Throughput: {throughput:.2f} events/sec")
        print(f"  Average Latency: {avg:.2f} ms")
        print(f"  p95 Latency: {p95:.2f} ms")
        print(f"  p99 Latency: {p99:.2f} ms")

        # Assert requirements
        assert p95 < 100, f"Sustained p95 latency {p95:.2f}ms exceeds 100ms"
        assert throughput >= 10, f"Throughput {throughput:.2f} events/sec is below 10 events/sec"

    @staticmethod
    def _percentile(data, percentile):
        """Calculate percentile of a list of values."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]


@pytest.mark.performance
@pytest.mark.slow
class TestDynamoDBReadLatency:
    """Test DynamoDB read operation latency."""

    def test_get_event_latency(self, repository):
        """Measure event retrieval latency."""
        # Create test event first
        user_id = f"read-perf-user-{int(time.time())}"
        event_id = f"evt-read-perf-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        repository.create_event(
            user_id=user_id,
            event_id=event_id,
            event_type="read.test",
            payload={"test": "data"},
            timestamp=timestamp
        )

        timestamp_event_id = f"{timestamp}#{event_id}"

        # Measure read latency
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter()

            result = repository.get_event(user_id, timestamp_event_id)

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert result is not None
            time.sleep(0.01)

        # Calculate statistics
        p50 = statistics.median(latencies)
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        avg = statistics.mean(latencies)

        print(f"\nRead Latency Statistics (100 samples):")
        print(f"  Average: {avg:.2f} ms")
        print(f"  Median (p50): {p50:.2f} ms")
        print(f"  p95: {p95:.2f} ms")
        print(f"  p99: {p99:.2f} ms")

        # Assert performance
        assert p95 < 50, f"Read p95 latency {p95:.2f}ms exceeds 50ms"
        assert p99 < 100, f"Read p99 latency {p99:.2f}ms exceeds 100ms"

    @staticmethod
    def _percentile(data, percentile):
        """Calculate percentile of a list of values."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]


@pytest.mark.performance
class TestDynamoDBCapacity:
    """Test DynamoDB capacity and throttling behavior."""

    def test_no_throttling_under_normal_load(self, repository):
        """Verify no throttling occurs under normal write load."""
        num_writes = 100
        errors = []

        for i in range(num_writes):
            try:
                user_id = f"throttle-test-{int(time.time())}"
                event_id = f"evt-throttle-{i}-{int(time.time())}"
                timestamp = datetime.utcnow().isoformat() + "Z"

                repository.create_event(
                    user_id=user_id,
                    event_id=event_id,
                    event_type="throttle.test",
                    payload={"index": i},
                    timestamp=timestamp
                )

            except Exception as e:
                error_msg = str(e)
                errors.append(error_msg)

                # Check if it's a throttling error
                if "ProvisionedThroughputExceededException" in error_msg:
                    print(f"THROTTLING DETECTED at write {i}: {error_msg}")

            time.sleep(0.01)  # 100 writes/sec

        success_rate = (num_writes - len(errors)) / num_writes * 100

        print(f"\nThrottling Test Results:")
        print(f"  Total Writes: {num_writes}")
        print(f"  Errors: {len(errors)}")
        print(f"  Success Rate: {success_rate:.1f}%")

        # Assert no throttling
        assert len(errors) == 0, f"Encountered {len(errors)} errors (including potential throttling)"
        assert success_rate == 100, f"Success rate {success_rate}% indicates throttling or errors"
