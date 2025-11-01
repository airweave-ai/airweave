"""Pytest configuration for integration tests.

Configures async test behavior and prevents database initialization during testing.
"""

import os
import pytest

# Set minimal required env vars before any imports
# This prevents Settings validation errors when modules import airweave.core.config
os.environ.setdefault("FIRST_SUPERUSER", "test@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "test123")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-characters-minimum")
os.environ.setdefault("STATE_SECRET", "test-state-secret-32-characters-minimum")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio as the async backend for all tests."""
    return "asyncio"
