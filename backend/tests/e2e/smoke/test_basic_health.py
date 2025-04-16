"""Basic smoke test for the Airweave API.

This test verifies that the API is accessible and returns expected responses.
"""

import pytest
import requests

from tests.e2e.runner import E2ETestRunner


# Set up and tear down the E2E test environment once for all tests in this module
@pytest.fixture(scope="module")
def e2e_environment():
    """Set up and tear down the E2E test environment."""
    # Skip this test when running unit or integration tests
    runner = E2ETestRunner()
    try:
        runner.setup()
        yield runner
    finally:
        runner.teardown()


def test_health_endpoint(e2e_environment):
    """Test that the health endpoint returns a 200 status code."""
    # Arrange
    health_url = "http://localhost:9001/health"

    # Act
    response = requests.get(health_url)

    # Assert
    assert response.status_code == 200

    # Check response body
    response_data = response.json()
    assert response_data["status"] == "healthy"


def test_api_docs_accessible(e2e_environment):
    """Test that the API documentation is accessible."""
    # Arrange
    docs_url = "http://localhost:9001/docs"

    # Act
    response = requests.get(docs_url)

    # Assert
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]

    # Check for Swagger UI content
    assert "swagger-ui" in response.text.lower()
