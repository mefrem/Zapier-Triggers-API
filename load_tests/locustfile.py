"""
Locust Load Testing for Zapier Triggers API

This script tests the API at scale:
- Target: 10,000 events/sec ingestion rate
- Latency: p95 <100ms for POST /events, p95 <50ms for GET /inbox
- Error Rate: <0.1%

Run:
    locust -f locustfile.py --host https://api.zapier.com --users 10000 --spawn-rate 3333 --run-time 5m
"""

import json
import time
import uuid
from datetime import datetime
from locust import HttpUser, task, between, events


class EventIngestionLoadTest(HttpUser):
    """Load test for event ingestion and retrieval."""
    
    wait_time = between(0.001, 0.01)  # 1-10ms between requests
    
    def on_start(self):
        """Initialize test user with API key."""
        # In production, use real API key from environment
        self.api_key = "sk_test_load_test_key"
        self.event_counter = 0
        
        # Set headers for all requests
        self.client.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        })
    
    @task(8)  # 80% of traffic - event ingestion
    def ingest_event(self):
        """POST /events - Ingest a new event."""
        event_id = str(uuid.uuid4())
        self.event_counter += 1
        
        payload = {
            'event_type': 'order.created',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'payload': {
                'order_id': f'order_{self.event_counter}',
                'user_id': f'user_{self.event_counter % 100}',  # 100 unique users
                'amount': 99.99,
                'currency': 'USD',
                'items': [
                    {
                        'sku': 'ITEM-001',
                        'quantity': 1,
                        'price': 99.99
                    }
                ],
                'metadata': {
                    'source': 'load_test',
                    'timestamp': time.time()
                }
            }
        }
        
        with self.client.post(
            '/v1/events',
            json=payload,
            name='POST /events',
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 429:
                # Rate limit - expected during load test
                response.failure("Rate limited")
            else:
                response.failure(f"Failed with {response.status_code}")
    
    @task(2)  # 20% of traffic - inbox retrieval
    def get_inbox(self):
        """GET /inbox - Retrieve undelivered events."""
        with self.client.get(
            '/v1/inbox?limit=10',
            name='GET /inbox',
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Verify response structure
                if 'events' in data and 'has_more' in data:
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Failed with {response.status_code}")
    
    @task(1)  # Occasional health checks
    def health_check(self):
        """GET /health - Health check."""
        with self.client.get(
            '/v1/health',
            name='GET /health',
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed with {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start."""
    print("=" * 50)
    print("LOAD TEST STARTING")
    print(f"Target: {environment.parsed_options.num_users} users")
    print(f"Spawn Rate: {environment.parsed_options.spawn_rate} users/sec")
    print(f"Duration: {environment.parsed_options.run_time or 'unlimited'}")
    print("=" * 50)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log test results."""
    stats = environment.stats
    
    print("\n" + "=" * 50)
    print("LOAD TEST RESULTS")
    print("=" * 50)
    
    # Overall stats
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Error Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")
    
    # Latency stats
    print(f"\nLatency (ms):")
    print(f"  p50: {stats.total.get_response_time_percentile(0.50):.2f}")
    print(f"  p95: {stats.total.get_response_time_percentile(0.95):.2f}")
    print(f"  p99: {stats.total.get_response_time_percentile(0.99):.2f}")
    print(f"  Max: {stats.total.max_response_time:.2f}")
    
    # Per-endpoint stats
    print(f"\nPer-Endpoint Stats:")
    for name, entry in stats.entries.items():
        if entry.num_requests > 0:
            print(f"\n  {name}:")
            print(f"    Requests: {entry.num_requests}")
            print(f"    Failures: {entry.num_failures}")
            print(f"    Error Rate: {entry.fail_ratio * 100:.2f}%")
            print(f"    p95 Latency: {entry.get_response_time_percentile(0.95):.2f}ms")
    
    # Success criteria validation
    print(f"\n" + "=" * 50)
    print("SUCCESS CRITERIA VALIDATION")
    print("=" * 50)
    
    error_rate = stats.total.fail_ratio * 100
    p95_latency = stats.total.get_response_time_percentile(0.95)
    throughput = stats.total.total_rps
    
    criteria_met = True
    
    # Error rate < 0.1%
    if error_rate < 0.1:
        print(f"✓ Error Rate: {error_rate:.3f}% (target: <0.1%)")
    else:
        print(f"✗ Error Rate: {error_rate:.3f}% (target: <0.1%)")
        criteria_met = False
    
    # p95 latency < 100ms
    if p95_latency < 100:
        print(f"✓ p95 Latency: {p95_latency:.2f}ms (target: <100ms)")
    else:
        print(f"✗ p95 Latency: {p95_latency:.2f}ms (target: <100ms)")
        criteria_met = False
    
    # Throughput >= 9,900 req/sec (allowing 1% margin)
    if throughput >= 9900:
        print(f"✓ Throughput: {throughput:.2f} req/sec (target: >=9,900)")
    else:
        print(f"✗ Throughput: {throughput:.2f} req/sec (target: >=9,900)")
        criteria_met = False
    
    print("=" * 50)
    if criteria_met:
        print("RESULT: ALL CRITERIA MET ✓")
    else:
        print("RESULT: SOME CRITERIA FAILED ✗")
    print("=" * 50)
