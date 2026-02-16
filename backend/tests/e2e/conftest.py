"""
Shared pytest fixtures for E2E tests.

Provides async HTTP client and test configuration.
"""

import pytest
import pytest_asyncio
import uuid
import time
import asyncio
from typing import AsyncGenerator, Dict, Optional
import httpx
from config import settings


# pytest-asyncio is now configured in root conftest.py


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio as the async backend."""
    return "asyncio"


@pytest.fixture(scope="session")
def config():
    """Get test configuration."""
    return settings


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API requests."""
    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(settings.default_timeout),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def collection(api_client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
    """Create a test collection that's cleaned up after use."""
    # Create collection
    collection_data = {"name": f"Test Collection {int(time.time())}"}
    response = await api_client.post("/collections/", json=collection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create test collection: {response.text}")

    collection = response.json()

    # Yield for test to useclear

    yield collection

    # Cleanup
    try:
        await api_client.delete(f"/collections/{collection['readable_id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def module_api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API requests."""
    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(settings.default_timeout),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def module_collection(module_api_client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
    """Create a test collection that's shared across the entire module."""
    # Create collection
    collection_data = {"name": f"Module Test Collection {int(time.time())}"}
    response = await module_api_client.post("/collections/", json=collection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create module test collection: {response.text}")

    collection = response.json()

    # Yield for tests to use
    yield collection

    # Cleanup
    try:
        await module_api_client.delete(f"/collections/{collection['readable_id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def composio_auth_provider(
    module_api_client: httpx.AsyncClient, config
) -> AsyncGenerator[Dict, None]:
    """Create Composio auth provider connection for testing.

    Uses get-or-create with retry to handle race conditions when multiple
    pytest-xdist workers try to create the same provider simultaneously.
    """
    if not config.TEST_COMPOSIO_API_KEY:
        pytest.fail("Composio API key not configured")

    provider_readable_id = f"composio-test"
    auth_provider_payload = {
        "name": "Test Composio Provider",
        "short_name": "composio",
        "readable_id": provider_readable_id,
        "auth_fields": {"api_key": config.TEST_COMPOSIO_API_KEY},
    }

    # Get-or-create with retry to handle parallel worker race conditions.
    # Two workers can both GET 404 then both POST, causing a duplicate key error.
    # On conflict, retry the GET since the other worker already created it.
    for attempt in range(3):
        # Check if connection already exists
        response = await module_api_client.get(
            f"/auth-providers/connections/{provider_readable_id}"
        )

        if response.status_code == 200:
            # Connection already exists, use it
            yield response.json()
            return

        # Try to create it
        response = await module_api_client.post("/auth-providers/", json=auth_provider_payload)

        if response.status_code == 200:
            yield response.json()
            return

        # If creation failed due to duplicate key (race condition), retry GET
        if "UniqueViolation" in response.text or "duplicate key" in response.text:
            await asyncio.sleep(0.5 * (attempt + 1))
            continue

        # Some other error — fail immediately
        pytest.fail(f"Failed to create Composio auth provider: {response.text}")

    # Final fallback: one last GET after all retries
    response = await module_api_client.get(
        f"/auth-providers/connections/{provider_readable_id}"
    )
    if response.status_code == 200:
        yield response.json()
        return

    pytest.fail(
        f"Failed to get or create Composio auth provider after retries. "
        f"Last response: {response.status_code} {response.text}"
    )


@pytest_asyncio.fixture(scope="function")
async def source_connection_fast(
    api_client: httpx.AsyncClient,
    collection: Dict,
    composio_auth_provider: Dict,
    config,
) -> AsyncGenerator[Dict, None]:
    """Create a fast Todoist source connection via Composio.

    Ideally this should take less than 30 seconds to sync.
    """
    connection_data = {
        "name": f"Todoist Fast Connection {uuid.uuid4().hex[:8]}",
        "short_name": "todoist",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_TODOIST_AUTH_CONFIG_ID,
                "account_id": config.TEST_COMPOSIO_TODOIST_ACCOUNT_ID,
            },
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Todoist connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def source_connection_medium(
    api_client: httpx.AsyncClient,
    collection: Dict,
    composio_auth_provider: Dict,
    config,
) -> AsyncGenerator[Dict, None]:
    """Create a medium-speed Asana source connection via Composio.

    Ideally this should take between 1 and 3 minutes to sync.
    """
    connection_data = {
        "name": f"Asana Medium Connection {int(time.time())}",
        "short_name": "asana",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_ASANA_AUTH_CONFIG_ID,
                "account_id": config.TEST_COMPOSIO_ASANA_ACCOUNT_ID,
            },
        },
        "sync_immediately": False,  # Control sync timing in tests
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Asana connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture(scope="function")
async def timed_source_connection_fast(
    api_client: httpx.AsyncClient,
    collection: Dict,
) -> AsyncGenerator[Dict, None]:
    """Create a fast TimedSource connection for testing.

    Generates 20 entities over 2 seconds. Use for tests that need a
    sync to complete quickly (e.g., testing post-completion state).
    No external service dependencies.
    """
    connection_data = {
        "name": f"Timed Fast {uuid.uuid4().hex[:8]}",
        "short_name": "timed",
        "readable_collection_id": collection["readable_id"],
        "authentication": {"credentials": {"timed_key": "test"}},
        "config": {"entity_count": 20, "duration_seconds": 2, "seed": 42},
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create timed fast connection: {response.text}")

    connection = response.json()

    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except Exception:
        pass  # Best effort cleanup


@pytest_asyncio.fixture(scope="function")
async def timed_source_connection_medium(
    api_client: httpx.AsyncClient,
    collection: Dict,
) -> AsyncGenerator[Dict, None]:
    """Create a medium-speed TimedSource connection for testing.

    Generates 100 entities over 30 seconds. Use for tests that need
    a sync to stay running long enough to cancel mid-flight.
    No external service dependencies.
    """
    connection_data = {
        "name": f"Timed Medium {uuid.uuid4().hex[:8]}",
        "short_name": "timed",
        "readable_collection_id": collection["readable_id"],
        "authentication": {"credentials": {"timed_key": "test"}},
        "config": {"entity_count": 100, "duration_seconds": 30, "seed": 42},
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create timed medium connection: {response.text}")

    connection = response.json()

    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except Exception:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def module_source_connection_stripe(
    module_api_client: httpx.AsyncClient, module_collection: Dict, config
) -> AsyncGenerator[Dict, None]:
    """Create a Stripe source connection that's shared across the entire module.

    This fixture is module-scoped to avoid recreating the connection for each test.
    Performs initial sync and waits for completion to ensure data is available.
    """
    connection_data = {
        "name": f"Module Stripe Connection {int(time.time())}",
        "short_name": "stripe",
        "readable_collection_id": module_collection["readable_id"],
        "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
        "sync_immediately": True,  # Sync immediately on creation
    }

    response = await module_api_client.post("/source-connections", json=connection_data)

    if response.status_code == 400 and "invalid" in response.text.lower():
        # Skip if using dummy/invalid credentials
        pytest.fail(f"Skipping due to invalid Stripe credentials: {response.text}")

    if response.status_code != 200:
        pytest.fail(f"Failed to create module Stripe connection: {response.text}")

    connection = response.json()

    # Wait for initial sync to complete by checking sync job status
    max_wait_time = 180  # 3 minutes
    poll_interval = 2
    elapsed = 0
    sync_completed = False

    while elapsed < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        # Get detailed connection info to check sync status
        status_response = await module_api_client.get(f"/source-connections/{connection['id']}")
        if status_response.status_code == 200:
            conn_details = status_response.json()

            # Check the status field - based on SourceConnection schema
            if conn_details.get("status") in ["active", "error"]:
                # Sync has completed (either successfully or with error)
                sync_completed = True
                break

            # Also check if we have sync details with last_job
            sync_info = conn_details.get("sync")
            if sync_info and sync_info.get("last_job"):
                last_job = sync_info["last_job"]
                job_status = last_job.get("status")
                if job_status in ["completed", "failed", "cancelled"]:
                    sync_completed = True
                    break

    if not sync_completed:
        pytest.fail(f"Stripe sync did not complete within {max_wait_time} seconds")

    # Verify data is actually searchable (sync complete != indexed)
    readable_id = module_collection["readable_id"]
    data_verified = False
    for attempt in range(12):
        wait_secs = 3 if attempt < 5 else 5
        await asyncio.sleep(wait_secs)
        verify_resp = await module_api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "customer OR invoice OR payment",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
                "limit": 5,
            },
            timeout=60,
        )
        if verify_resp.status_code == 200:
            verify_data = verify_resp.json()
            if verify_data.get("results") and len(verify_data["results"]) > 0:
                data_verified = True
                print(
                    f"✓ Stripe data searchable: {len(verify_data['results'])} results "
                    f"(attempt {attempt + 1})"
                )
                break
        print(f"  [stripe verify] attempt {attempt + 1}: no results yet, retrying...")

    if not data_verified:
        pytest.fail("Stripe sync completed but data not searchable after retries")

    # Yield for tests to use
    yield connection

    # Cleanup
    try:
        await module_api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def source_connection_continuous_slow(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
) -> AsyncGenerator[Dict, None]:
    """Create a slow Gmail source connection via Composio.

    This should take at least 5 minutes to sync.

    Uses cursor fields and is the slowest sync option.
    """
    # Skip if Gmail config not available
    if not config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID or not config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID:
        pytest.fail("Gmail Composio configuration not available")

    connection_data = {
        "name": f"Gmail Slow Connection {int(time.time())}",
        "short_name": "gmail",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID,
                "account_id": config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID,
            },
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Gmail connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest.fixture
def unique_name() -> str:
    """Generate a unique name for test resources."""
    return f"test_{int(time.time())}_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def pipedream_rate_limit_auth_provider(api_client: httpx.AsyncClient) -> Dict:
    """Create a Pipedream auth provider for rate limit testing."""
    import os

    # Use rate limit-specific Pipedream credentials (separate from regular Pipedream tests)
    pipedream_client_id = os.environ.get("TEST_PIPEDREAM_RATE_LIMIT_CLIENT_ID")
    pipedream_client_secret = os.environ.get("TEST_PIPEDREAM_RATE_LIMIT_CLIENT_SECRET")

    if not all([pipedream_client_id, pipedream_client_secret]):
        pytest.fail("Pipedream rate limit test credentials not configured")

    provider_id = f"pipedream-rate-limit-{uuid.uuid4().hex[:8]}"
    auth_provider_payload = {
        "name": "Test Pipedream Provider (Rate Limit)",
        "short_name": "pipedream",
        "readable_id": provider_id,
        "auth_fields": {
            "client_id": pipedream_client_id,
            "client_secret": pipedream_client_secret,
        },
    }

    response = await api_client.post("/auth-providers/", json=auth_provider_payload)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Pipedream auth provider: {response.text}")

    provider = response.json()

    # Yield for test to use
    yield provider

    # Cleanup
    try:
        await api_client.delete(f"/auth-providers/{provider['readable_id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def pipedream_auth_provider(api_client: httpx.AsyncClient, config) -> Dict:
    """Create a Pipedream auth provider for regular auth provider tests."""
    import os

    # Use regular Pipedream credentials (not rate limit specific)
    pipedream_client_id = config.TEST_PIPEDREAM_CLIENT_ID
    pipedream_client_secret = config.TEST_PIPEDREAM_CLIENT_SECRET

    if not all([pipedream_client_id, pipedream_client_secret]):
        pytest.fail("Regular Pipedream test credentials not configured")

    provider_id = f"pipedream-{uuid.uuid4().hex[:8]}"
    auth_provider_payload = {
        "name": "Test Pipedream Provider",
        "short_name": "pipedream",
        "readable_id": provider_id,
        "auth_fields": {
            "client_id": pipedream_client_id,
            "client_secret": pipedream_client_secret,
        },
    }

    response = await api_client.post("/auth-providers/", json=auth_provider_payload)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Pipedream auth provider: {response.text}")

    provider = response.json()

    # Yield for test to use
    yield provider

    # Cleanup
    try:
        await api_client.delete(f"/auth-providers/{provider['readable_id']}")
    except:
        pass  # Best effort cleanup


# ---------------------------------------------------------------------------
# Enable agentic_search feature flag for the test organization
# ---------------------------------------------------------------------------
_agentic_search_flag_enabled = False


async def _enable_agentic_search_feature_flag() -> None:
    """Enable the agentic_search feature flag on the test organization via admin API.

    In dev mode the test user is a superuser, so the admin endpoint succeeds.
    Runs once per session; subsequent calls are no-ops.
    """
    global _agentic_search_flag_enabled
    if _agentic_search_flag_enabled:
        return

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(15),
        follow_redirects=True,
    ) as client:
        # Discover the test organization ID
        orgs_resp = await client.get("/users/me/organizations")
        if orgs_resp.status_code != 200 or not orgs_resp.json():
            print("Warning: could not fetch organizations to enable agentic_search flag")
            return

        org_id = orgs_resp.json()[0]["id"]

        resp = await client.post(
            f"/admin/organizations/{org_id}/feature-flags/agentic_search/enable"
        )
        if resp.status_code == 200:
            _agentic_search_flag_enabled = True
            print(f"✓ agentic_search feature flag enabled for org {org_id}")
        else:
            print(f"Warning: failed to enable agentic_search flag: {resp.status_code} {resp.text}")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_agentic_search_flag():
    """Session-scoped fixture that enables the agentic_search feature flag once."""
    await _enable_agentic_search_feature_flag()


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "requires_sync: tests that require completed sync")
    config.addinivalue_line(
        "markers", "requires_temporal: tests that require Temporal (local only)"
    )
    config.addinivalue_line("markers", "critical: critical path tests that must pass")
    config.addinivalue_line("markers", "requires_openai: tests that require OpenAI API key")
    config.addinivalue_line(
        "markers", "requires_composio: tests that require Composio auth provider"
    )
    config.addinivalue_line(
        "markers", "rate_limit: tests that consume rate limit quota (run last)"
    )
    config.addinivalue_line(
        "markers", "api_rate_limit: tests that consume API rate limit quota (skipped in CI)"
    )
    config.addinivalue_line(
        "markers", "local_only: tests that require local environment (direct storage access)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection: skip tests based on environment, reorder rate_limit tests.

    - Skip local_only tests when TEST_ENV is not "local"
    - Move rate_limit tests to run last
    """
    import os

    test_env = os.environ.get("TEST_ENV", "local")
    skip_local_only = pytest.mark.skip(
        reason="Test requires local environment (TEST_ENV != local)"
    )

    # Separate rate_limit tests from others
    rate_limit_tests = []
    other_tests = []

    for item in items:
        # Skip local_only tests when not in local environment
        if item.get_closest_marker("local_only") and test_env != "local":
            item.add_marker(skip_local_only)

        if item.get_closest_marker("rate_limit"):
            rate_limit_tests.append(item)
        else:
            other_tests.append(item)

    # Reorder: run all other tests first, then rate_limit tests
    items[:] = other_tests + rate_limit_tests

    if rate_limit_tests:
        print(f"\n📊 Test order modified: {len(rate_limit_tests)} rate_limit tests will run last")
