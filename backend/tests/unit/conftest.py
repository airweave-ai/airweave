"""Unit test conftest for setting up test environment."""

import os

# Set minimal required environment variables before importing any airweave modules
# This prevents Settings initialization errors during test collection
os.environ.setdefault("FIRST_SUPERUSER", "test@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "testpassword123")
os.environ.setdefault("ENCRYPTION_KEY", "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0=")
os.environ.setdefault("STATE_SECRET", "test-state-secret-key-minimum-32-characters-long")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("AUTH_ENABLED", "false")
