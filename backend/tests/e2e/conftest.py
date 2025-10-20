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
    """Create Composio auth provider connection for testing."""
    if not config.TEST_COMPOSIO_API_KEY:
        pytest.fail("Composio API key not configured")

    provider_readable_id = f"composio-test"
    auth_provider_payload = {
        "name": "Test Composio Provider",
        "short_name": "composio",
        "readable_id": provider_readable_id,
        "auth_fields": {"api_key": config.TEST_COMPOSIO_API_KEY},
    }

    # Check if connection already exists
    response = await module_api_client.get(f"/auth-providers/connections/{provider_readable_id}")

    if response.status_code == 200:
        # Connection already exists, use it
        provider = response.json()
        yield provider
    else:
        # Create new connection
        response = await module_api_client.post("/auth-providers/", json=auth_provider_payload)

        if response.status_code != 200:
            pytest.fail(f"Failed to create Composio auth provider: {response.text}")

        provider = response.json()
        yield provider


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
        print(f"Warning: Initial sync may not have completed after {max_wait_time} seconds")

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
async def pipedream_auth_provider(api_client: httpx.AsyncClient) -> Dict:
    """Create a Pipedream auth provider for testing."""
    import os

    # Check for Pipedream environment variables
    pipedream_client_id = os.environ.get("TEST_PIPEDREAM_CLIENT_ID")
    pipedream_client_secret = os.environ.get("TEST_PIPEDREAM_CLIENT_SECRET")

    if not all([pipedream_client_id, pipedream_client_secret]):
        pytest.fail("Pipedream credentials not configured")

    provider_id = f"pipedream-test-{uuid.uuid4().hex[:8]}"
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


def pytest_collection_modifyitems(config, items):
    """Reorder tests to ensure rate_limit tests run last.

    This prevents rate limiting tests from interfering with other tests
    by consuming the rate limit quota.
    """
    # Separate rate_limit tests from others
    rate_limit_tests = []
    other_tests = []

    for item in items:
        if item.get_closest_marker("rate_limit"):
            rate_limit_tests.append(item)
        else:
            other_tests.append(item)

    # Reorder: run all other tests first, then rate_limit tests
    items[:] = other_tests + rate_limit_tests

    if rate_limit_tests:
        print(f"\n📊 Test order modified: {len(rate_limit_tests)} rate_limit tests will run last")
