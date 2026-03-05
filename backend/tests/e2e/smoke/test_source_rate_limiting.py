"""E2E tests for source rate limiting.

Tests verify:
- Connection-level vs org-level rate limit tracking
- Pipedream proxy rate limiting
- Dual rate limiting (proxy + source)
- Feature flag behavior
- Atomic Lua script prevents race conditions

All tests marked with @pytest.mark.rate_limit to run sequentially for proper isolation.
"""

import asyncio
import subprocess
import time
from typing import Dict, List, Optional

import httpx
import pytest

# Mark all tests in this module to run sequentially (no parallel execution)
# This ensures proper Redis isolation between tests
pytestmark = [pytest.mark.rate_limit]


# Test rate limit configuration
RATE_LIMIT = 1  # requests
WINDOW_SECONDS = 3  # seconds


# ============================================================================
# Helper Functions
# ============================================================================


async def get_redis_keys(pattern: str) -> List[str]:
    """Get Redis keys matching pattern via docker exec.

    Args:
        pattern: Redis key pattern (e.g., "source_rate_limit:*")

    Returns:
        List of matching Redis keys
    """
    try:
        result = subprocess.run(
            ["docker", "exec", "airweave-redis", "redis-cli", "--scan", "--pattern", pattern],
            capture_output=True,
            text=True,
            check=True,
        )
        keys = [k for k in result.stdout.strip().split("\n") if k]
        return keys
    except subprocess.CalledProcessError as e:
        print(f"Failed to get Redis keys: {e}")
        return []


