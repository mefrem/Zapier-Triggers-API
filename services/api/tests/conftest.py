"""
Pytest configuration and shared fixtures.
"""

import sys
import os
from pathlib import Path

# CRITICAL: Add src directory to Python path BEFORE any test imports
# This must happen at module level, not in a hook
src_path = Path(__file__).parent.parent / 'src'
src_path_str = str(src_path.absolute())

if src_path_str not in sys.path:
    sys.path.insert(0, src_path_str)

# Set AWS environment variables for testing
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['EVENTS_TABLE_NAME'] = 'test-events-table'
os.environ['EVENT_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'
os.environ['POWERTOOLS_SERVICE_NAME'] = 'test-service'
os.environ['POWERTOOLS_METRICS_NAMESPACE'] = 'TestNamespace'
os.environ['LOG_LEVEL'] = 'INFO'

# Pytest configuration complete
