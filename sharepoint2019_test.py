"""SharePoint 2019 V2 test - Sync data and verify ACL permissions.

Run with: poetry run python sharepoint2019_test.py

Modes (set FORCE_RESYNC variable):
  False (default): If collection exists, skip sync and run verify only.
                   If collection doesn't exist, create + sync + verify.
  True:            Delete existing collection (if any), then create + sync + verify.

This script:
1. Syncs SharePoint 2019 data to Airweave
2. Runs verify.py (static ACL tests from test 4)
3. Optionally runs incremental tests (test 5) to verify change handling
"""

import asyncio
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass
class SyncStats:
    """Statistics from a completed sync."""

    total_time_seconds: float
    entities_inserted: int
    entities_updated: int
    memberships_count: int = 0


# =============================================================================
# CONFIGURATION - Modify these as needed
# =============================================================================

# TODO: have to be able to re-generate items and access in SP and AD using the generate script

# Mode: Set to True to force delete and re-sync, False to reuse existing collection
# - FORCE_RESYNC=True: Delete collection → Full sync (60-80 min with 50K users) → Tests
# - FORCE_RESYNC=False: Reuse existing collection → Skip sync → Tests only (~1-2 min)
FORCE_RESYNC = True  # Reuse existing collection, run verification only

# Run static verification (verify.py from test 4)
RUN_STATIC_TESTS = True  # Run verify.py to test ACL correctness (fast, ~1-2 min)

# Run incremental tests (test 5)
RUN_INCREMENTAL_TESTS = (
    False  # Skip - each test triggers re-sync (~30-45 min each with 50K users)
)

# Incremental test markers to run (e.g., "critical" for security-critical only)
# Set to None to run all tests, or "critical" for security tests only
INCREMENTAL_TEST_MARKERS = None

# Airweave API
BASE_URL = "http://localhost:8001"

# Path to verify.py in infra-core repo (static tests)
VERIFY_SCRIPT_PATH = Path(
    "/Users/daanmanneke/Repositories/infra-core/"
    "sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator/verify.py"
)
MANIFEST_PATH = Path(
    "/Users/daanmanneke/Repositories/infra-core/"
    "sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator/output/manifest.json"
)
OUTPUT_PATH = Path(
    "/Users/daanmanneke/Repositories/infra-core/"
    "sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator/output/metrics.json"
)

# Path to incremental tests
INCREMENTAL_TESTS_PATH = Path(
    "/Users/daanmanneke/Repositories/infra-core/"
    "sharepoint-2019-trial/5-incremental-tests"
)

# Search destination for verify.py
SEARCH_DESTINATION = "vespa"  # or "qdrant"

# SharePoint 2019 credentials
SP_SITE_URL = "http://sharepoint-2019.demos.airweave.ai"
SP_USERNAME = "SP_Admin"
SP_PASSWORD = "FOKVgLLhxvyvPwFmY#"
SP_DOMAIN = "AIRWEAVE-SP2019"

# Active Directory credentials (for SID resolution)
AD_USERNAME = "sp2019admin"
AD_PASSWORD = "OEtJV0DenQDF21gug#"
AD_DOMAIN = "AIRWEAVE-SP2019"
AD_SERVER = "ldaps://108.143.169.156:636"
AD_SEARCH_BASE = "DC=AIRWEAVE-SP2019,DC=local"

# Fixed collection name - reused across runs
COLLECTION_NAME = "SharePoint 2019 V2 Test"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def get_collection_by_name(client: httpx.AsyncClient, name: str) -> dict | None:
    """Check if a collection with the given name exists."""
    response = await client.get(f"{BASE_URL}/collections/")
    response.raise_for_status()
    collections = response.json()

    for collection in collections:
        if collection.get("name") == name:
            return collection
    return None


async def delete_collection(client: httpx.AsyncClient, collection_id: str) -> bool:
    """Delete a collection by its readable ID."""
    try:
        response = await client.delete(f"{BASE_URL}/collections/{collection_id}")
        if response.status_code in (200, 204):
            return True
        print(f"   ⚠️ Delete returned status {response.status_code}: {response.text}")
        return False
    except Exception as e:
        print(f"   ❌ Error deleting collection: {e}")
        return False