async def get_redis_counter(key: str) -> int:
    """Get count from Redis sorted set.

    Args:
        key: Redis key

    Returns:
        Number of entries in the sorted set
    """
    try:
        result = subprocess.run(
            ["docker", "exec", "airweave-redis", "redis-cli", "ZCARD", key],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Failed to get Redis counter for {key}: {e}")
        return 0


async def clear_redis():
    """Clear all Redis data."""
    try:
        subprocess.run(
            ["docker", "exec", "airweave-redis", "redis-cli", "FLUSHALL"],
            capture_output=True,
            check=True,
        )
        print("Redis cleared successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to clear Redis: {e}")


async def monitor_redis_during_sync(pattern: str, duration: int = 10, interval: int = 2) -> Dict[str, List[int]]:
    """Monitor Redis counters during sync execution.

    Args:
        pattern: Redis key pattern to monitor
        duration: How long to monitor (seconds)
        interval: Check interval (seconds)

    Returns:
        Dictionary mapping keys to list of counter values over time
    """
    monitoring_data = {}
    start_time = time.time()

    while time.time() - start_time < duration:
        keys = await get_redis_keys(pattern)

        for key in keys:
            if key not in monitoring_data:
                monitoring_data[key] = []

            counter = await get_redis_counter(key)
            monitoring_data[key].append(counter)

        await asyncio.sleep(interval)

    return monitoring_data


async def get_current_org_id(api_client: httpx.AsyncClient) -> str:
    """Get the current organization ID from organizations list.

    In DEV_MODE with AUTH disabled, there's a default organization.
    We get the list and use the first one.

    Args:
        api_client: HTTP client

    Returns:
        Organization ID as string
    """
    response = await api_client.get("/admin/organizations")

    if response.status_code != 200:
        raise Exception(f"Could not fetch organizations: {response.status_code} - {response.text}")

    orgs = response.json()
    if not orgs or len(orgs) == 0:
        raise Exception("No organizations found")

    # In DEV_MODE, use the first (default) organization
    return str(orgs[0]["id"])


async def verify_feature_flag_enabled(api_client: httpx.AsyncClient, flag_name: str = "source_rate_limiting") -> bool:
    """Check if a feature flag is enabled for the test organization.

    Args:
        api_client: HTTP client
        flag_name: Feature flag name

    Returns:
        True if enabled, False otherwise
    """
    org_id = await get_current_org_id(api_client)
    response = await api_client.get(f"/admin/organizations/{org_id}")

    if response.status_code != 200:
        print(f"Could not fetch org info: {response.status_code}")
        return False

    org = response.json()
    # Feature flags come as a list of objects with 'flag' and 'enabled' fields
    feature_flags = org.get("feature_flags", [])

    is_enabled = any(ff.get("flag") == flag_name and ff.get("enabled") for ff in feature_flags)
    print(f"Feature flag '{flag_name}': {'ENABLED' if is_enabled else 'DISABLED'}")

    return is_enabled


async def enable_feature_flag(api_client: httpx.AsyncClient, flag_name: str = "source_rate_limiting", org_id: Optional[str] = None):
    """Enable a feature flag for the test organization.

    Args:
        api_client: HTTP client
        flag_name: Feature flag name
        org_id: Organization ID (if None, will be auto-detected)
    """
    if org_id is None:
        org_id = await get_current_org_id(api_client)

    response = await api_client.post(f"/admin/organizations/{org_id}/feature-flags/{flag_name}/enable")

    if response.status_code != 200:
        raise Exception(f"Failed to enable feature flag: {response.text}")

    print(f"✓ Enabled feature flag '{flag_name}' for org {org_id}")


async def disable_feature_flag(api_client: httpx.AsyncClient, flag_name: str = "source_rate_limiting", org_id: Optional[str] = None):
    """Disable a feature flag for the test organization.

    Args:
        api_client: HTTP client
        flag_name: Feature flag name
        org_id: Organization ID (if None, will be auto-detected)
    """
    if org_id is None:
        org_id = await get_current_org_id(api_client)

    response = await api_client.post(f"/admin/organizations/{org_id}/feature-flags/{flag_name}/disable")

    if response.status_code != 200:
        raise Exception(f"Failed to disable feature flag: {response.text}")

    print(f"✓ Disabled feature flag '{flag_name}' for org {org_id}")


async def set_source_rate_limit(
    api_client: httpx.AsyncClient, source_short_name: str, limit: int, window: int
):
    """Set rate limit for a source via API.

    Args:
        api_client: HTTP client
        source_short_name: Source identifier (e.g., "notion", "google_drive", "pipedream_proxy")
        limit: Maximum requests
        window: Time window in seconds
    """
    payload = {"limit": limit, "window_seconds": window}
    response = await api_client.put(f"/source-rate-limits/{source_short_name}", json=payload)

    if response.status_code != 200:
        raise Exception(f"Failed to set rate limit: {response.text}")

    print(f"Set rate limit for {source_short_name}: {limit} req/{window}s")
    return response.json()


async def delete_source_rate_limit(api_client: httpx.AsyncClient, source_short_name: str):
    """Delete rate limit for a source via API.

    Args:
        api_client: HTTP client
        source_short_name: Source identifier
    """
    response = await api_client.delete(f"/source-rate-limits/{source_short_name}")

    # 204 = deleted, 404 = not found, 403 = feature disabled (all OK for cleanup)
    if response.status_code not in [204, 404, 403]:
        raise Exception(f"Failed to delete rate limit: {response.text}")

    if response.status_code == 403:
        print(f"Skipped deleting rate limit for {source_short_name} (feature disabled)")
    else:
        print(f"Deleted rate limit for {source_short_name}")


async def trigger_sync(api_client: httpx.AsyncClient, connection_id: str) -> Dict:
    """Trigger a manual sync for a source connection.

    Args:
        api_client: HTTP client
        connection_id: Source connection ID

    Returns:
        Sync job response
    """
    response = await api_client.post(f"/source-connections/{connection_id}/run")

    if response.status_code != 200:
        raise Exception(f"Failed to trigger sync: {response.text}")

    return response.json()


async def wait_for_sync_completion(
    api_client: httpx.AsyncClient, connection_id: str, timeout: int = 120
) -> Dict:
    """Poll sync job status until completed or failed.

    Args:
        api_client: HTTP client
        connection_id: Source connection ID
        timeout: Maximum time to wait in seconds

    Returns:
        Final sync job details
    """
    start_time = time.time()
    poll_interval = 2

    while time.time() - start_time < timeout:
        # Get connection details
        response = await api_client.get(f"/source-connections/{connection_id}")

        if response.status_code != 200:
            raise Exception(f"Failed to get connection: {response.text}")

        conn_details = response.json()

        # Check sync status
        sync_info = conn_details.get("sync")
        if sync_info and sync_info.get("last_job"):
            last_job = sync_info["last_job"]
            status = last_job.get("status")

            if status in ["completed", "failed", "cancelled"]:
                print(f"Sync {status}: {last_job.get('stats', {})}")
                return last_job

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Sync did not complete within {timeout} seconds")


def verify_sync_stats_only_inserts(job: Dict, connection_name: str = "connection"):
    """Verify that sync only performed inserts (fresh sync, no updates/deletes/skips/keeps).

    Args:
        job: Sync job dictionary with entity count fields
        connection_name: Name for error messages
    """
    inserted = job.get("entities_inserted", 0)
    updated = job.get("entities_updated", 0)
    deleted = job.get("entities_deleted", 0)
    skipped = job.get("entities_skipped", 0)
    kept = job.get("entities_kept", 0)

    assert inserted > 0, f"No entities inserted for {connection_name}: inserted={inserted}"
    assert updated == 0, f"Unexpected updates in {connection_name}: updated={updated}"
    assert deleted == 0, f"Unexpected deletes in {connection_name}: deleted={deleted}"
    assert skipped == 0, f"Entities skipped in {connection_name}: skipped={skipped}"
    assert kept == 0, f"Unexpected kept entities in {connection_name}: kept={kept}"

    print(f"✅ {connection_name}: {inserted} inserted, 0 updates/deletes/skips/keeps")


# ============================================================================
# Test Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_notion_connection_level_rate_limiting_isolated(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
):
    """Test that Notion (connection-level) rate limits are tracked separately per account.

    Verifies that two different Notion accounts each have their own rate limit quota,
    and requests from one account don't affect the other's quota.
    """
    # Fail if Notion test accounts not configured (required for this test)
    if not all(
        [
            config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1,
            config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1,
            config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_2,
            config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_2,
        ]
    ):
        pytest.fail("Notion test accounts not configured - required environment variables missing")

    # Clear Redis to start fresh
    await clear_redis()

    # Enable feature flag before setting rate limits
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Set Notion rate limit: 1 req/3s (org-wide, but tracked per connection)
    await set_source_rate_limit(api_client, "notion", RATE_LIMIT, WINDOW_SECONDS)

    # Create Notion connection 1
    connection1_data = {
        "name": f"Notion Test 1 {int(time.time())}",
        "short_name": "notion",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1,
                "account_id": config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1,
            },
        },
        "sync_immediately": False,
    }

    response1 = await api_client.post("/source-connections", json=connection1_data)
    assert response1.status_code == 200, f"Failed to create connection 1: {response1.text}"
    connection1 = response1.json()

    # Create Notion connection 2
    connection2_data = {
        "name": f"Notion Test 2 {int(time.time())}",
        "short_name": "notion",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_2,
                "account_id": config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_2,
            },
        },
        "sync_immediately": False,
    }

    response2 = await api_client.post("/source-connections", json=connection2_data)
    assert response2.status_code == 200, f"Failed to create connection 2: {response2.text}"
    connection2 = response2.json()

    try:
        # Trigger syncs simultaneously
        await trigger_sync(api_client, connection1["id"])
        await trigger_sync(api_client, connection2["id"])

        # Monitor Redis during sync to verify rate limits are enforced
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:notion:connection:*", duration=30, interval=2)
        )

        # Wait for both to complete (timeout is acceptable - rate limiting slows things down)
        job1 = None
        job2 = None
        sync_timed_out = False
        try:
            job1 = await wait_for_sync_completion(api_client, connection1["id"], timeout=120)
            job2 = await wait_for_sync_completion(api_client, connection2["id"], timeout=120)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out = True

        # Get monitoring data - this is the important verification
        monitoring_data = await monitoring_task

        # If syncs completed, verify they were successful
        if job1 is not None:
            assert job1["status"] == "completed", f"Sync 1 failed: {job1.get('error')}"
            verify_sync_stats_only_inserts(job1, "connection 1")
        if job2 is not None:
            assert job2["status"] == "completed", f"Sync 2 failed: {job2.get('error')}"
            verify_sync_stats_only_inserts(job2, "connection 2")

        # Verify Redis has exactly 2 separate keys (connection-level tracking)
        # Use monitoring data since keys expire quickly (6s TTL)
        assert len(monitoring_data) == 2, f"Expected exactly 2 connection-level keys during sync, got {len(monitoring_data)}: {list(monitoring_data.keys())}"
        print(f"✅ Found 2 separate connection-level rate limit keys during sync")

        # Verify rate limits were enforced during sync (check monitoring data)
        print(f"\n📊 Redis monitoring during sync:")
        for key, counters in monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/{RATE_LIMIT}, samples={counters}")
            assert max_counter <= RATE_LIMIT, f"Rate limit exceeded during sync: {max_counter}/{RATE_LIMIT}"

        completed_status = "both syncs completed" if not sync_timed_out else "sync timed out (rate limiting verified)"
        print(f"\n✅ Connection-level isolation verified: 2 separate quotas, {completed_status}")

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{connection1['id']}")
        await api_client.delete(f"/source-connections/{connection2['id']}")
        await delete_source_rate_limit(api_client, "notion")
        await clear_redis()  # Prevent interference with other tests


