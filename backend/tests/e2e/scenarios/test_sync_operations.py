"""E2E tests for Sync operations."""

import os
import time
import uuid

import pytest
import requests

from airweave.core.constants.native_connections import NATIVE_TEXT2VEC_UUID


@pytest.fixture
def source_connection_data():
    """Fixture to provide test source connection data."""
    # Include both connection name and credential information in auth_fields
    stripe_api_key = os.getenv("STRIPE_API_KEY")
    return {
        "name": "Test Source Connection",
        "auth_fields": {
            # Add required authentication fields for Stripe (StripeAuthConfig)
            "api_key": stripe_api_key,
        },
    }


@pytest.fixture
def sync_data():
    """Fixture to provide test sync data."""
    return {
        "name": f"Test Sync {uuid.uuid4()}",
        "description": "Test sync created by E2E test",
        "source_connection_id": None,  # Will be created during test
        "destination_connection_ids": [],  # Will be populated during test
        "embedding_model_connection_id": str(
            NATIVE_TEXT2VEC_UUID
        ),  # Use the default native embedding model
        "run_immediately": False,
        "schedule": None,
    }


def test_sync_operations(e2e_environment, e2e_api_url, source_connection_data, sync_data):
    """Test the complete lifecycle for a Sync.

    This test:
    1. Creates a new source connection
    2. Creates a new sync
    3. Runs a sync job
    4. Lists sync jobs
    5. Gets the sync DAG
    6. Deletes the sync
    """
    # Step 1: Create a source connection
    create_connection_response = requests.post(
        f"{e2e_api_url}/connections/connect/source/stripe", json=source_connection_data
    )
    assert (
        create_connection_response.status_code == 200
    ), f"Failed to create connection: {create_connection_response.text}"

    # Update the sync data with the source connection ID
    sync_data["source_connection_id"] = create_connection_response.json()["id"]

    # Step 2: Create a new sync
    create_sync_response = requests.post(f"{e2e_api_url}/sync/", json=sync_data)
    assert (
        create_sync_response.status_code == 200
    ), f"Failed to create sync: {create_sync_response.text}"

    # Extract the sync ID from the response
    sync = create_sync_response.json()
    sync_id = sync["id"]
    assert sync["name"] == sync_data["name"]
    assert sync["description"] == sync_data["description"]
    assert sync["source_connection_id"] == sync_data["source_connection_id"]
    assert "destination_connection_ids" in sync
    assert isinstance(sync["destination_connection_ids"], list)

    # Step 4: Retrieve the sync
    get_response = requests.get(f"{e2e_api_url}/sync/{sync_id}")
    assert get_response.status_code == 200, f"Failed to get sync: {get_response.text}"
    retrieved_sync = get_response.json()
    assert retrieved_sync["id"] == sync_id
    assert retrieved_sync["name"] == sync_data["name"]
    assert "destination_connection_ids" in retrieved_sync
    assert isinstance(retrieved_sync["destination_connection_ids"], list)

    # Step 5: Run a sync job
    run_sync_response = requests.post(f"{e2e_api_url}/sync/{sync_id}/run")
    assert run_sync_response.status_code == 200, f"Failed to run sync: {run_sync_response.text}"
    sync_job = run_sync_response.json()
    job_id = sync_job["id"]
    assert sync_job["sync_id"] == sync_id
    assert sync_job["status"] in ["pending", "running", "completed", "failed"]

    # Give the job a moment to start processing
    time.sleep(1)

    # Step 6: List sync jobs
    list_jobs_response = requests.get(f"{e2e_api_url}/sync/{sync_id}/jobs")
    assert (
        list_jobs_response.status_code == 200
    ), f"Failed to list sync jobs: {list_jobs_response.text}"
    jobs = list_jobs_response.json()
    assert len(jobs) >= 1
    assert any(job["id"] == job_id for job in jobs)

    # Get specific job details - Note: The API requires sync_id as a query parameter
    get_job_response = requests.get(
        f"{e2e_api_url}/sync/{sync_id}/job/{job_id}", params={"sync_id": sync_id}
    )
    assert get_job_response.status_code == 200, f"Failed to get sync job: {get_job_response.text}"
    retrieved_job = get_job_response.json()
    assert retrieved_job["id"] == job_id
    assert retrieved_job["sync_id"] == sync_id

    # Step 7: Get the sync DAG
    get_dag_response = requests.get(f"{e2e_api_url}/sync/{sync_id}/dag")
    assert get_dag_response.status_code == 200, f"Failed to get sync DAG: {get_dag_response.text}"
    dag = get_dag_response.json()
    assert dag["sync_id"] == sync_id
    assert "nodes" in dag
    assert "edges" in dag

    # Step 7.5: Remove

    # Step 8: Delete the sync
    delete_response = requests.delete(f"{e2e_api_url}/sync/{sync_id}")
    assert delete_response.status_code == 200, f"Failed to delete sync: {delete_response.text}"

    # Give the system time to process the deletion
    time.sleep(2)

    # Step 9: Verify the sync is gone
    get_after_delete_response = requests.get(f"{e2e_api_url}/sync/{sync_id}")
    assert get_after_delete_response.status_code == 404, "Sync should be deleted"