async def get_membership_count(source_connection_id: str) -> int:
    """Query PostgreSQL directly to get membership count for the source connection."""
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            database="airweave",
            user="airweave",
            password="airweave1234!",
        )
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM access_control_membership
            WHERE source_connection_id = $1
            """,
            source_connection_id,
        )
        await conn.close()
        return count or 0
    except Exception as e:
        print(f"   ⚠️ Could not query membership count: {e}")
        return 0


def print_sync_summary(stats: SyncStats) -> None:
    """Print a beautiful summary of the sync performance."""
    total_entities = stats.entities_inserted + stats.entities_updated
    minutes = int(stats.total_time_seconds // 60)
    seconds = int(stats.total_time_seconds % 60)

    # Calculate rates
    entities_per_sec = (
        total_entities / stats.total_time_seconds if stats.total_time_seconds > 0 else 0
    )
    memberships_per_sec = (
        stats.memberships_count / stats.total_time_seconds
        if stats.total_time_seconds > 0
        else 0
    )

    print()
    print("╔" + "═" * 62 + "╗")
    print("║" + " " * 18 + "✨ SYNC COMPLETE ✨" + " " * 19 + "║")
    print("╠" + "═" * 62 + "╣")
    print("║" + " " * 62 + "║")
    print(f"║   ⏱️  Total Time:          {minutes:>3}m {seconds:02d}s" + " " * 26 + "║")
    print("║" + " " * 62 + "║")
    print("╠" + "─" * 62 + "╣")
    print("║   📄 ENTITIES" + " " * 48 + "║")
    print(f"║      • Inserted:          {stats.entities_inserted:>8,}" + " " * 22 + "║")
    print(f"║      • Updated:           {stats.entities_updated:>8,}" + " " * 22 + "║")
    print(f"║      • Total:             {total_entities:>8,}" + " " * 22 + "║")
    print(f"║      • Rate:              {entities_per_sec:>8.1f}/sec" + " " * 18 + "║")
    print("║" + " " * 62 + "║")
    print("╠" + "─" * 62 + "╣")
    print("║   🔐 ACL MEMBERSHIPS" + " " * 41 + "║")
    print(f"║      • Total:             {stats.memberships_count:>8,}" + " " * 22 + "║")
    print(
        f"║      • Rate:              {memberships_per_sec:>8.1f}/sec" + " " * 18 + "║"
    )
    print("║" + " " * 62 + "║")
    print("╚" + "═" * 62 + "╝")
    print()


async def wait_for_sync_completion(
    client: httpx.AsyncClient, source_connection_id: str
) -> SyncStats | None:
    """Wait indefinitely for sync to complete. Returns SyncStats if successful."""
    poll_interval = 5
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        # Get sync jobs for the source connection
        response = await client.get(
            f"{BASE_URL}/source-connections/{source_connection_id}/jobs",
        )
        response.raise_for_status()
        jobs = response.json()

        if jobs:
            latest_job = jobs[0]  # Most recent job
            status = latest_job.get("status", "unknown").lower()

            inserted = latest_job.get("entities_inserted", 0)
            updated = latest_job.get("entities_updated", 0)
            total = inserted + updated

            print(
                f"   [{int(elapsed)}s] Status: {status} | "
                f"Entities: {total} (inserted: {inserted}, updated: {updated})"
            )

            if status == "completed":
                # Get membership count
                memberships = await get_membership_count(source_connection_id)

                stats = SyncStats(
                    total_time_seconds=elapsed,
                    entities_inserted=inserted,
                    entities_updated=updated,
                    memberships_count=memberships,
                )

                # Print beautiful summary
                print_sync_summary(stats)

                return stats
            elif status in ("failed", "cancelled"):
                print(f"\n❌ Sync {status.upper()}")
                error = latest_job.get("error_message", "Unknown error")
                print(f"   Error: {error}")
                return None
        else:
            print(f"   [{int(elapsed)}s] Waiting for sync job to start...")

        await asyncio.sleep(poll_interval)


async def create_collection_and_sync(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Create a new collection and source connection, start sync.

    Returns: (collection_readable_id, collection_uuid, source_connection_id)
    """
    # Create collection
    print(f"   Creating collection '{COLLECTION_NAME}'...")

    response = await client.post(
        f"{BASE_URL}/collections/",
        json={"name": COLLECTION_NAME},
    )
    response.raise_for_status()
    collection = response.json()
    collection_id = collection["readable_id"]
    collection_uuid = collection["id"]
    print(f"✅ Created collection: {collection_id}")
    print(f"   UUID: {collection_uuid}")

    # Create SharePoint 2019 V2 source connection
    print("\n" + "=" * 60)
    print("Creating SharePoint 2019 V2 source connection...")
    print("=" * 60)

    print(f"   Site URL: {SP_SITE_URL}")
    print(f"   SP Domain: {SP_DOMAIN}")
    print(f"   AD Server: {AD_SERVER}")
    print(f"   AD Search Base: {AD_SEARCH_BASE}")

    response = await client.post(
        f"{BASE_URL}/source-connections/",
        json={
            "name": "SharePoint 2019 Test Connection",
            "short_name": "sharepoint2019v2",
            "readable_collection_id": collection_id,
            "authentication": {
                "credentials": {
                    "sharepoint_username": SP_USERNAME,
                    "sharepoint_password": SP_PASSWORD,
                    "sharepoint_domain": SP_DOMAIN,
                    "ad_username": AD_USERNAME,
                    "ad_password": AD_PASSWORD,
                    "ad_domain": AD_DOMAIN,
                }
            },
            "config": {
                "site_url": SP_SITE_URL,
                "ad_server": AD_SERVER,
                "ad_search_base": AD_SEARCH_BASE,
            },
            "sync_immediately": True,
        },
    )

    if response.status_code != 200:
        print(f"❌ Failed to create source connection: {response.status_code}")
        print(f"   Response: {response.text}")
        raise RuntimeError("Failed to create source connection")

    source_connection = response.json()
    source_connection_id = source_connection["id"]
    print(f"✅ Created source connection: {source_connection_id}")
    print(f"   Status: {source_connection.get('status', 'unknown')}")

    # Wait for sync to complete
    print("\n" + "=" * 60)
    print("Waiting for sync to complete (no timeout)...")
    print("=" * 60)

    sync_stats = await wait_for_sync_completion(client, source_connection_id)
    if not sync_stats:
        print("\n⚠️  Sync did not complete successfully, but continuing to verify...")

    return collection_id, collection_uuid, source_connection_id


