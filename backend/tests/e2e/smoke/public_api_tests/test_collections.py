"""
Test module for Collections CRUD operations.

This module tests the complete lifecycle of collections including:
- Creating collections with auto-generated readable_id
- Reading collections by ID
- Updating collection properties
- Listing collections with pagination
- Error handling for various edge cases
"""

import time
import requests
from .utils import show_backend_logs


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
