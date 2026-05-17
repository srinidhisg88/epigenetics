"""
conftest.py — shared pytest configuration for all test suites.
Checks backend availability before running API-dependent tests.
"""

import pytest
import requests


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_backend: test requires backend running at localhost:8000"
    )


def pytest_collection_modifyitems(config, items):
    """Skip API tests if backend is not available."""
    backend_up = True
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        backend_up = r.status_code == 200
    except Exception:
        backend_up = False

    if not backend_up:
        skip_api = pytest.mark.skip(reason="Backend not running at localhost:8000")
        for item in items:
            # Unit tests and regression tests (module-level) don't need backend
            if "test_unit" not in item.nodeid and "test_regression" not in item.nodeid:
                item.add_marker(skip_api)