def run_verify_script(collection_readable_id: str) -> int:
    """Run verify.py from the infra-core repo.

    Returns the exit code of the verify.py script.
    """
    print("\n" + "=" * 60)
    print("Running verify.py to validate ACL permissions...")
    print("=" * 60)

    if not VERIFY_SCRIPT_PATH.exists():
        print(f"❌ verify.py not found at: {VERIFY_SCRIPT_PATH}")
        print("   Make sure the infra-core repo path is correct.")
        return 1

    if not MANIFEST_PATH.exists():
        print(f"❌ manifest.json not found at: {MANIFEST_PATH}")
        print("   Run generate.py first to create the test data and manifest.")
        return 1

    # Build the command
    cmd = [
        sys.executable,  # Use the same Python interpreter
        str(VERIFY_SCRIPT_PATH),
        "--manifest",
        str(MANIFEST_PATH),
        "--airweave-url",
        BASE_URL,
        "--collection-id",
        collection_readable_id,
        "--destination",
        SEARCH_DESTINATION,
        "--output",
        str(OUTPUT_PATH),
    ]

    print("\n   Command: python verify.py \\")
    print(f"       --manifest {MANIFEST_PATH} \\")
    print(f"       --airweave-url {BASE_URL} \\")
    print(f"       --collection-id {collection_readable_id} \\")
    print(f"       --destination {SEARCH_DESTINATION} \\")
    print(f"       --output {OUTPUT_PATH}")
    print()

    # Run verify.py - use the venv from the test-data-generator directory
    venv_python = VERIFY_SCRIPT_PATH.parent / "venv" / "bin" / "python"
    if venv_python.exists():
        cmd[0] = str(venv_python)
        print(f"   Using venv: {venv_python}")
    else:
        print(f"   ⚠️ No venv found at {venv_python}, using system Python")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(VERIFY_SCRIPT_PATH.parent),
            capture_output=False,  # Show output in real-time
        )
        return result.returncode
    except Exception as e:
        print(f"❌ Error running verify.py: {e}")
        return 1


