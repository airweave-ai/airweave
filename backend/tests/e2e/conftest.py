"""Configuration and fixtures for end-to-end tests."""

import logging
from typing import Generator

import pytest

from tests.e2e.runner import E2ETestRunner

logger = logging.getLogger(__name__)

# Global runner instance to ensure reuse across test sessions
_runner = None


@pytest.fixture(scope="session")
def e2e_environment() -> Generator[E2ETestRunner, None, None]:
    """Set up and tear down the E2E test environment.

    This fixture starts all required services using docker-compose
    and tears them down after all tests are complete.
    """
    global _runner

    # Create runner with minimal mode (postgres and backend only)
    # This avoids issues with Weaviate and Neo4j that can be flaky in tests
    if _runner is None:
        _runner = E2ETestRunner()

    try:
        # Start services (or reuse existing ones)
        logger.info("Starting or reusing E2E test environment")
        _runner.setup()

        # Yield runner for additional operations if needed
        yield _runner
    except Exception as e:
        logger.error(f"Error during E2E environment setup: {e}")
        raise


@pytest.fixture(scope="session")
def e2e_api_url() -> str:
    """Return the base URL for API requests in E2E tests."""
    return "http://localhost:9001/"
