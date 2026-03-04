"""
E2E smoke tests for continuous/incremental sync.

Uses the incremental_stub source to verify that cursor-based incremental
sync works correctly end-to-end through the public API:

1. Phase 1 (Full Sync): Create connection with entity_count=5 -> sync -> verify
   all 6 entities synced (5 + container) and cursor is stored.
2. Phase 2 (Incremental Sync): Update config to entity_count=10 -> trigger sync
   -> verify only 5 NEW entities were inserted (not a full re-sync of all 10).
3. Phase 3 (No-change Sync): Trigger sync with same config -> verify no new
   entities inserted (only updates/keeps).
"""

import asyncio
import atexit
import time

import httpx
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, List, Optional


def _cleanup_resources():
    """Cleanup test resources on process exit."""
    global _cleanup_connection_ids, _cleanup_collection_readable_id

    if not _cleanup_connection_ids and not _cleanup_collection_readable_id:
        return

    try:
        from config import settings

        import httpx as httpx_sync

        with httpx_sync.Client(
            base_url=settings.api_url,
            headers=settings.api_headers,
            timeout=30,
        ) as client:
            for conn_id in _cleanup_connection_ids:
                try:
                    client.delete(f"/source-connections/{conn_id}")
                except Exception:
                    pass

            if _cleanup_collection_readable_id:
                try:
                    client.delete(f"/collections/{_cleanup_collection_readable_id}")
                except Exception:
                    pass
    except Exception:
        pass


_cleanup_connection_ids: List[str] = []
_cleanup_collection_readable_id: Optional[str] = None
atexit.register(_cleanup_resources)