async def get_source_connection_id_for_collection(
    client: httpx.AsyncClient, collection_readable_id: str
) -> str | None:
    """Get the source connection ID for the collection's SharePoint source."""
    try:
        # Get all source connections and filter by collection
        response = await client.get(f"{BASE_URL}/source-connections/")
        if response.status_code == 200:
            source_connections = response.json()
            for sc in source_connections:
                if sc.get("readable_collection_id") == collection_readable_id:
                    return sc["id"]
    except Exception as e:
        print(f"   ⚠️ Could not get source connection ID: {e}")
    return None


def run_incremental_tests(
    collection_readable_id: str,
    collection_uuid: str,
    source_connection_id: str,
    markers: str | None = None,
) -> int:
    """Run incremental tests from test 5.

    Args:
        collection_readable_id: The collection's readable ID
        collection_uuid: The collection's UUID
        source_connection_id: The source connection ID for triggering syncs
        markers: Pytest markers to filter tests (e.g., "critical", "permission")

    Returns the exit code of the pytest run.
    """
    print("\n" + "=" * 60)
    print("Running Incremental Tests (Test 5)...")
    print("=" * 60)

    if not INCREMENTAL_TESTS_PATH.exists():
        print(f"❌ Incremental tests not found at: {INCREMENTAL_TESTS_PATH}")
        print("   Make sure the infra-core repo path is correct.")
        return 1

    # Set environment variables for the tests
    env = os.environ.copy()
    env.update(
        {
            "COLLECTION_READABLE_ID": collection_readable_id,
            "COLLECTION_UUID": collection_uuid,
            "SOURCE_CONNECTION_ID": source_connection_id,
            "AIRWEAVE_API_URL": BASE_URL,
            "SHAREPOINT_URL": SP_SITE_URL,
            "SHAREPOINT_USERNAME": SP_USERNAME,
            "SHAREPOINT_PASSWORD": SP_PASSWORD,
            "SHAREPOINT_DOMAIN": SP_DOMAIN,
            "AD_SERVER": AD_SERVER,
            "AD_USERNAME": AD_USERNAME,
            "AD_PASSWORD": AD_PASSWORD,
            "AD_DOMAIN": AD_DOMAIN,
            "AD_SEARCH_BASE": AD_SEARCH_BASE,
            "SEARCH_DESTINATION": SEARCH_DESTINATION,
            # PostgreSQL credentials for direct DB inspection
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "airweave",
            "POSTGRES_USER": "airweave",
            "POSTGRES_PASSWORD": "airweave1234!",
        }
    )

    # Build pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(INCREMENTAL_TESTS_PATH / "tests"),
        "-v",
        "--tb=short",
    ]

    # Add marker filter if specified
    if markers:
        cmd.extend(["-m", markers])
        print(f"   Running tests with marker: {markers}")
    else:
        print("   Running all incremental tests")

    print(f"\n   Collection: {collection_readable_id}")
    print(f"   Source Connection: {source_connection_id}")
    print()

    # Check for venv
    venv_python = INCREMENTAL_TESTS_PATH / "venv" / "bin" / "python"
    if venv_python.exists():
        cmd[0] = str(venv_python)
        print(f"   Using venv: {venv_python}")
    else:
        print(f"   ⚠️ No venv found at {venv_python}, using system Python")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(INCREMENTAL_TESTS_PATH),
            env=env,
            capture_output=False,
        )
        return result.returncode
    except Exception as e:
        print(f"❌ Error running incremental tests: {e}")
        return 1


# =============================================================================
# MAIN
# =============================================================================


