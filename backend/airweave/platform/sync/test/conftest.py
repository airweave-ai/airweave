"""Pytest configuration for platform sync tests.

Uses pytest_configure hook to set minimal environment variables
before test collection (and thus before imports).
"""

import os


def pytest_configure(config):
    """Configure pytest environment before test collection.

    This hook runs BEFORE pytest collects tests, which means it runs
    BEFORE imports happen. We set minimal env vars here so Settings()
    validation passes during module imports.

    Using setdefault() means we only set if not already present,
    so actual environment variables always take precedence.
    """
    # Core settings required for Settings() initialization
    os.environ.setdefault("FIRST_SUPERUSER", "test@example.com")
    os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "test_password_123")
    os.environ.setdefault("ENCRYPTION_KEY", "test_encryption_key_minimum_32chars_long")
    os.environ.setdefault("STATE_SECRET", "test_state_secret_key_minimum_32_characters_required")

    # Database settings
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_USER", "test_user")
    os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
    os.environ.setdefault("POSTGRES_DB", "test_db")

    # Redis settings
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")

    # Disable features that require external services
    os.environ.setdefault("ANALYTICS_ENABLED", "false")
    os.environ.setdefault("BILLING_ENABLED", "false")
