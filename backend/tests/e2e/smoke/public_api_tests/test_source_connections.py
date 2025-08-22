"""
Test module for Source Connections functionality.

This module tests the complete source connections lifecycle including:
- Creating source connections with and without immediate sync
- Updating source connection properties
- Running manual syncs
- Monitoring sync job progress
- Testing pubsub subscriptions
- Listing and filtering connections
- Error handling for various scenarios
"""

import time
import uuid
import requests
from typing import Tuple
from .utils import show_backend_logs
from .test_pubsub import test_sync_job_pubsub


def test_source_connections(
    api_url: str, headers: dict, collection_id: str, stripe_api_key: str = None
) -> Tuple[str, str]:
    """Test complete source connections functionality.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to use
        stripe_api_key: Stripe API key for testing

    Returns:
        Tuple[str, str]: The IDs of the two created source connections
    """
    print("\n🔄 Testing Source Connections - Full CRUD & Sync Operations")

    # Debug: Print the collection_id being used
    print(f"  Using collection_id: '{collection_id}'")

    # Verify the collection still exists before creating source connection
    print("  Verifying collection exists before creating source connection...")
    response = requests.get(f"{api_url}/collections/{collection_id}", headers=headers)
    if response.status_code != 200:
        print(f"  ✗ Collection verification failed: {response.status_code} - {response.text}")
        raise AssertionError(
            f"Collection '{collection_id}' not found before creating source connection"
        )

    collection_detail = response.json()
    print(
        f"  ✓ Collection verified: {collection_detail['name']} ({collection_detail['readable_id']})"
    )

    # Use provided Stripe API key or fail
    if not stripe_api_key:
        raise ValueError("Stripe API key must be provided via --stripe-api-key argument")

    # CREATE: Source connection without immediate sync
    print("  Creating source connection (sync_immediately=false)...")
    source_conn_data = {
        "name": "Test Stripe Connection",
        "description": "Test connection for Stripe data",
        "short_name": "stripe",
        "collection": collection_id,
        "sync_immediately": False,
        "auth_fields": {"api_key": stripe_api_key},
        "cron_schedule": "0 */6 * * *",
    }

    # Use correct endpoint with hyphen
    create_url = f"{api_url}/source-connections/"
    print(f"  POST URL: {create_url}")
    print(f"  Request data: {source_conn_data}")
    print(f"  Request headers: {headers}")

    response = requests.post(create_url, json=source_conn_data, headers=headers)

    # Debug response if needed
    if response.status_code != 200:
        print(f"  Response status: {response.status_code}")
        print(f"  Response body: {response.text}")
        print(f"  Response headers: {dict(response.headers)}")

        # Try to parse error details
        try:
            error_detail = response.json()
            print(f"  Parsed error: {error_detail}")
        except:
            pass

        # Show backend logs to help debug the issue
        print("📋 Backend logs for debugging:")
        show_backend_logs(lines=30)

    assert response.status_code == 200, f"Failed to create source connection: {response.text}"

    source_conn = response.json()
    source_conn_id = source_conn["id"]

    # Verify response structure
    assert "id" in source_conn, "Missing id field"
    assert "name" in source_conn, "Missing name field"
    assert "sync_id" in source_conn, "Missing sync_id field"
    assert "status" in source_conn, "Missing status field"
    assert "collection" in source_conn, "Missing collection field"
    assert source_conn["collection"] == collection_id, "Collection mismatch"
    assert source_conn["status"] == "active", "Expected active status for non-immediate sync"

    # Verify no sync job was created (since sync_immediately=false)
    assert (
        source_conn.get("latest_sync_job_id") is None
    ), "Should not have sync job when sync_immediately=false"

    print(f"  ✓ Source connection created: {source_conn['name']} (ID: {source_conn_id})")
    print("  ✓ Verified no sync job was started (sync_immediately=false)")

    # GET: Source connection with hidden auth fields
    print("  Getting source connection (auth fields hidden)...")
    response = requests.get(f"{api_url}/source-connections/{source_conn_id}", headers=headers)
    assert response.status_code == 200, f"Failed to get source connection: {response.text}"

    conn_detail = response.json()
    assert conn_detail["auth_fields"] == "********", "Auth fields should be hidden by default"
    assert conn_detail["cron_schedule"] == "0 */6 * * *", "Cron schedule mismatch"
    assert "next_scheduled_run" in conn_detail, "Missing next_scheduled_run field"

    print("  ✓ Source connection retrieved with hidden auth fields")

    # GET: Source connection with visible auth fields
    print("  Getting source connection (auth fields visible)...")
    response = requests.get(
        f"{api_url}/source-connections/{source_conn_id}?show_auth_fields=true", headers=headers
    )
    assert response.status_code == 200, f"Failed to get source connection: {response.text}"

    conn_detail_auth = response.json()
    assert isinstance(
        conn_detail_auth["auth_fields"], dict
    ), "Auth fields should be a dict when shown"
    assert "api_key" in conn_detail_auth["auth_fields"], "Missing api_key in auth fields"
    assert conn_detail_auth["auth_fields"]["api_key"] == stripe_api_key, "API key mismatch"

    print("  ✓ Source connection retrieved with visible auth fields")

    # UPDATE: Source connection
    print("  Updating source connection...")
    update_data = {
        "name": "Updated Stripe Connection",
        "description": "Updated description for testing",
        "cron_schedule": "0 0 * * *",  # Daily at midnight
    }

    response = requests.put(
        f"{api_url}/source-connections/{source_conn_id}", json=update_data, headers=headers
    )
    assert response.status_code == 200, f"Failed to update source connection: {response.text}"

    updated_conn = response.json()
    assert updated_conn["name"] == update_data["name"], "Name not updated"
    assert updated_conn["description"] == update_data["description"], "Description not updated"
    assert (
        updated_conn["cron_schedule"] == update_data["cron_schedule"]
    ), "Cron schedule not updated"

    print("  ✓ Source connection updated successfully")

    # LIST: All source connections with pagination check
    print("  Listing source connections...")
    response = requests.get(f"{api_url}/source-connections/?limit=100", headers=headers)
    assert response.status_code == 200, f"Failed to list source connections: {response.text}"

    all_connections = response.json()
    assert isinstance(all_connections, list), "Response should be a list"

    # Check if we hit the limit
    if len(all_connections) == 100:
        # Check if there are more
        response = requests.get(f"{api_url}/source-connections/?skip=100&limit=1", headers=headers)
        assert response.status_code == 200, f"Failed to check for more connections: {response.text}"

        if len(response.json()) > 0:
            print("  ⚠️  Warning: Environment has more than 100 source connections")

    assert any(c["id"] == source_conn_id for c in all_connections), "Created connection not in list"

    # LIST: Filter by collection
    response = requests.get(
        f"{api_url}/source-connections/?collection={collection_id}", headers=headers
    )
    assert response.status_code == 200, f"Failed to list by collection: {response.text}"

    collection_connections = response.json()
    assert all(
        c["collection"] == collection_id for c in collection_connections
    ), "Collection filter not working"

    print(
        f"  ✓ Source connections listed ({len(all_connections)} total, {len(collection_connections)} in collection)"
    )

    # RUN: Trigger manual sync
    print("  Running source connection...")
    response = requests.post(f"{api_url}/source-connections/{source_conn_id}/run", headers=headers)
    assert response.status_code == 200, f"Failed to run source connection: {response.text}"

    sync_job = response.json()
    job_id = sync_job["id"]

    # Verify SourceConnectionJob response model fields
    assert "id" in sync_job, "Missing job id"
    assert "source_connection_id" in sync_job, "Missing source_connection_id"
    assert sync_job["source_connection_id"] == source_conn_id, "source_connection_id mismatch"
    assert "status" in sync_job, "Missing job status"
    assert "started_at" in sync_job, "Missing started_at"
    assert sync_job["status"].upper() in [
        "PENDING",
        "IN_PROGRESS",
    ], f"Unexpected initial status: {sync_job['status']}"

    print(f"  ✓ Sync job started (ID: {job_id}, Status: {sync_job['status']})")

    # TEST PUBSUB: Subscribe to sync job progress via SSE
    print("  Testing PubSub subscription to sync job progress...")
    pubsub_success = test_sync_job_pubsub(api_url, job_id, headers, timeout=30)
    assert pubsub_success, "PubSub subscription test failed"

    # GET SOURCE CONNECTION: Verify it now has sync job info
    print("  Verifying source connection has sync job info...")
    response = requests.get(f"{api_url}/source-connections/{source_conn_id}", headers=headers)
    assert response.status_code == 200, f"Failed to get source connection: {response.text}"

    conn_with_job = response.json()
    assert (
        conn_with_job["latest_sync_job_id"] == job_id
    ), "Source connection should have latest_sync_job_id"
    assert "latest_sync_job_status" in conn_with_job, "Missing latest_sync_job_status"
    assert "latest_sync_job_started_at" in conn_with_job, "Missing latest_sync_job_started_at"

    print("  ✓ Source connection updated with sync job information")

    # LIST JOBS: Get all jobs for source connection
    print("  Listing jobs for source connection...")
    response = requests.get(f"{api_url}/source-connections/{source_conn_id}/jobs", headers=headers)
    assert response.status_code == 200, f"Failed to list jobs: {response.text}"

    jobs = response.json()
    assert isinstance(jobs, list), "Jobs should be a list"
    assert any(j["id"] == job_id for j in jobs), "Created job not in list"

    print(f"  ✓ Found {len(jobs)} jobs for source connection")

    # GET JOB: Get specific job details
    print("  Getting specific job details...")
    response = requests.get(
        f"{api_url}/source-connections/{source_conn_id}/jobs/{job_id}", headers=headers
    )
    assert response.status_code == 200, f"Failed to get job: {response.text}"

    job_detail = response.json()
    assert job_detail["id"] == job_id, "Job ID mismatch"
    assert (
        job_detail["source_connection_id"] == source_conn_id
    ), "source_connection_id mismatch in job"
    assert "status" in job_detail, "Missing job status"
    assert "started_at" in job_detail, "Missing started_at"

    print(f"  ✓ Job details retrieved (Status: {job_detail['status']})")

    # WAIT FOR COMPLETION: Poll until job completes
    print("  Waiting for sync to complete...")
    max_wait = 300  # 5 minutes
    poll_interval = 5
    elapsed = 0
    last_log_check = 0

    while elapsed < max_wait:
        response = requests.get(
            f"{api_url}/source-connections/{source_conn_id}/jobs/{job_id}", headers=headers
        )
        assert response.status_code == 200, f"Failed to poll job: {response.text}"

        job_status = response.json()
        current_status = job_status["status"].upper()  # Normalize to uppercase

        if current_status == "COMPLETED":
            print(f"  ✓ Sync completed successfully in ~{elapsed} seconds")
            assert "completed_at" in job_status, "Missing completed_at timestamp"
            break
        elif current_status == "FAILED":
            error_msg = job_status.get("error", "Unknown error")
            print(f"  ✗ Sync failed: {error_msg}")
            print("📋 Backend logs for sync failure debugging:")
            show_backend_logs(lines=50)
            if "test" in stripe_api_key or "dummy" in stripe_api_key:
                print("  ℹ️  Note: Sync failure expected with test API key")
            break

        # Show backend logs every 30 seconds during sync to monitor progress
        if elapsed - last_log_check >= 30:
            print(f"\n  📋 Sync still running after {elapsed}s - checking backend logs:")
            show_backend_logs(lines=10)
            last_log_check = elapsed

        time.sleep(poll_interval)
        elapsed += poll_interval
        print(".", end="", flush=True)

    if elapsed >= max_wait:
        print(f"\n  ⚠️  Sync did not complete within {max_wait} seconds")
        print("📋 Backend logs for timeout debugging:")
        show_backend_logs(lines=50)

    # CREATE SECOND: Source connection with immediate sync
    print("\n  Creating second source connection (sync_immediately=true)...")
    source_conn_data2 = {
        "name": "Auto-sync Stripe Connection",
        "description": "Test connection with immediate sync",
        "short_name": "stripe",
        # No collection specified - should create new one
        "sync_immediately": True,
        "auth_fields": {"api_key": stripe_api_key},
    }

    response = requests.post(
        f"{api_url}/source-connections/", json=source_conn_data2, headers=headers
    )
    assert (
        response.status_code == 200
    ), f"Failed to create second source connection: {response.text}"

    source_conn2 = response.json()
    source_conn2_id = source_conn2["id"]
    auto_collection = source_conn2["collection"]

    assert (
        source_conn2["status"].upper() == "IN_PROGRESS"
    ), "Expected IN_PROGRESS for immediate sync"
    assert "latest_sync_job_id" in source_conn2, "Missing latest_sync_job_id"
    assert source_conn2["latest_sync_job_id"] is not None, "Should have active sync job"

    print(f"  ✓ Second source connection created with auto-collection: {auto_collection}")

    # VERIFY AUTO-CREATED COLLECTION EXISTS
    print("  Verifying auto-created collection exists...")
    response = requests.get(f"{api_url}/collections/{auto_collection}", headers=headers)
    assert response.status_code == 200, f"Auto-created collection not found: {response.text}"

    auto_collection_detail = response.json()
    assert (
        auto_collection_detail["readable_id"] == auto_collection
    ), "Collection readable_id mismatch"
    assert (
        "Collection for" in auto_collection_detail["name"]
    ), "Expected auto-generated collection name"

    print("  ✓ Auto-created collection verified")

    # ERROR HANDLING: Test various error scenarios
    print("\n  Testing error handling...")

    # Test 404: Get non-existent source connection
    response = requests.get(f"{api_url}/source-connections/{uuid.uuid4()}", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent connection, got {response.status_code}"

    # Test 404: Get non-existent job
    response = requests.get(
        f"{api_url}/source-connections/{source_conn_id}/jobs/{uuid.uuid4()}", headers=headers
    )
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent job, got {response.status_code}"

    # Test 404: Create with non-existent collection
    bad_data = {
        "name": "Bad Connection",
        "short_name": "stripe",
        "collection": "non-existent-collection",
        "auth_fields": {"api_key": stripe_api_key},
    }
    response = requests.post(f"{api_url}/source-connections/", json=bad_data, headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent collection, got {response.status_code}"

    # Test 422: Invalid cron schedule
    bad_cron_data = {**source_conn_data, "cron_schedule": "invalid cron"}
    response = requests.post(f"{api_url}/source-connections/", json=bad_cron_data, headers=headers)
    assert response.status_code == 422, f"Expected 422 for invalid cron, got {response.status_code}"

    print("  ✓ Error handling works correctly")

    print("✅ Source Connections test completed successfully")

    # Return the source connection IDs for potential later use
    return source_conn_id, source_conn2_id