async def main():
    """Run the SharePoint 2019 V2 sync and verification test."""
    print("\n" + "=" * 60)
    print("SharePoint 2019 V2 ACL Test")
    print("=" * 60)
    print(f"   Mode: {'FORCE_RESYNC' if FORCE_RESYNC else 'REUSE_EXISTING'}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Destination: {SEARCH_DESTINATION}")
    print(f"   Static Tests (Test 4): {'YES' if RUN_STATIC_TESTS else 'NO'}")
    print(f"   Incremental Tests (Test 5): {'YES' if RUN_INCREMENTAL_TESTS else 'NO'}")
    if RUN_INCREMENTAL_TESTS:
        print(f"   Incremental Markers: {INCREMENTAL_TEST_MARKERS or 'ALL'}")
    print()

    source_connection_id = None

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # =================================================================
            # 1. Check if collection already exists
            # =================================================================
            print("\n" + "=" * 60)
            print("1. Checking for existing collection...")
            print("=" * 60)

            existing_collection = await get_collection_by_name(client, COLLECTION_NAME)

            if existing_collection:
                collection_id = existing_collection["readable_id"]
                collection_uuid = existing_collection["id"]
                print(f"✅ Found existing collection: {collection_id}")
                print(f"   UUID: {collection_uuid}")

                if FORCE_RESYNC:
                    # Delete existing collection and re-sync
                    print("\n   FORCE_RESYNC=True - Deleting existing collection...")
                    deleted = await delete_collection(client, collection_id)
                    if deleted:
                        print(f"   ✅ Deleted collection: {collection_id}")
                        # Wait a moment for cleanup
                        await asyncio.sleep(2)
                    else:
                        print("   ⚠️ Failed to delete, will try to create anyway...")

                    # Create new collection and sync
                    print("\n" + "=" * 60)
                    print("2. Creating new collection and syncing...")
                    print("=" * 60)
                    (
                        collection_id,
                        collection_uuid,
                        source_connection_id,
                    ) = await create_collection_and_sync(client)
                else:
                    # Reuse existing - skip sync
                    print(
                        "\n   FORCE_RESYNC=False - Skipping sync, will run verify only"
                    )
                    # Get source connection ID for incremental tests
                    source_connection_id = (
                        await get_source_connection_id_for_collection(
                            client, collection_id
                        )
                    )
                    if source_connection_id:
                        print(f"   Source Connection: {source_connection_id}")
            else:
                # Collection doesn't exist - create and sync
                print(f"   Collection '{COLLECTION_NAME}' not found.")

                print("\n" + "=" * 60)
                print("2. Creating collection and syncing...")
                print("=" * 60)
                (
                    collection_id,
                    collection_uuid,
                    source_connection_id,
                ) = await create_collection_and_sync(client)

            # =================================================================
            # 2. Run verify.py (Static Tests - Test 4) - if enabled
            # =================================================================
            if RUN_STATIC_TESTS:
                # Small delay to ensure writes are committed
                await asyncio.sleep(3)

                verify_exit_code = run_verify_script(collection_id)

                if verify_exit_code == 0:
                    print("\n" + "=" * 60)
                    print("🎉 Static verification (Test 4) completed successfully!")
                    print("=" * 60)
                else:
                    print("\n" + "=" * 60)
                    print(
                        f"⚠️ Static verification completed with exit code: {verify_exit_code}"
                    )
                    print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("Skipping static verification (RUN_STATIC_TESTS=False)")
                print("=" * 60)

            # =================================================================
            # 3. Run Incremental Tests (Test 5) - if enabled
            # =================================================================
            if RUN_INCREMENTAL_TESTS:
                if not source_connection_id:
                    print(
                        "\n⚠️ Cannot run incremental tests: source_connection_id not available"
                    )
                else:
                    incremental_exit_code = run_incremental_tests(
                        collection_readable_id=collection_id,
                        collection_uuid=collection_uuid,
                        source_connection_id=source_connection_id,
                        markers=INCREMENTAL_TEST_MARKERS,
                    )

                    if incremental_exit_code == 0:
                        print("\n" + "=" * 60)
                        print("🎉 Incremental tests (Test 5) completed successfully!")
                        print("=" * 60)
                    else:
                        print("\n" + "=" * 60)
                        print(
                            f"⚠️ Incremental tests completed with exit code: {incremental_exit_code}"
                        )
                        print("=" * 60)

        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
            raise

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
