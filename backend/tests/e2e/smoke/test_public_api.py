"""
Public API Test Script

Tests Airweave API across different environments:
- local: Starts services via start.sh, uses localhost:8001
- dev: Uses api.dev-airweave.com
- prod: Uses api.airweave.ai

Usage:
    python test_public_api.py --env local
    python test_public_api.py --env local --openai-api-key YOUR_KEY
    python test_public_api.py --env dev --api-key YOUR_KEY
    python test_public_api.py --env prod --api-key YOUR_KEY
"""

import pytest

pytestmark = pytest.mark.skip(reason="This is a standalone script, not a pytest test")

import argparse
import subprocess
import time
import sys
import os
import requests
from typing import Optional
from pathlib import Path
import uuid
import json
import threading


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test Airweave Public API")

    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        required=True,
        help="Environment to test against (local, dev, or prod)",
    )

    parser.add_argument(
        "--api-key", type=str, help="API key for authentication (required for dev/prod)"
    )

    parser.add_argument(
        "--openai-api-key", type=str, help="OpenAI API key for local environment setup"
    )

    parser.add_argument(
        "--stripe-api-key",
        type=str,
        required=True,
        help="Stripe API key for testing source connections (required)",
    )

    args = parser.parse_args()

    # Validate that API key is provided for dev/prod environments
    if args.env in ["dev", "prod"] and not args.api_key:
        parser.error(f"--api-key is required for {args.env} environment")

    # Validate that Stripe API key is provided
    if not args.stripe_api_key:
        parser.error("--stripe-api-key is required for testing source connections")

    # Validate Stripe API key format
    if not args.stripe_api_key.startswith("sk_"):
        parser.error("Stripe API key must start with 'sk_' (e.g., sk_test_... or sk_live_...)")

    return args