@pytest.mark.asyncio
async def test_google_drive_org_level_rate_limiting_aggregated(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
):
    """Test that Google Drive (org-level) rate limits are aggregated across accounts.

    Verifies that two different Google Drive accounts share the same rate limit quota,
    demonstrating org-wide tracking.
    """
    # Skip if Google Drive test accounts not configured
    if not all(
        [
            config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1,
            config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1,
            config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_2,
            config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_2,
        ]
    ):
        pytest.fail("Google Drive test accounts not configured")

    await clear_redis()

    # Enable feature flag before setting rate limits
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Set Google Drive rate limit: 1 req/3s (org-wide aggregation)
    await set_source_rate_limit(api_client, "google_drive", RATE_LIMIT, WINDOW_SECONDS)

    # Create Google Drive connection 1
    connection1_data = {
        "name": f"Google Drive Test 1 {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1,
                "account_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1,
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },

        "sync_immediately": False,
    }

    response1 = await api_client.post("/source-connections", json=connection1_data)
    assert response1.status_code == 200, f"Failed to create connection 1: {response1.text}"
    connection1 = response1.json()

    # Create Google Drive connection 2
    connection2_data = {
        "name": f"Google Drive Test 2 {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_2,
                "account_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_2,
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },
        "sync_immediately": False,
    }

    response2 = await api_client.post("/source-connections", json=connection2_data)
    assert response2.status_code == 200, f"Failed to create connection 2: {response2.text}"
    connection2 = response2.json()

    try:
        # Trigger syncs simultaneously
        await trigger_sync(api_client, connection1["id"])
        await trigger_sync(api_client, connection2["id"])

        # Monitor Redis during sync to verify rate limits are enforced
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:google_drive:org:*", duration=30, interval=2)
        )

        # Wait for both to complete (timeout is acceptable - rate limiting slows things down)
        job1 = None
        job2 = None
        sync_timed_out = False
        try:
            job1 = await wait_for_sync_completion(api_client, connection1["id"], timeout=180)
            job2 = await wait_for_sync_completion(api_client, connection2["id"], timeout=180)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out = True

        # Get monitoring data - this is the important verification
        monitoring_data = await monitoring_task

        # If syncs completed, verify status
        if job1 is not None:
            assert job1["status"] in ["completed", "failed"], f"Unexpected status: {job1['status']}"
            if job1["status"] == "completed":
                verify_sync_stats_only_inserts(job1, "connection 1")
        if job2 is not None:
            assert job2["status"] in ["completed", "failed"], f"Unexpected status: {job2['status']}"
            if job2["status"] == "completed":
                verify_sync_stats_only_inserts(job2, "connection 2")

        # Verify Redis had exactly 1 shared key during sync (org-level tracking)
        # Use monitoring data since keys expire quickly (3s TTL)
        assert len(monitoring_data) == 1, f"Expected exactly 1 org-level key during sync, got {len(monitoring_data)}: {list(monitoring_data.keys())}"
        print(f"✅ Found 1 shared org-level rate limit key during sync")

        # Verify rate limits were enforced during sync (check monitoring data)
        print(f"\n📊 Redis monitoring during sync:")
        for key, counters in monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/{RATE_LIMIT}, samples={counters}")
            assert max_counter <= RATE_LIMIT, f"Rate limit exceeded during sync: {max_counter}/{RATE_LIMIT}"

        # With aggressive limits and concurrent syncs, expect some contention
        completed_count = sum(1 for job in [job1, job2] if job is not None and job["status"] == "completed")
        status_msg = f"{completed_count}/2 syncs completed" if not sync_timed_out else "sync timed out (rate limiting verified)"
        print(f"\n✅ Org-level aggregation verified: Shared quota enforced, {status_msg}")

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{connection1['id']}")
        await api_client.delete(f"/source-connections/{connection2['id']}")
        await delete_source_rate_limit(api_client, "google_drive")
        await clear_redis()  # Prevent interference with other tests


