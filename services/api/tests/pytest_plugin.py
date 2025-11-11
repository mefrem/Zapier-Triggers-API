"""
Pytest plugin to configure Python path before test collection.
"""

import sys
from pathlib import Path

def pytest_configure(config):
    """Configure pytest before test collection."""
    # Add src directory to Python path
    src_path = Path(__file__).parent.parent / 'src'
    src_path_str = str(src_path.absolute())

    if src_path_str not in sys.path:
        sys.path.insert(0, src_path_str)
