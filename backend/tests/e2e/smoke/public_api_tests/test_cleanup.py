"""
Test module for Cleanup operations.

This module tests the deletion of created resources including:
- Deleting source connections with and without data
- Deleting collections with and without data
- Verifying cascade deletions
- Error handling for non-existent resources
"""

import uuid
import requests


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