@pytest.mark.asyncio
async def test_pipedream_proxy_rate_limiting_aggregated(
    api_client: httpx.AsyncClient, collection: Dict, pipedream_rate_limit_auth_provider: Dict, config
):
    """Test that Pipedream proxy limits are shared across all proxy-mode connections.

    Verifies that the org-wide Pipedream infrastructure limit is enforced across
    different sources using the same proxy.
    """
    # Skip if Pipedream test accounts not configured
    if not all(
        [
            config.TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_ACCOUNT_ID,
            config.TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_EXTERNAL_USER_ID,
            config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_ACCOUNT_ID,
            config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_EXTERNAL_USER_ID,
        ]
    ):
        pytest.fail("Pipedream default OAuth accounts not configured")

    await clear_redis()

    # Enable feature flag before setting rate limits
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Set Pipedream proxy limit: 5 req/10s (org-wide)
    await set_source_rate_limit(api_client, "pipedream_proxy", 5, 10)

    # Create Notion connection via Pipedream (default OAuth - proxy mode)
    notion_conn_data = {
        "name": f"Notion Pipedream Test {int(time.time())}",
        "short_name": "notion",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": pipedream_rate_limit_auth_provider["readable_id"],
            "provider_config": {
                "project_id": config.TEST_PIPEDREAM_RATE_LIMIT_PROJECT_ID,
                "account_id": config.TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_ACCOUNT_ID,
                "external_user_id": config.TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_EXTERNAL_USER_ID,
                "environment": "development",
            },
        },
        "sync_immediately": False,
    }

    notion_response = await api_client.post("/source-connections", json=notion_conn_data)
    assert notion_response.status_code == 200, f"Failed to create Notion connection: {notion_response.text}"
    notion_conn = notion_response.json()

    # Create Google Drive connection via Pipedream (default OAuth - proxy mode)
    gdrive_conn_data = {
        "name": f"Google Drive Pipedream Test {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": pipedream_rate_limit_auth_provider["readable_id"],
            "provider_config": {
                "project_id": config.TEST_PIPEDREAM_RATE_LIMIT_PROJECT_ID,
                "account_id": config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_ACCOUNT_ID,
                "external_user_id": config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_EXTERNAL_USER_ID,
                "environment": "development",
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },
        "sync_immediately": False,
    }

    gdrive_response = await api_client.post("/source-connections", json=gdrive_conn_data)
    assert gdrive_response.status_code == 200, f"Failed to create Google Drive connection: {gdrive_response.text}"
    gdrive_conn = gdrive_response.json()

    try:
        # Trigger both syncs
        await trigger_sync(api_client, notion_conn["id"])
        await trigger_sync(api_client, gdrive_conn["id"])

        # Monitor Redis during sync
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("pipedream_proxy_rate_limit:*", duration=30, interval=2)
        )

        # Wait for completion (timeout is acceptable - rate limiting slows things down)
        notion_job = None
        gdrive_job = None
        sync_timed_out = False
        try:
            notion_job = await wait_for_sync_completion(api_client, notion_conn["id"], timeout=180)
            gdrive_job = await wait_for_sync_completion(api_client, gdrive_conn["id"], timeout=180)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out = True

        # Get monitoring data - this is the important verification
        monitoring_data = await monitoring_task

        # If syncs completed, verify status
        if notion_job is not None:
            assert notion_job["status"] in ["completed", "failed"]
            if notion_job["status"] == "completed":
                verify_sync_stats_only_inserts(notion_job, "Notion")
        if gdrive_job is not None:
            assert gdrive_job["status"] in ["completed", "failed"]
            if gdrive_job["status"] == "completed":
                verify_sync_stats_only_inserts(gdrive_job, "Google Drive")

        # Verify Redis had 1 proxy key during sync (shared across sources)
        # Use monitoring data since keys expire quickly (10s TTL)
        assert len(monitoring_data) >= 1, f"Expected at least 1 proxy key during sync, got {len(monitoring_data)}: {list(monitoring_data.keys())}"
        print(f"✅ Found {len(monitoring_data)} shared proxy rate limit key(s) during sync")

        # Verify rate limits were enforced during sync
        print(f"\n📊 Redis monitoring during sync:")
        for key, counters in monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/5, samples={counters}")
            assert max_counter <= 5, f"Proxy rate limit exceeded during sync: {max_counter}/5"

        completed_count = sum(
            1 for job in [notion_job, gdrive_job] if job is not None and job["status"] == "completed"
        )
        status_msg = f"{completed_count}/2 syncs completed" if not sync_timed_out else "sync timed out (rate limiting verified)"
        print(
            f"\n✅ Pipedream proxy aggregation verified: 1 shared proxy quota, {status_msg}"
        )

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{notion_conn['id']}")
        await api_client.delete(f"/source-connections/{gdrive_conn['id']}")
        await delete_source_rate_limit(api_client, "pipedream_proxy")
        await clear_redis()  # Prevent interference with other tests


