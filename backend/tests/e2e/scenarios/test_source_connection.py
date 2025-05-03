"""E2E tests for Source Connection operations."""

import os

import pytest
import requests


@pytest.fixture
def source_connection_data():
    """Fixture to provide test source connection data."""
    # Include both connection name and credential information in auth_fields
    return {
        "name": "Test Source Connection",
        "auth_fields": {
            # Add required authentication fields for Stripe (StripeAuthConfig)
            "api_key": os.getenv("STRIPE_API_KEY"),
        },
    }


def test_source_connection_operations(e2e_environment, e2e_api_url, source_connection_data):
    """Test the complete lifecycle for a Source Connection.

    This test:
    1. Creates a new source connection with credentials
    2. Retrieves the source connection
    3. Updates the source connection status (disconnect)
    4. Deletes the source connection
    5. Verifies the source connection is gone
    """
    # Step 1: Create a new source connection using the connect endpoint
    # This will also create the integration credential internally
    integration_type = "source"
    short_name = "stripe"

    create_connection_response = requests.post(
        f"{e2e_api_url}/connections/connect/{integration_type}/{short_name}",
        json=source_connection_data,
    )
    assert (
        create_connection_response.status_code == 200
    ), f"Failed to create connection: {create_connection_response.text}"

    # Extract the connection ID from the response
    connection = create_connection_response.json()
    connection_id = connection["id"]
    assert connection["name"] == source_connection_data["name"]
    assert connection["short_name"] == short_name
    assert connection["integration_type"] == integration_type
    assert connection["status"] == "active"

    # Step 2: Retrieve the source connection using the detail endpoint
    get_response = requests.get(f"{e2e_api_url}/connections/detail/{connection_id}")
    assert get_response.status_code == 200, f"Failed to get connection: {get_response.text}"
    retrieved_connection = get_response.json()
    assert retrieved_connection["id"] == connection_id
    assert retrieved_connection["name"] == source_connection_data["name"]

    # Step 3: Disconnect the source connection
    disconnect_response = requests.put(
        f"{e2e_api_url}/connections/disconnect/source/{connection_id}"
    )
    assert (
        disconnect_response.status_code == 200
    ), f"Failed to disconnect connection: {disconnect_response.text}"
    disconnected_connection = disconnect_response.json()
    assert disconnected_connection["status"] == "inactive"

    # Verify the connection is inactive by retrieving it again
    get_after_disconnect_response = requests.get(
        f"{e2e_api_url}/connections/detail/{connection_id}"
    )
    assert get_after_disconnect_response.status_code == 200
    assert get_after_disconnect_response.json()["status"] == "inactive"

    # Step 4: Delete the source connection
    delete_response = requests.delete(f"{e2e_api_url}/connections/delete/source/{connection_id}")
    assert (
        delete_response.status_code == 200
    ), f"Failed to delete connection: {delete_response.text}"

    # Step 5: Verify the source connection is gone
    get_after_delete_response = requests.get(f"{e2e_api_url}/connections/detail/{connection_id}")
    assert get_after_delete_response.status_code == 404, "Source connection should be deleted"
