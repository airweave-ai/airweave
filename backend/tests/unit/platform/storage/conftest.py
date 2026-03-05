"""Shared fixtures for storage unit tests."""

import pytest


@pytest.fixture
def test_data() -> dict:
    """Sample JSON data for testing."""
    return {
        "name": "test-entity",
        "count": 42,
        "nested": {"key": "value", "list": [1, 2, 3]},
        "unicode": "こんにちは世界",
    }


@pytest.fixture
def test_binary() -> bytes:
    """Sample binary data for testing."""
    return b"\x00\x01\x02\x03\x04\x05" + b"binary content" + bytes(range(256))


@pytest.fixture
def large_binary() -> bytes:
    """Large binary data (>1MB) for testing."""
    return b"x" * (1024 * 1024 + 1)  # 1MB + 1 byte