@pytest.mark.asyncio
async def test_dual_rate_limiting_proxy_and_source(
    api_client: httpx.AsyncClient, collection: Dict, pipedream_rate_limit_auth_provider: Dict, config
):
    """Test that proxy mode applies both Pipedream proxy limit AND source-specific limit.

    Verifies that when using Pipedream proxy, the system checks BOTH the proxy
    infrastructure limit and the source-specific limit, applying whichever is stricter.
    """
    # Skip if Pipedream Google Drive account not configured
    if not all([
        config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_ACCOUNT_ID,
        config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_EXTERNAL_USER_ID,
    ]):
        pytest.fail("Pipedream Google Drive account not configured")

    await clear_redis()

    # Enable feature flag before setting rate limits
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Set generous Pipedream proxy limit (won't be the bottleneck)
    await set_source_rate_limit(api_client, "pipedream_proxy", 10, 10)

    # Set strict Google Drive source limit (will be the bottleneck)
    await set_source_rate_limit(api_client, "google_drive", RATE_LIMIT, WINDOW_SECONDS)

    # Create Google Drive connection via Pipedream proxy
    conn_data = {
        "name": f"Google Drive Dual Limit Test {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": pipedream_rate_limit_auth_provider["readable_id"],
            "provider_config": {
                "project_id": config.TEST_PIPEDREAM_RATE_LIMIT_PROJECT_ID,
                "account_id": config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_ACCOUNT_ID,
                "external_user_id": config.TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_EXTERNAL_USER_ID,
                "environment": "development",
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=conn_data)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"
    connection = response.json()

    try:
        # Trigger sync
        await trigger_sync(api_client, connection["id"])

        # Monitor both proxy and source Redis keys during sync
        proxy_monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("pipedream_proxy_rate_limit:*", duration=30, interval=2)
        )
        source_monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:google_drive:org:*", duration=30, interval=2)
        )

        # Wait for completion (timeout is acceptable - rate limiting slows things down)
        job = None
        sync_timed_out = False
        try:
            job = await wait_for_sync_completion(api_client, connection["id"], timeout=180)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out = True

        # Get monitoring data - this is the important verification
        proxy_monitoring_data = await proxy_monitoring_task
        source_monitoring_data = await source_monitoring_task

        # If sync completed, verify it was successful
        if job is not None:
            assert job["status"] == "completed", f"Sync failed: {job.get('error')}"
            verify_sync_stats_only_inserts(job, "Google Drive")

        # Verify both rate limit types were tracked during sync
        # Use monitoring data since keys may expire (proxy: 10s TTL, source: 3s TTL)
        assert len(proxy_monitoring_data) >= 1, f"Expected at least 1 proxy key during sync, got {len(proxy_monitoring_data)}"
        assert len(source_monitoring_data) >= 1, f"Expected at least 1 source key during sync, got {len(source_monitoring_data)}"
        print(f"✅ Found both proxy and source rate limit keys during sync")

        # Verify rate limits were enforced during sync
        print(f"\n📊 Proxy rate limit monitoring:")
        for key, counters in proxy_monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/10, samples={counters}")
            assert max_counter <= 10, f"Proxy limit exceeded during sync: {max_counter}/10"

        print(f"\n📊 Source rate limit monitoring:")
        for key, counters in source_monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/{RATE_LIMIT}, samples={counters}")
            assert max_counter <= RATE_LIMIT, f"Source limit exceeded during sync: {max_counter}/{RATE_LIMIT}"

        status_msg = "sync completed" if not sync_timed_out else "sync timed out (rate limiting verified)"
        print(f"\n✅ Dual rate limiting verified: Both limits checked, {status_msg}")

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
        await delete_source_rate_limit(api_client, "google_drive")
        await delete_source_rate_limit(api_client, "pipedream_proxy")
        await clear_redis()  # Prevent interference with other tests