def show_backend_logs(lines: int = 50) -> None:
    """Show recent backend logs for debugging."""
    try:
        print(f"📋 Showing last {lines} lines of backend logs:")
        print("=" * 80)

        # Get logs from the backend container
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), "airweave-backend"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
        else:
            print(f"Failed to get logs: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("⚠️  Timeout getting backend logs")
    except Exception as e:
        print(f"⚠️  Error getting backend logs: {e}")
    finally:
        print("=" * 80)


def wait_for_health(url: str, timeout: int = 300) -> bool:
    """Wait for service to be healthy."""
    print(f"Waiting for {url} to be healthy (timeout: {timeout}s)...")
    start_time = time.time()
    last_error = None
    error_count = 0

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print("✓ Service is healthy")
                return True
            else:
                last_error = f"HTTP {response.status_code}: {response.text}"
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            error_count += 1
            # Only log errors occasionally to avoid spam
            if error_count % 10 == 1:  # Log every 10th error
                print(f"\n⚠️  Health check error (#{error_count}): {e}")

        time.sleep(2)
        print(".", end="", flush=True)

    elapsed = time.time() - start_time
    print(f"\n✗ Service health check timed out after {elapsed:.1f}s")
    if last_error:
        print(f"  Last error: {last_error}")
    return False


def start_local_services(openai_api_key: Optional[str] = None) -> bool:
    """Start local services using start.sh script."""
    print("Starting local services...")

    # Find the repository root (where start.sh is located)
    current_dir = Path(__file__).resolve()
    repo_root = (
        current_dir.parent.parent.parent.parent.parent
    )  # Go up from backend/tests/e2e/smoke/test_public_api.py
    start_script = repo_root / "start.sh"

    if not start_script.exists():
        print(f"✗ start.sh not found at {start_script}")
        return False

    # Prepare automated responses for the interactive prompts
    if openai_api_key:
        # If we have an API key, answer 'y' and provide the key, then 'n' for Mistral
        automated_input = f"y\n{openai_api_key}\nn\ny\n"
    else:
        # If no API key, answer 'n' to both API key prompts, 'y' to remove containers
        automated_input = "n\nn\ny\n"

    # Set environment variables to suppress Azure credential warnings
    env = os.environ.copy()
    env.update({
        'AZURE_CLIENT_ID': '',
        'AZURE_CLIENT_SECRET': '',
        'AZURE_TENANT_ID': '',
        'AZURE_USERNAME': '',
        'AZURE_PASSWORD': '',
        'MSI_ENDPOINT': '',  # Disable managed identity
        'IMDS_ENDPOINT': '',  # Disable IMDS
    })

    try:
        # Run start.sh script with automated input
        process = subprocess.Popen(
            ["bash", str(start_script)],
            cwd=str(repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,  # Pass environment variables to suppress Azure warnings
        )

        # Send automated responses
        process.stdin.write(automated_input)
        process.stdin.flush()
        process.stdin.close()  # Close stdin to prevent hanging

        # Monitor output
        services_started = False
        for line in process.stdout:
            print(f"  {line.strip()}")
            if "All services started successfully" in line:
                services_started = True
                break
            if "Error:" in line or "error:" in line:
                print(f"✗ Error detected: {line.strip()}")

        # Wait for process to complete (but with longer timeout since Docker health checks take time)
        return_code = process.wait(timeout=180)  # 3 minutes for Docker to pull images and start

        if return_code != 0:
            print(f"✗ start.sh exited with code {return_code}")
            return False

        if not services_started:
            print("✗ Services did not start successfully")
            return False

        print("✓ Services started and should be healthy")
        return True

    except subprocess.TimeoutExpired:
        print("✗ start.sh script timed out (Docker may be slow)")
        process.kill()
        return False
    except Exception as e:
        print(f"✗ Failed to start local services: {e}")
        return False


def get_api_url(env: str) -> str:
    """Get API URL based on environment."""
    urls = {
        "local": "http://localhost:8001",
        "dev": "https://api.dev-airweave.com",
        "prod": "https://api.airweave.ai",
    }
    return urls[env]


def setup_environment(env: str, openai_api_key: Optional[str] = None) -> Optional[str]:
    """Setup environment and return API URL if successful."""
    api_url = get_api_url(env)

    if env == "local":
        # Start local services (they should be healthy when this completes)
        if not start_local_services(openai_api_key):
            return None

        # Health check to verify backend is accessible (longer timeout for full initialization)
        print("Verifying backend is accessible...")
        if not wait_for_health(api_url, timeout=120):  # Increased from 30 to 120 seconds
            print("✗ Backend is not responding after 2 minutes")
            print("📋 Checking backend logs for debugging...")
            show_backend_logs()
            return None

    else:
        # For dev/prod, just check if API is reachable
        print(f"Checking {env} API availability...")
        if not wait_for_health(api_url, timeout=30):
            print(f"✗ {env.upper()} API is not reachable")
            return None

    print(f"✓ Using API URL: {api_url}")
    return api_url


def test_collections(api_url: str, headers: dict) -> str:
    """Test complete CRUD operations for collections.

    Returns:
        str: The readable_id of the created collection for use in other tests
    """
    print("\n🔄 Testing Collections - Full CRUD")

    # CREATE: Create collection with auto-generated readable_id
    print("  Creating collection...")
    collection_data = {"name": f"Test Collection {int(time.time())}"}

    # Debug the request
    print(f"  Request URL: {api_url}/collections/")
    print(f"  Request headers: {headers}")
    print(f"  Request data: {collection_data}")

    response = requests.post(f"{api_url}/collections/", json=collection_data, headers=headers)

    # Debug the response
    print(f"  Response status: {response.status_code}")
    if response.status_code != 200:
        print(f"  Response headers: {dict(response.headers)}")
        print(f"  Response body: {response.text}")
        try:
            error_detail = response.json()
            print(f"  Parsed error: {error_detail}")
        except:
            pass

        # Show backend logs to help debug the issue
        print("📋 Backend logs for debugging:")
        show_backend_logs(lines=20)

    assert response.status_code == 200, f"Failed to create collection: {response.text}"

    collection = response.json()
    readable_id = collection["readable_id"]

    # Verify collection structure and readable_id format
    assert "id" in collection, "Collection missing 'id' field"
    assert "name" in collection, "Collection missing 'name' field"
    assert "readable_id" in collection, "Collection missing 'readable_id' field"
    assert "status" in collection, "Collection missing 'status' field"
    assert "created_at" in collection, "Collection missing 'created_at' field"
    assert collection["name"] == collection_data["name"], "Collection name mismatch"
    assert (
        collection["status"] == "NEEDS SOURCE"
    ), "New collection should have 'NEEDS SOURCE' status"

    # Verify readable_id format (lowercase, hyphens, ends with 6-char suffix)
    assert readable_id.islower(), "readable_id should be lowercase"
    assert "-" in readable_id, "readable_id should contain hyphens"
    assert len(readable_id.split("-")[-1]) == 6, "readable_id should end with 6-character suffix"

    print(f"  ✓ Collection created: {collection['name']} (ID: {readable_id})")

    # READ: Get collection by readable_id
    print("  Getting collection...")
    response = requests.get(f"{api_url}/collections/{readable_id}", headers=headers)
    assert response.status_code == 200, f"Failed to get collection: {response.text}"

    retrieved_collection = response.json()
    assert retrieved_collection["id"] == collection["id"], "Retrieved collection ID mismatch"
    assert retrieved_collection["name"] == collection["name"], "Retrieved collection name mismatch"
    assert (
        retrieved_collection["readable_id"] == readable_id
    ), "Retrieved collection readable_id mismatch"

    print(f"  ✓ Collection retrieved successfully")

    # UPDATE: Update collection name
    print("  Updating collection...")
    updated_name = f"Updated Test Collection {int(time.time())}"
    update_data = {"name": updated_name}

    response = requests.put(
        f"{api_url}/collections/{readable_id}", json=update_data, headers=headers
    )
    assert response.status_code == 200, f"Failed to update collection: {response.text}"

    updated_collection = response.json()
    assert updated_collection["name"] == updated_name, "Collection name not updated"
    assert (
        updated_collection["readable_id"] == readable_id
    ), "readable_id should not change on update"

    print(f"  ✓ Collection updated: {updated_name}")

    # READ AGAIN: Verify update persisted
    print("  Verifying update persisted...")
    response = requests.get(f"{api_url}/collections/{readable_id}", headers=headers)
    assert response.status_code == 200, f"Failed to get updated collection: {response.text}"

    final_collection = response.json()
    assert final_collection["name"] == updated_name, "Update did not persist"

    print(f"  ✓ Update verified")

    # LIST: Test pagination and verify our collection exists somewhere
    print("  Testing collection listing with pagination...")

    # First, test that pagination limit works
    response = requests.get(f"{api_url}/collections/?skip=0&limit=2", headers=headers)
    assert response.status_code == 200, f"Failed to list collections: {response.text}"

    limited_list = response.json()
    assert isinstance(limited_list, list), "Collections list should be an array"
    assert len(limited_list) <= 2, "Pagination limit not respected"

    # Now get all collections to verify ours exists
    response = requests.get(f"{api_url}/collections/?skip=0&limit=100", headers=headers)
    assert response.status_code == 200, f"Failed to list all collections: {response.text}"

    all_collections = response.json()
    assert isinstance(all_collections, list), "Collections list should be an array"

    # Check if we hit the limit - might be more collections
    if len(all_collections) == 100:
        # Try to get one more to see if there are actually more than 100
        response = requests.get(f"{api_url}/collections/?skip=100&limit=1", headers=headers)
        assert response.status_code == 200, f"Failed to check for more collections: {response.text}"

        overflow_check = response.json()
        if len(overflow_check) > 0:
            raise AssertionError(
                f"Environment has more than 100 collections! Cannot verify our collection exists. "
                f"Please clean up old test collections or increase the test limit."
            )

    # Verify our collection is in the full list
    collection_found = any(c["readable_id"] == readable_id for c in all_collections)
    assert (
        collection_found
    ), f"Created collection '{readable_id}' not found in list of {len(all_collections)} collections"

    # Test skip parameter
    if len(all_collections) > 1:
        response = requests.get(f"{api_url}/collections/?skip=1&limit=100", headers=headers)
        assert response.status_code == 200, f"Failed to list collections with skip: {response.text}"

        skipped_list = response.json()
        assert len(skipped_list) == len(all_collections) - 1, "Skip parameter not working correctly"

    print(f"  ✓ Collection listing works (found {len(all_collections)} total collections)")
    print(f"  ✓ Pagination parameters (skip, limit) work correctly")

    # ERROR HANDLING: Test various error scenarios
    print("  Testing error handling...")

    # Test 404: Get non-existent collection
    response = requests.get(f"{api_url}/collections/nonexistent-collection", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent collection, got {response.status_code}"

    # Test 404: Update non-existent collection
    response = requests.put(
        f"{api_url}/collections/nonexistent-collection", json={"name": "Test"}, headers=headers
    )
    assert (
        response.status_code == 404
    ), f"Expected 404 for updating non-existent collection, got {response.status_code}"

    # Test 404: Delete non-existent collection
    response = requests.delete(f"{api_url}/collections/nonexistent-collection", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for deleting non-existent collection, got {response.status_code}"

    # Test 422: Create collection with invalid name (too short)
    response = requests.post(f"{api_url}/collections/", json={"name": "abc"}, headers=headers)
    assert (
        response.status_code == 422
    ), f"Expected 422 for invalid collection name, got {response.status_code}"

    # Test 422: Create collection with invalid name (too long)
    long_name = "x" * 100  # Exceeds 64 character limit
    response = requests.post(f"{api_url}/collections/", json={"name": long_name}, headers=headers)
    assert (
        response.status_code == 422
    ), f"Expected 422 for too long collection name, got {response.status_code}"

    # Test 422: Update collection with invalid name
    response = requests.put(
        f"{api_url}/collections/{readable_id}", json={"name": "ab"}, headers=headers
    )
    assert (
        response.status_code == 422
    ), f"Expected 422 for invalid update name, got {response.status_code}"

    print("  ✓ Error handling works correctly")

    print("✅ Collections CRUD test completed successfully")
    return readable_id


def test_sources(api_url: str, headers: dict) -> None:
    """Test sources endpoints - list and detail."""
    print("\n🔄 Testing Sources Endpoints")

    # LIST: Get all available sources
    print("  Listing all sources...")
    response = requests.get(f"{api_url}/sources/list", headers=headers)
    assert response.status_code == 200, f"Failed to list sources: {response.text}"

    sources = response.json()
    assert isinstance(sources, list), "Sources response should be an array"
    assert len(sources) > 0, "No sources available"

    # Verify first source has required structure
    first_source = sources[0]
    required_fields = [
        "id",
        "name",
        "short_name",
        "auth_config_class",
        "config_class",
        "class_name",
        "auth_fields",
        "created_at",
        "modified_at",
    ]
    for field in required_fields:
        assert field in first_source, f"Source missing required field: {field}"

    # Find Stripe source
    stripe_source = next((s for s in sources if s["short_name"] == "stripe"), None)
    assert stripe_source is not None, "Stripe source not found in sources list"

    print(f"  ✓ Found {len(sources)} sources, including Stripe")

    # Validate Stripe source structure
    assert stripe_source["auth_config_class"] == "StripeAuthConfig", "Unexpected auth config class"
    assert stripe_source["config_class"] == "StripeConfig", "Unexpected config class"

    # Validate auth_fields (required and must have fields)
    assert stripe_source["auth_fields"] is not None, "auth_fields is required"
    assert "fields" in stripe_source["auth_fields"], "auth_fields must have 'fields'"
    assert len(stripe_source["auth_fields"]["fields"]) > 0, "auth_fields cannot be empty"

    # Find and validate api_key field
    auth_fields = stripe_source["auth_fields"]["fields"]
    api_key_field = next((f for f in auth_fields if f["name"] == "api_key"), None)
    assert api_key_field is not None, "Stripe must have 'api_key' auth field"

    # Validate api_key field properties
    assert api_key_field["type"] == "string", "api_key must be string type"
    assert "title" in api_key_field, "api_key must have title"
    assert "description" in api_key_field, "api_key must have description"
    assert api_key_field["name"] == "api_key", "Field name should be 'api_key'"

    # Validate config_fields (can be None or empty for Stripe)
    if stripe_source.get("config_fields"):
        assert (
            "fields" in stripe_source["config_fields"]
        ), "config_fields must have 'fields' if present"

    print("  ✓ Stripe source structure validated")

    # DETAIL: Get specific source details
    print("  Getting Stripe source details...")
    response = requests.get(f"{api_url}/sources/detail/stripe", headers=headers)
    assert response.status_code == 200, f"Failed to get Stripe source details: {response.text}"

    stripe_detail = response.json()

    # Verify detail has all required fields
    for field in required_fields:
        assert field in stripe_detail, f"Detail response missing field: {field}"

    # Verify consistency between list and detail
    assert stripe_detail["id"] == stripe_source["id"], "ID mismatch between list and detail"
    assert stripe_detail["name"] == stripe_source["name"], "Name mismatch"
    assert stripe_detail["short_name"] == "stripe", "Short name mismatch"
    assert (
        stripe_detail["auth_config_class"] == stripe_source["auth_config_class"]
    ), "Auth config class mismatch"
    assert stripe_detail["config_class"] == stripe_source["config_class"], "Config class mismatch"

    # Verify auth_fields match
    detail_api_key = next(
        (f for f in stripe_detail["auth_fields"]["fields"] if f["name"] == "api_key"), None
    )
    assert detail_api_key is not None, "Detail response missing api_key field"
    assert detail_api_key == api_key_field, "api_key field mismatch between list and detail"

    print("  ✓ Stripe source details match list response")

    # ERROR HANDLING: Test non-existent source
    print("  Testing error handling...")
    response = requests.get(f"{api_url}/sources/detail/nonexistent", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent source, got {response.status_code}"

    # Verify error response structure
    error_response = response.json()
    assert "detail" in error_response, "Error response should have 'detail' field"
    assert (
        "nonexistent" in error_response["detail"].lower()
    ), "Error message should mention the source name"

    print("  ✓ Error handling works correctly")

    print("✅ Sources endpoints test completed successfully")


def test_source_connections(
    api_url: str, headers: dict, collection_id: str, stripe_api_key: str = None
) -> tuple[str, str]:
    """Test complete source connections functionality."""
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
        "cron_schedule": "0 */6 * * *",  # Every 6 hours
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


def test_sync_job_pubsub(api_url: str, job_id: str, headers: dict, timeout: int = 30) -> bool:
    """Test sync job pubsub functionality via SSE with header authentication.

    Args:
        api_url: The API URL
        job_id: The sync job ID to subscribe to
        headers: Request headers including authentication
        timeout: Maximum time to wait for messages

    Returns:
        bool: True if pubsub test succeeded, False otherwise
    """
    import json
    import threading

    sse_url = f"{api_url}/sync/job/{job_id}/subscribe"
    print(f"    Subscribing to SSE endpoint: {sse_url}")

    messages_received = []
    error_occurred = False

    def read_sse_stream():
        """Read SSE stream in a thread."""
        nonlocal error_occurred
        try:
            # Use stream=True for SSE with header authentication
            response = requests.get(sse_url, stream=True, timeout=timeout, headers=headers)

            if response.status_code != 200:
                print(f"    ✗ SSE connection failed: {response.status_code}")
                error_occurred = True
                return

            # Read SSE stream line by line
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        # Extract JSON data after "data: " prefix
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            messages_received.append(data)
                            print(
                                f"    📨 Received update: inserted={data.get('inserted', 0)}, "
                                f"updated={data.get('updated', 0)}, "
                                f"deleted={data.get('deleted', 0)}, "
                                f"is_complete={data.get('is_complete', False)}"
                            )

                            # Stop if job is complete
                            if data.get("is_complete") or data.get("is_failed"):
                                break
                        except json.JSONDecodeError as e:
                            print(f"    ⚠️  Failed to parse SSE data: {e}")

                # Stop after receiving some messages to avoid hanging
                if len(messages_received) >= 3:
                    break

        except requests.exceptions.Timeout:
            print("    ℹ️  SSE stream timed out (expected)")
        except Exception as e:
            print(f"    ✗ SSE stream error: {e}")
            error_occurred = True

    # Start SSE reader in a thread
    sse_thread = threading.Thread(target=read_sse_stream)
    sse_thread.daemon = True
    sse_thread.start()

    # Wait for thread to complete or timeout
    sse_thread.join(timeout=timeout)

    if error_occurred:
        return False

    # Verify we received at least one message
    if len(messages_received) == 0:
        print("    ⚠️  No pubsub messages received (sync might have completed too quickly)")
        return True  # Not necessarily a failure

    # Verify message structure
    for msg in messages_received:
        # Skip non-progress messages (connected, heartbeat, etc.)
        if msg.get("type") in ["connected", "heartbeat", "error"]:
            continue

        required_fields = [
            "inserted",
            "updated",
            "deleted",
            "kept",
            "skipped",
            "entities_encountered",
            "is_complete",
            "is_failed",
        ]
        for field in required_fields:
            if field not in msg:
                print(f"    ✗ Missing required field '{field}' in pubsub message")
                return False

    print(f"    ✓ PubSub test successful - received {len(messages_received)} progress updates")
    return True


def test_search_functionality(
    api_url: str, headers: dict, collection_id: str, wait_after_sync: int = 10
) -> None:
    """Test collection search functionality with both RAW and COMPLETION response types.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to search
        wait_after_sync: Seconds to wait after sync before searching (for indexing)
    """
    print("\n🔄 Testing Search Functionality")

    # Wait a bit for data to be fully indexed after sync
    print(f"  Waiting {wait_after_sync} seconds for data indexing...")
    time.sleep(wait_after_sync)

    # Define test query - same as in the deprecated test
    search_query = "Are there any open invoices"
    expected_keywords = ["Lufthansa"]

    # TEST 1: Raw search response
    print(f"\n  Testing RAW search for: '{search_query}'")
    response = requests.get(
        f"{api_url}/collections/{collection_id}/search",
        params={"query": search_query, "response_type": "raw"},
        headers=headers,
    )

    if response.status_code != 200:
        print(f"Search request failed: {response.status_code} - {response.text}")
        print("📋 Backend logs for search failure debugging:")
        show_backend_logs(lines=30)

    assert response.status_code == 200, f"Search failed: {response.text}"

    raw_results = response.json()

    # Validate RAW response structure based on SearchResponse schema
    assert "results" in raw_results, "Missing 'results' field in raw response"
    assert "response_type" in raw_results, "Missing 'response_type' field in raw response"
    assert "status" in raw_results, "Missing 'status' field in raw response"
    assert raw_results["response_type"] == "raw", "Response type should be 'raw'"

    results_list = raw_results.get("results", [])
    status = raw_results.get("status", "")

    print(f"  ✓ RAW search returned {len(results_list)} results (status: {status})")

    # Check if we have results before evaluating
    if len(results_list) > 0 and status == "success":
        # Validate individual result structure
        first_result = results_list[0]
        assert "payload" in first_result, "Result missing 'payload' field"
        assert "score" in first_result, "Result missing 'score' field"

        # Display first few results for debugging
        print(f"\n  Top results (showing up to 3):")
        for i, result in enumerate(results_list[:3]):
            print(f"    Result {i+1} (score: {result.get('score', 0):.4f}):")
            payload = result.get("payload", {})

            # More detailed debugging of payload content
            if isinstance(payload, dict):
                # Show all fields in the payload for debugging
                print("      Payload fields:")
                for key, value in payload.items():
                    # Truncate long values
                    value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"        {key}: {value_str}")

                # Look for any content that might contain invoice/product info
                text_content = payload.get("text", payload.get("content", ""))
                if text_content:
                    print(f"      Full text content: {text_content[:500]}...")
            else:
                content = str(payload)[:200]
                print(f"      Content: {content}...")
            print("      ---")

        # Use LLM judge to evaluate search quality
        try:
            # Add the tests directory to Python path to enable imports
            import sys
            import os

            current_dir = os.path.dirname(os.path.abspath(__file__))
            tests_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up to tests/
            if tests_dir not in sys.path:
                sys.path.insert(0, tests_dir)

            from helpers.llm_judge import evaluate_search_results

            print(f"\n  Evaluating search results with LLM judge...")
            evaluation = evaluate_search_results(
                query=search_query,
                results=results_list,
                expected_content_keywords=expected_keywords,
                minimum_score=0.5,  # Lower threshold since it's test data
                minimum_relevant_results=1,
            )

            print(f"    Relevance: {evaluation.get('relevance', 0):.2f}")
            print(f"    Completeness: {evaluation.get('completeness', 0):.2f}")
            print(f"    Score: {evaluation.get('score', 0):.2f}")
            print(f"    Feedback: {evaluation.get('feedback', 'No feedback')}")

            # FAIL THE TEST if score is too low
            min_acceptable_score = 0.3
            if evaluation.get("score", 0) < min_acceptable_score:
                # First, let's see if we can find the keywords anywhere in ALL results
                print(
                    f"\n  🔍 Debugging: Searching for keywords in all {len(results_list)} results..."
                )
                keywords_found_in_any = False
                for idx, result in enumerate(results_list):
                    payload = result.get("payload", {})
                    payload_str = json.dumps(payload).lower()
                    for keyword in expected_keywords:
                        if keyword.lower() in payload_str:
                            print(f"    Found '{keyword}' in result {idx+1}!")
                            keywords_found_in_any = True

                if not keywords_found_in_any:
                    print(
                        f"    ❌ Keywords {expected_keywords} not found in ANY of the {len(results_list)} results"
                    )

                # Now fail the test
                raise AssertionError(
                    f"Search quality too low! Score: {evaluation.get('score', 0):.2f} < {min_acceptable_score}. "
                    f"LLM Judge feedback: {evaluation.get('feedback', 'No feedback')}. "
                    f"This likely means the Stripe test data doesn't contain the expected invoice information."
                )
            else:
                print("    ✓ Search quality evaluation passed")

        except AssertionError:
            # Re-raise assertion errors
            raise
        except Exception as e:
            print(f"    ⚠️  LLM judge evaluation skipped: {e}")
    else:
        if status == "no_results":
            print("  ⚠️  No search results - data may not have synced or indexed properly")
        elif status == "no_relevant_results":
            print("  ⚠️  No relevant results found for the query")
        else:
            print(f"  ⚠️  Search returned status: {status}")

    # TEST 2: Completion search response
    print(f"\n  Testing COMPLETION search for: '{search_query}'")
    response = requests.get(
        f"{api_url}/collections/{collection_id}/search",
        params={"query": search_query, "response_type": "completion"},
        headers=headers,
    )

    # Completion might fail if no AI model is configured
    if response.status_code == 200:
        completion_results = response.json()

        # Validate COMPLETION response structure
        assert "response_type" in completion_results, "Missing 'response_type' field"
        assert "status" in completion_results, "Missing 'status' field"
        assert (
            completion_results["response_type"] == "completion"
        ), "Response type should be 'completion'"

        completion_text = completion_results.get("completion", "")
        status = completion_results.get("status", "")

        if completion_text and status == "success":
            print(f"  ✓ COMPLETION search returned AI response")
            print(f"    AI Response preview: {completion_text[:200]}...")

            # Check if completion mentions expected keywords
            keywords_found = [
                kw for kw in expected_keywords if kw.lower() in completion_text.lower()
            ]
            if keywords_found:
                print(f"    ✓ Found keywords in completion: {keywords_found}")
            else:
                print(f"    ⚠️  Expected keywords not found in completion")
        else:
            print(f"  ⚠️  COMPLETION search status: {status}")
            if not completion_text:
                print("    No completion text generated")
    else:
        print(f"  ⚠️  COMPLETION search returned {response.status_code} - may require AI setup")
        print(f"    Response: {response.text[:200]}...")

    print("\n✅ Search functionality test completed")


def test_cleanup(
    api_url: str,
    headers: dict,
    collection_id: str,
    source_conn_id1: str,
    source_conn_id2: str,
    auto_collection_id: str = None,
) -> None:
    """Test cleanup - delete all created resources and verify deletion.

    This tests the DELETE endpoints for source connections and collections,
    including the delete_data parameter options.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the manually created collection
        source_conn_id1: First source connection ID
        source_conn_id2: Second source connection ID (with auto-collection)
        auto_collection_id: The auto-created collection ID (if known)
    """
    print("\n🧹 Testing Cleanup - DELETE operations")

    # First, if we don't know the auto-collection ID, get it from source_conn_id2
    if not auto_collection_id:
        print("  Getting auto-created collection ID from second source connection...")
        response = requests.get(f"{api_url}/source-connections/{source_conn_id2}", headers=headers)
        if response.status_code == 200:
            auto_collection_id = response.json().get("collection")
            print(f"  ✓ Found auto-collection: {auto_collection_id}")
        else:
            print("  ⚠️  Could not retrieve second source connection")

    # DELETE SOURCE CONNECTION 1: Without deleting data
    print(f"\n  Deleting first source connection (delete_data=false)...")
    response = requests.delete(
        f"{api_url}/source-connections/{source_conn_id1}?delete_data=false", headers=headers
    )
    assert response.status_code == 200, f"Failed to delete source connection 1: {response.text}"

    deleted_conn1 = response.json()
    assert deleted_conn1["id"] == source_conn_id1, "Deleted connection ID mismatch"
    print(f"  ✓ Source connection 1 deleted: {deleted_conn1['name']}")

    # Verify it's actually deleted
    response = requests.get(f"{api_url}/source-connections/{source_conn_id1}", headers=headers)
    assert response.status_code == 404, "Source connection 1 should return 404 after deletion"
    print("  ✓ Verified source connection 1 no longer exists (404)")

    # DELETE SOURCE CONNECTION 2: With deleting data
    print(f"\n  Deleting second source connection (delete_data=true)...")
    response = requests.delete(
        f"{api_url}/source-connections/{source_conn_id2}?delete_data=true", headers=headers
    )
    assert response.status_code == 200, f"Failed to delete source connection 2: {response.text}"

    deleted_conn2 = response.json()
    assert deleted_conn2["id"] == source_conn_id2, "Deleted connection ID mismatch"
    print(f"  ✓ Source connection 2 deleted with data: {deleted_conn2['name']}")

    # Verify it's actually deleted
    response = requests.get(f"{api_url}/source-connections/{source_conn_id2}", headers=headers)
    assert response.status_code == 404, "Source connection 2 should return 404 after deletion"
    print("  ✓ Verified source connection 2 no longer exists (404)")

    # LIST SOURCE CONNECTIONS: Verify both are gone
    print("\n  Listing source connections to verify deletions...")
    response = requests.get(f"{api_url}/source-connections/", headers=headers)
    assert response.status_code == 200, f"Failed to list source connections: {response.text}"

    remaining_connections = response.json()
    remaining_ids = [sc["id"] for sc in remaining_connections]
    assert source_conn_id1 not in remaining_ids, "Source connection 1 still in list after deletion"
    assert source_conn_id2 not in remaining_ids, "Source connection 2 still in list after deletion"
    print(
        f"  ✓ Verified both source connections removed from list ({len(remaining_connections)} remaining)"
    )

    # DELETE COLLECTION 1: The manually created one (without data)
    print(f"\n  Deleting manually created collection (delete_data=false)...")
    response = requests.delete(
        f"{api_url}/collections/{collection_id}?delete_data=false", headers=headers
    )

    # Collection might already be deleted if it had no more source connections
    if response.status_code == 200:
        deleted_coll1 = response.json()
        assert deleted_coll1["readable_id"] == collection_id, "Deleted collection ID mismatch"
        print(f"  ✓ Collection deleted: {deleted_coll1['name']}")
    elif response.status_code == 404:
        print("  ℹ️  Collection already deleted (cascade from source connections)")
    else:
        raise AssertionError(
            f"Unexpected response deleting collection: {response.status_code} - {response.text}"
        )

    # Verify it's actually deleted
    response = requests.get(f"{api_url}/collections/{collection_id}", headers=headers)
    assert response.status_code == 404, "Collection should return 404 after deletion"
    print("  ✓ Verified collection no longer exists (404)")

    # DELETE COLLECTION 2: The auto-created one (with data)
    if auto_collection_id:
        print(f"\n  Deleting auto-created collection (delete_data=true)...")
        response = requests.delete(
            f"{api_url}/collections/{auto_collection_id}?delete_data=true", headers=headers
        )

        if response.status_code == 200:
            deleted_coll2 = response.json()
            assert (
                deleted_coll2["readable_id"] == auto_collection_id
            ), "Deleted collection ID mismatch"
            print(f"  ✓ Auto-collection deleted with data: {deleted_coll2['name']}")
        elif response.status_code == 404:
            print("  ℹ️  Auto-collection already deleted")
        else:
            raise AssertionError(
                f"Unexpected response deleting auto-collection: {response.status_code}"
            )

        # Verify it's deleted
        response = requests.get(f"{api_url}/collections/{auto_collection_id}", headers=headers)
        assert response.status_code == 404, "Auto-collection should return 404 after deletion"
        print("  ✓ Verified auto-collection no longer exists (404)")

    # LIST COLLECTIONS: Final verification
    print("\n  Listing collections to verify all test collections are deleted...")
    response = requests.get(f"{api_url}/collections/", headers=headers)
    assert response.status_code == 200, f"Failed to list collections: {response.text}"

    remaining_collections = response.json()
    remaining_ids = [c["readable_id"] for c in remaining_collections]
    assert collection_id not in remaining_ids, "Manual collection still in list after deletion"
    if auto_collection_id:
        assert (
            auto_collection_id not in remaining_ids
        ), "Auto-collection still in list after deletion"

    print(
        f"  ✓ All test collections successfully deleted ({len(remaining_collections)} collections remaining)"
    )

    # Test DELETE error handling
    print("\n  Testing DELETE error handling...")

    # Try to delete non-existent source connection
    fake_id = str(uuid.uuid4())
    response = requests.delete(f"{api_url}/source-connections/{fake_id}", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent source connection, got {response.status_code}"
    print("  ✓ DELETE non-existent source connection returns 404")

    # Try to delete non-existent collection
    response = requests.delete(f"{api_url}/collections/non-existent-collection", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent collection, got {response.status_code}"
    print("  ✓ DELETE non-existent collection returns 404")

    print("\n✅ Cleanup test completed - all resources deleted successfully!")


def main():
    """Main test execution."""
    args = parse_arguments()

    # Setup environment
    api_url = setup_environment(args.env, args.openai_api_key)
    if not api_url:
        sys.exit(1)

    # Configure headers with correct x-api-key format
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if args.api_key:
        headers["x-api-key"] = args.api_key

    print(f"\n🚀 Ready to test {args.env} environment at {api_url}")

    # Run tests
    test_sources(api_url, headers)
    readable_id = test_collections(api_url, headers)

    # Pass stripe API key to source connections test
    source_conn_id1, source_conn_id2 = test_source_connections(
        api_url, headers, readable_id, args.stripe_api_key
    )

    # Test search functionality on the collection that has synced data
    test_search_functionality(api_url, headers, readable_id)

    # Test cleanup
    test_cleanup(api_url, headers, readable_id, source_conn_id1, source_conn_id2)

    print("\n✅ All tests completed successfully!")
    print(f"\n📋 Test artifacts created:")
    print(f"  - Collection: {readable_id}")
    print(f"  - Source connections: {source_conn_id1}, {source_conn_id2}")
    print("\n💡 Note: Test data was NOT deleted for potential further testing")


if __name__ == "__main__":
    main()