@pytest_asyncio.fixture(scope="function")
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for incremental sync tests."""
    from config import settings

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(60),
        follow_redirects=True,
    ) as client:
        yield client


async def wait_for_sync(
    client: httpx.AsyncClient,
    connection_id: str,
    max_wait_time: int = 180,
    poll_interval: int = 3,
) -> bool:
    """Wait for a source connection sync job to successfully complete.

    Returns True if sync completed successfully, False otherwise.
    """
    elapsed = 0
    while elapsed < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        status_response = await client.get(f"/source-connections/{connection_id}")
        if status_response.status_code != 200:
            continue

        conn_details = status_response.json()
        sync_info = conn_details.get("sync")
        if sync_info and sync_info.get("last_job"):
            job_status = sync_info["last_job"].get("status")
            if job_status == "completed":
                return True
            if job_status in ["failed", "cancelled"]:
                return False

        if conn_details.get("status") == "error":
            return False

    return False


async def get_last_job_details(
    client: httpx.AsyncClient, connection_id: str
) -> Dict:
    """Get the last sync job details from the connection endpoint."""
    response = await client.get(f"/source-connections/{connection_id}")
    assert response.status_code == 200, f"Failed to get connection: {response.text}"
    conn = response.json()
    sync_info = conn.get("sync", {})
    last_job = sync_info.get("last_job")
    assert last_job is not None, "No last_job found in connection sync info"
    return last_job


async def get_jobs(
    client: httpx.AsyncClient, connection_id: str
) -> List[Dict]:
    """Get all sync jobs for a connection (newest first)."""
    response = await client.get(f"/source-connections/{connection_id}/jobs")
    assert response.status_code == 200, f"Failed to get jobs: {response.text}"
    return response.json()


# =============================================================================
# INCREMENTAL SYNC TEST
# =============================================================================


@pytest.mark.asyncio
async def test_incremental_sync_three_phases(api_client: httpx.AsyncClient):
    """Test the full incremental sync lifecycle: full sync -> incremental -> no-op.

    Phase 1: Full sync with entity_count=5
      - Creates 6 entities (5 data + 1 container)
      - Cursor is stored with last_entity_index=4
      - entities_inserted = 6

    Phase 2: Incremental sync after config update to entity_count=10
      - Source reads cursor (last_entity_index=4)
      - Only generates entities 5-9 (5 new entities + container re-emitted)
      - entities_inserted = 5, entities_updated >= 1 (container)

    Phase 3: No-op sync with same config (entity_count=10)
      - Source reads cursor (last_entity_index=9)
      - No new entities to generate (only container re-emitted with same content)
      - entities_inserted = 0, entities_updated = 0 (container hash unchanged = KEEP)
    """
    global _cleanup_connection_ids, _cleanup_collection_readable_id

    client = api_client

    # =========================================================================
    # Setup: Create collection
    # =========================================================================
    collection_name = f"Incremental Sync Test {int(time.time())}"
    response = await client.post("/collections/", json={"name": collection_name})
    assert response.status_code == 200, f"Failed to create collection: {response.text}"

    collection = response.json()
    readable_id = collection["readable_id"]
    _cleanup_collection_readable_id = readable_id
    print(f"\n[setup] Created collection: {readable_id}")

    # =========================================================================
    # Phase 1: Full Sync (entity_count=5)
    # =========================================================================
    print("\n" + "=" * 60)
    print("PHASE 1: Full sync with entity_count=5")
    print("=" * 60)

    connection_data = {
        "name": f"Inc Stub Test {int(time.time())}",
        "short_name": "incremental_stub",
        "readable_collection_id": readable_id,
        "authentication": {"credentials": {"stub_key": "test"}},
        "config": {
            "seed": 42,
            "entity_count": 5,
        },
        "sync_immediately": True,
    }

    response = await client.post("/source-connections", json=connection_data)
    assert response.status_code == 200, (
        f"Failed to create incremental_stub connection: {response.text}"
    )

    connection = response.json()
    connection_id = connection["id"]
    _cleanup_connection_ids.append(connection_id)
    print(f"[phase1] Created connection: {connection_id}")

    # Wait for first sync to complete
    sync_ok = await wait_for_sync(client, connection_id)
    assert sync_ok, "Phase 1 sync did not complete successfully"
    print("[phase1] Sync completed")

    # Get job details for phase 1
    phase1_job = await get_last_job_details(client, connection_id)
    print(f"[phase1] Job details: {phase1_job}")

    # Phase 1 assertions:
    # - 6 entities inserted: 1 container + 5 data entities
    p1_inserted = phase1_job["entities_inserted"]
    assert p1_inserted == 6, (
        f"Phase 1: expected 6 entities inserted (1 container + 5 data), got {p1_inserted}"
    )
    assert phase1_job["entities_updated"] == 0, (
        f"Phase 1: expected 0 updates on first sync, got {phase1_job['entities_updated']}"
    )
    print(f"[phase1] PASS: {p1_inserted} entities inserted, 0 updated")

    # =========================================================================
    # Phase 2: Incremental Sync (entity_count=5 -> 10)
    # =========================================================================
    print("\n" + "=" * 60)
    print("PHASE 2: Incremental sync with entity_count=10")
    print("=" * 60)

    # Update config to add more entities
    update_response = await client.patch(
        f"/source-connections/{connection_id}",
        json={"config": {"entity_count": 10, "seed": 42}},
    )
    assert update_response.status_code == 200, (
        f"Failed to update config: {update_response.text}"
    )
    print("[phase2] Updated entity_count to 10")

    # Trigger incremental sync
    run_response = await client.post(f"/source-connections/{connection_id}/run")
    assert run_response.status_code == 200, (
        f"Failed to trigger sync: {run_response.text}"
    )
    print("[phase2] Triggered incremental sync")

    # Wait for sync to complete
    sync_ok = await wait_for_sync(client, connection_id)
    assert sync_ok, "Phase 2 sync did not complete successfully"
    print("[phase2] Sync completed")

    # Get job details for phase 2
    phase2_job = await get_last_job_details(client, connection_id)
    print(f"[phase2] Job details: {phase2_job}")

    # Phase 2 assertions:
    # - 5 new entities inserted (indices 5-9)
    # - Container and existing entities should be updated/kept, not re-inserted
    p2_inserted = phase2_job["entities_inserted"]
    p2_updated = phase2_job["entities_updated"]

    assert p2_inserted == 5, (
        f"Phase 2: expected 5 new entities inserted (indices 5-9), got {p2_inserted}. "
        f"If {p2_inserted} > 5, the cursor was not used (full re-sync happened). "
        f"If {p2_inserted} < 5, some entities were missed."
    )
    # Container entity should be updated (re-emitted with same entity_id)
    assert p2_updated >= 1, (
        f"Phase 2: expected at least 1 entity updated (container), got {p2_updated}"
    )
    print(f"[phase2] PASS: {p2_inserted} entities inserted, {p2_updated} updated")

    # =========================================================================
    # Phase 3: No-op Sync (same config, entity_count=10)
    # =========================================================================
    print("\n" + "=" * 60)
    print("PHASE 3: No-op sync with same entity_count=10")
    print("=" * 60)

    # Trigger another sync without changing config
    run_response = await client.post(f"/source-connections/{connection_id}/run")
    assert run_response.status_code == 200, (
        f"Failed to trigger sync: {run_response.text}"
    )
    print("[phase3] Triggered no-op sync")

    # Wait for sync to complete
    sync_ok = await wait_for_sync(client, connection_id)
    assert sync_ok, "Phase 3 sync did not complete successfully"
    print("[phase3] Sync completed")

    # Get job details for phase 3
    phase3_job = await get_last_job_details(client, connection_id)
    print(f"[phase3] Job details: {phase3_job}")

    # Phase 3 assertions:
    # - 0 new entities inserted (cursor is at last_entity_index=9, entity_count=10)
    # - 0 entities updated: container is re-emitted with identical content,
    #   so the entity pipeline resolves it as KEEP (same hash), not UPDATE.
    p3_inserted = phase3_job["entities_inserted"]
    p3_updated = phase3_job["entities_updated"]

    assert p3_inserted == 0, (
        f"Phase 3: expected 0 entities inserted (no new data), got {p3_inserted}. "
        f"If {p3_inserted} > 0, the cursor was not properly persisted."
    )
    assert p3_updated == 0, (
        f"Phase 3: expected 0 entities updated (all unchanged = KEEP), got {p3_updated}"
    )
    print(f"[phase3] PASS: {p3_inserted} entities inserted, {p3_updated} updated (all KEEP)")

    # =========================================================================
    # Verify total entity count via job history
    # =========================================================================
    jobs = await get_jobs(client, connection_id)
    assert len(jobs) >= 3, f"Expected at least 3 sync jobs, got {len(jobs)}"
    print(f"\n[summary] Total sync jobs: {len(jobs)}")

    total_inserted = sum(j["entities_inserted"] for j in jobs)
    print(f"[summary] Total entities inserted across all syncs: {total_inserted}")
    # 6 (phase 1) + 5 (phase 2) + 0 (phase 3) = 11
    assert total_inserted == 11, (
        f"Expected 11 total entities inserted (6 + 5 + 0), got {total_inserted}"
    )
    print("[summary] ALL PHASES PASSED")


@pytest.mark.asyncio
async def test_force_full_sync_ignores_cursor(api_client: httpx.AsyncClient):
    """Test that force_full_sync=true ignores the cursor and does a full re-sync.

    1. Create connection with entity_count=5 -> sync (6 entities inserted)
    2. Reduce entity_count to 3 + force_full_sync=true
       - Without force_full_sync: cursor says last_entity_index=4, start=5, no new entities
       - With force_full_sync: cursor skipped, full sync from index 0, yields 4 entities
         (container + 3 data). Entities at indices 3-4 become orphans and are deleted.

    This proves force_full_sync actually ignores the cursor because:
    - If cursor were used, 0 entities would be emitted (start_index=5, entity_count=3)
    - With cursor skipped, all 3 data entities are re-emitted from index 0
    """
    global _cleanup_connection_ids, _cleanup_collection_readable_id

    client = api_client

    # Create collection
    collection_name = f"Force Full Sync Test {int(time.time())}"
    response = await client.post("/collections/", json={"name": collection_name})
    assert response.status_code == 200, f"Failed to create collection: {response.text}"

    collection = response.json()
    readable_id = collection["readable_id"]
    _cleanup_collection_readable_id = readable_id

    # Create connection and initial sync with entity_count=5
    connection_data = {
        "name": f"Force Sync Test {int(time.time())}",
        "short_name": "incremental_stub",
        "readable_collection_id": readable_id,
        "authentication": {"credentials": {"stub_key": "test"}},
        "config": {"seed": 99, "entity_count": 5},
        "sync_immediately": True,
    }

    response = await client.post("/source-connections", json=connection_data)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"

    connection = response.json()
    connection_id = connection["id"]
    _cleanup_connection_ids.append(connection_id)

    # Wait for first sync
    sync_ok = await wait_for_sync(client, connection_id)
    assert sync_ok, "Initial sync failed"

    phase1_job = await get_last_job_details(client, connection_id)
    assert phase1_job["entities_inserted"] == 6, (
        f"Expected 6 entities inserted, got {phase1_job['entities_inserted']}"
    )
    print(f"[phase1] Initial sync: {phase1_job['entities_inserted']} inserted")

    # Reduce entity_count to 3, then force full sync.
    # force_full_sync skips cursor loading, so source does a full sync from
    # index 0 with entity_count=3: re-emits container + entities 0,1,2.
    # Entities 3 and 4 are not re-emitted -> orphan cleanup deletes them.
    update_response = await client.patch(
        f"/source-connections/{connection_id}",
        json={"config": {"seed": 99, "entity_count": 3}},
    )
    assert update_response.status_code == 200, (
        f"Failed to update config: {update_response.text}"
    )
    print("[phase2] Updated entity_count from 5 to 3")

    run_response = await client.post(
        f"/source-connections/{connection_id}/run?force_full_sync=true"
    )
    assert run_response.status_code == 200, (
        f"Failed to trigger force full sync: {run_response.text}"
    )
    print("[phase2] Triggered force_full_sync")

    sync_ok = await wait_for_sync(client, connection_id)
    assert sync_ok, "Force full sync failed"

    phase2_job = await get_last_job_details(client, connection_id)
    print(
        f"[phase2] Force sync: inserted={phase2_job['entities_inserted']}, "
        f"updated={phase2_job['entities_updated']}, "
        f"deleted={phase2_job['entities_deleted']}"
    )

    p2_inserted = phase2_job["entities_inserted"]
    p2_deleted = phase2_job["entities_deleted"]

    # Container + entities 0,1,2 are re-emitted with identical content -> KEEP (0 inserts).
    # If the cursor were used, we'd get 0 emitted entities entirely (start_index > entity_count).
    # The fact that we get 0 inserts (not a failure) AND deletions proves the cursor was skipped.
    assert p2_inserted == 0, (
        f"Force full sync: expected 0 new inserts (entities 0-2 unchanged), got {p2_inserted}"
    )
    # Entities at indices 3 and 4 should be deleted as orphans
    assert p2_deleted == 2, (
        f"Force full sync: expected 2 deletions (orphaned entities at indices 3-4), "
        f"got {p2_deleted}. If 0, the cursor may not have been skipped "
        f"(no entities re-emitted = no orphan detection)."
    )
    print("[phase2] PASS: Force full sync correctly orphaned removed entities")