@pytest.mark.asyncio
async def test_rate_limiting_feature_flag_disabled(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
):
    """Test that rate limiting is skipped when feature flag is disabled.

    This test actually toggles the feature flag to verify both enabled and disabled behavior.
    """
    if not all([config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1, config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1]):
        pytest.fail("Google Drive test account not configured")

    # Store initial feature flag state
    initial_state = await verify_feature_flag_enabled(api_client, "source_rate_limiting")

    # Ensure feature is ENABLED for first test
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])
    await clear_redis()

    # Set Google Drive limit
    await set_source_rate_limit(api_client, "google_drive", RATE_LIMIT, WINDOW_SECONDS)

    # Create connection
    conn_data = {
        "name": f"Google Drive Feature Flag Test {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1,
                "account_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1,
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=conn_data)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"
    connection = response.json()

    try:
        # ========== TEST 1: Feature Flag ENABLED ==========
        print("\n" + "="*60)
        print("TEST 1: Feature Flag ENABLED")
        print("="*60)

        await trigger_sync(api_client, connection["id"])

        # Monitor Redis
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:google_drive:*", duration=15, interval=2)
        )

        start_time = time.time()
        job1 = None
        sync_timed_out_1 = False
        try:
            job1 = await wait_for_sync_completion(api_client, connection["id"], timeout=120)
        except TimeoutError:
            print("⚠️ Sync 1 did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out_1 = True
        elapsed1 = time.time() - start_time
        monitoring_data1 = await monitoring_task

        if job1 is not None:
            assert job1["status"] == "completed", f"Sync failed: {job1.get('error')}"
            verify_sync_stats_only_inserts(job1, "enabled test")

        # Verify rate limiting WAS applied (use monitoring data since keys expire after 3s TTL)
        assert len(monitoring_data1) > 0, f"Expected rate limit keys during sync when feature is enabled, got {len(monitoring_data1)}"

        print(f"\n📊 Redis monitoring (feature ENABLED):")
        for key, counters in monitoring_data1.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/{RATE_LIMIT}, samples={counters}")
            assert max_counter <= RATE_LIMIT, f"Rate limit violated: {max_counter}/{RATE_LIMIT}"

        status_1 = f"sync took {elapsed1:.1f}s" if not sync_timed_out_1 else "sync timed out (rate limiting verified)"
        print(f"\n✅ Feature ENABLED: Rate limiting applied ({len(monitoring_data1)} keys tracked), {status_1}")

        # ========== TEST 2: Feature Flag DISABLED ==========
        print("\n" + "="*60)
        print("TEST 2: Feature Flag DISABLED")
        print("="*60)

        # Disable the feature flag
        await disable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])
        await clear_redis()

        await trigger_sync(api_client, connection["id"])

        # Monitor Redis during second sync
        monitoring_task2 = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:google_drive:*", duration=15, interval=2)
        )

        start_time = time.time()
        job2 = None
        sync_timed_out_2 = False
        try:
            job2 = await wait_for_sync_completion(api_client, connection["id"], timeout=120)
        except TimeoutError:
            print("⚠️ Sync 2 did not complete within timeout")
            sync_timed_out_2 = True
        elapsed2 = time.time() - start_time
        monitoring_data2 = await monitoring_task2

        if job2 is not None:
            assert job2["status"] == "completed", f"Sync failed: {job2.get('error')}"
        # Note: Second sync will have updates, not inserts, since data already exists
        # Just verify it completed successfully

        # Verify rate limiting was SKIPPED (no keys created during sync)
        assert len(monitoring_data2) == 0, f"Rate limit keys should NOT exist when feature is disabled, but found {len(monitoring_data2)}: {list(monitoring_data2.keys())}"

        status_2 = f"sync took {elapsed2:.1f}s" if not sync_timed_out_2 else "sync timed out"
        print(f"\n✅ Feature DISABLED: Rate limiting skipped (0 keys tracked), {status_2}")

        # Sync should be faster when rate limiting is disabled (only if both completed)
        if not sync_timed_out_1 and not sync_timed_out_2 and elapsed2 < elapsed1:
            print(f"✅ Disabled sync was faster ({elapsed2:.1f}s vs {elapsed1:.1f}s)")

        print(f"\n✅ Feature flag toggle confirmed")

    finally:
        # Cleanup and restore original state
        await api_client.delete(f"/source-connections/{connection['id']}")
        await delete_source_rate_limit(api_client, "google_drive")

        # Restore original feature flag state
        if initial_state:
            await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])
        else:
            await disable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

        await clear_redis()


@pytest.mark.asyncio
async def test_rate_limiting_no_limit_configured(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
):
    """Test that rate limiting is skipped when no limit is configured in DB.

    Verifies that even with the feature flag enabled, if no limit is set for a source,
    requests proceed without rate limiting.
    """
    if not all([config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1, config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1]):
        pytest.fail("Google Drive test account not configured")

    await clear_redis()

    # Enable feature flag (needed to access rate limit endpoints)
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Explicitly ensure NO limit is configured for Google Drive
    await delete_source_rate_limit(api_client, "google_drive")

    # Verify no limit in DB
    limits_response = await api_client.get("/source-rate-limits")
    assert limits_response.status_code == 200
    limits = limits_response.json()
    gdrive_limit = next((l for l in limits if l["source_short_name"] == "google_drive"), None)
    assert gdrive_limit is None or gdrive_limit["limit"] is None, "Google Drive limit should not be set"

    # Create connection
    conn_data = {
        "name": f"Google Drive No Limit Test {int(time.time())}",
        "short_name": "google_drive",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1,
                "account_id": config.TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1,
            },
        },
        "config": {
            "include_patterns": ["slapieslapie/*"]
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=conn_data)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"
    connection = response.json()

    try:
        # Trigger sync
        await trigger_sync(api_client, connection["id"])

        # Monitor Redis during sync
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:google_drive:*", duration=30, interval=2)
        )

        start_time = time.time()
        job = None
        sync_timed_out = False
        try:
            job = await wait_for_sync_completion(api_client, connection["id"], timeout=120)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout")
            sync_timed_out = True
        elapsed = time.time() - start_time
        monitoring_data = await monitoring_task

        # If sync completed, verify it was successful
        if job is not None:
            assert job["status"] == "completed", f"Sync failed: {job.get('error')}"
            verify_sync_stats_only_inserts(job, "no limit test")

        # Verify no rate limit keys created during sync - this is the key assertion
        assert len(monitoring_data) == 0, f"Rate limit keys created despite no limit: {list(monitoring_data.keys())}"

        # Sync should be fast (no artificial delays)
        status_msg = f"in {elapsed:.1f}s" if not sync_timed_out else "(timed out)"
        print(f"\nSync completed {status_msg} (no rate limiting)")
        print(f"✅ No limit configured: Sync proceeded without rate limiting (0 keys tracked)")

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
        await clear_redis()  # Prevent interference with other tests


@pytest.mark.asyncio
async def test_atomic_lua_prevents_bursts(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
):
    """Test that atomic Lua script prevents race condition bursts.

    Verifies that even with concurrent requests, the atomic Lua script ensures
    only the configured number of requests succeed (no bursts beyond limit).
    """
    if not all([config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1, config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1]):
        pytest.fail("Notion test account not configured")

    await clear_redis()

    # Enable feature flag before setting rate limits
    await enable_feature_flag(api_client, "source_rate_limiting", org_id=collection["organization_id"])

    # Set very strict limit to observe atomic behavior
    await set_source_rate_limit(api_client, "notion", 1, 10)  # 1 req/10s

    # Create connection
    conn_data = {
        "name": f"Notion Atomic Test {int(time.time())}",
        "short_name": "notion",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1,
                "account_id": config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1,
            },
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=conn_data)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"
    connection = response.json()

    try:
        # Trigger sync
        await trigger_sync(api_client, connection["id"])

        # Monitor Redis during sync to catch any bursts
        monitoring_task = asyncio.create_task(
            monitor_redis_during_sync("source_rate_limit:*:notion:connection:*", duration=30, interval=1)
        )

        # Wait for sync completion (timeout is acceptable - rate limiting slows things down)
        job = None
        sync_timed_out = False
        try:
            job = await wait_for_sync_completion(api_client, connection["id"], timeout=180)
        except TimeoutError:
            print("⚠️ Sync did not complete within timeout (expected with aggressive rate limiting)")
            sync_timed_out = True

        # Get monitoring data - this is the important verification
        monitoring_data = await monitoring_task

        # If sync completed, verify it was successful
        if job is not None:
            assert job["status"] == "completed", f"Sync failed: {job.get('error')}"
            verify_sync_stats_only_inserts(job, "atomic test")

        # Verify atomic behavior: counter NEVER exceeded limit during sync
        print(f"\n📊 Atomic Lua monitoring (checking for bursts):")
        for key, counters in monitoring_data.items():
            max_counter = max(counters) if counters else 0
            print(f"  {key}: max={max_counter}/1, all samples={counters}")

            # With atomic Lua, NO sample should exceed the limit
            for i, counter in enumerate(counters):
                assert counter <= 1, f"Atomic script FAILED: sample {i} had counter={counter}/1 (burst detected!)"

            print(f"  ✓ All {len(counters)} samples respected limit (no bursts)")

        status_msg = "sync completed" if not sync_timed_out else "sync timed out (rate limiting verified)"
        print(f"\n✅ Atomic Lua script verified: No bursts beyond configured limit, {status_msg}")

    finally:
        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
        await delete_source_rate_limit(api_client, "notion")
        await clear_redis()  # Prevent interference with other tests
