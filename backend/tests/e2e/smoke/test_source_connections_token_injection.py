"""
Test module for OAuth token injection (direct token injection) source connections.

Tests the OAuthTokenAuthentication flow where users provide access tokens directly
without going through the OAuth browser flow.
"""

import pytest
import pytest_asyncio
import httpx
import asyncio
from typing import Dict


async def fetch_fresh_token_from_composio(
    api_key: str,
    auth_config_id: str,
    account_id: str,
    source_slug: str = "notion",
) -> str:
    """Fetch a fresh access token directly from Composio API."""
    async with httpx.AsyncClient() as client:
        headers = {"x-api-key": api_key}

        page = 1
        while True:
            response = await client.get(
                "https://backend.composio.dev/api/v3/connected_accounts",
                headers=headers,
                params={"limit": 100, "page": page},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for account in items:
                toolkit_slug = account.get("toolkit", {}).get("slug")
                acc_auth_config_id = account.get("auth_config", {}).get("id")
                acc_id = account.get("id")

                if (toolkit_slug == source_slug and
                    acc_auth_config_id == auth_config_id and
                    acc_id == account_id):
                    creds = account.get("state", {}).get("val", {})
                    token = creds.get("access_token")
                    if token:
                        return token

            if len(items) < 100:
                break
            page += 1

    raise ValueError(f"Could not find access_token for {source_slug}")


@pytest_asyncio.fixture
async def fresh_notion_token(config) -> str:
    """Fetch a fresh Notion access token from Composio. Fails if not configured."""
    if not config.TEST_COMPOSIO_API_KEY:
        pytest.fail("TEST_COMPOSIO_API_KEY not configured")
    if not config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1:
        pytest.fail("TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1 not configured")
    if not config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1:
        pytest.fail("TEST_COMPOSIO_NOTION_ACCOUNT_ID_1 not configured")

    return await fetch_fresh_token_from_composio(
        api_key=config.TEST_COMPOSIO_API_KEY,
        auth_config_id=config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1,
        account_id=config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1,
        source_slug="notion",
    )


class TestDirectTokenInjectionValidation:
    """Test suite for token injection API validation (no valid tokens needed)."""

    @pytest.mark.asyncio
    async def test_token_injection_invalid_token_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that invalid tokens are rejected during connection creation."""
        payload = {
            "name": "Test Invalid Token",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": "invalid_token_12345",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "invalid" in detail or "token" in detail

    @pytest.mark.asyncio
    async def test_token_injection_empty_token_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that empty access_token is rejected."""
        payload = {
            "name": "Test Empty Token",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": "",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_token_injection_unsupported_source_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that token injection on non-OAuth sources is rejected."""
        payload = {
            "name": "Test Token on Non-OAuth Source",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": "some_access_token",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "not support" in detail or "unsupported" in detail

    @pytest.mark.asyncio
    async def test_token_injection_whitespace_token_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that whitespace-only access_token is rejected."""
        payload = {
            "name": "Test Whitespace Token",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": "   ",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code in [400, 422]


class TestDirectTokenInjectionWithValidToken:
    """Test suite for token injection with valid tokens."""

    @pytest.mark.asyncio
    async def test_token_injection_creates_authenticated_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test that token injection creates an immediately authenticated connection."""
        payload = {
            "name": "Test Token Injection",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        assert connection["auth"]["method"] == "oauth_token"
        assert connection["auth"]["authenticated"] is True
        assert connection["status"] in ["active", "syncing"]
        assert connection["auth"]["auth_url"] is None

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_token_injection_defaults_sync_immediately_true(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test that token injection defaults to sync_immediately=True."""
        payload = {
            "name": "Test Token Injection Default Sync",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        assert connection["auth"]["method"] == "oauth_token"
        assert connection["status"] in ["active", "syncing"]

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_token_injection_with_optional_refresh_token(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test token injection with both access_token and refresh_token."""
        payload = {
            "name": "Test Token Injection With Refresh",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
                "refresh_token": "optional_refresh_token_for_test",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        assert connection["auth"]["method"] == "oauth_token"
        assert connection["auth"]["authenticated"] is True

        await api_client.delete(f"/source-connections/{connection['id']}")


class TestTokenInjectionSync:
    """Test sync behavior for token-injected connections."""

    @pytest.mark.asyncio
    async def test_token_injection_sync_completes_without_refresh(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test that sync completes successfully without token refresh."""
        payload = {
            "name": "Test Token Sync No Refresh",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        max_wait = 60
        poll_interval = 2
        elapsed = 0
        sync_completed = False
        final_status = None

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_response = await api_client.get(f"/source-connections/{connection_id}")
            if status_response.status_code == 200:
                conn_details = status_response.json()
                final_status = conn_details.get("status")

                if final_status in ["active", "error"]:
                    sync_completed = True
                    break

                sync_info = conn_details.get("sync")
                if sync_info and sync_info.get("last_job"):
                    job_status = sync_info["last_job"].get("status")
                    if job_status in ["completed", "failed"]:
                        sync_completed = True
                        final_status = "active" if job_status == "completed" else "error"
                        break

        assert sync_completed, f"Sync did not complete within {max_wait} seconds"
        assert final_status == "active", f"Expected 'active' status, got '{final_status}'"

        await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_token_injection_manual_sync_trigger(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test manually triggering a sync on a token-injected connection."""
        payload = {
            "name": "Test Token Manual Sync",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        assert connection["sync"] is None or connection["sync"]["total_runs"] == 0

        run_response = await api_client.post(f"/source-connections/{connection_id}/run")
        assert run_response.status_code == 200
        sync_job = run_response.json()
        assert sync_job["status"] in ["pending", "running"]

        max_wait = 60
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_response = await api_client.get(f"/source-connections/{connection_id}")
            if status_response.status_code == 200:
                conn_details = status_response.json()
                sync_info = conn_details.get("sync")
                if sync_info and sync_info.get("last_job"):
                    job_status = sync_info["last_job"].get("status")
                    if job_status in ["completed", "failed"]:
                        assert job_status == "completed", \
                            f"Sync failed: {sync_info['last_job'].get('error')}"
                        break

        await api_client.delete(f"/source-connections/{connection_id}")


class TestTokenInjectionEdgeCases:
    """Edge case tests for token injection."""

    @pytest.mark.asyncio
    async def test_token_injection_with_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test token injection with a sync schedule."""
        payload = {
            "name": "Test Token With Schedule",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "schedule": {
                "cron": "0 * * * *",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        assert connection["auth"]["method"] == "oauth_token"
        assert connection["schedule"]["cron"] == "0 * * * *"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_token_injection_connection_get_details(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test retrieving details of a token-injected connection."""
        payload = {
            "name": "Test Token Get Details",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        get_response = await api_client.get(f"/source-connections/{connection_id}")
        get_response.raise_for_status()
        details = get_response.json()

        assert details["auth"]["method"] == "oauth_token"
        assert details["auth"]["authenticated"] is True
        assert "access_token" not in str(details["auth"])

        await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_token_injection_list_connections(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test that token-injected connections appear in list endpoints."""
        payload = {
            "name": "Test Token List",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        list_response = await api_client.get("/source-connections")
        list_response.raise_for_status()
        connections = list_response.json()

        found = False
        for conn in connections:
            if conn["id"] == connection_id:
                found = True
                assert conn["auth_method"] == "oauth_token"
                assert conn["is_authenticated"] is True
                break

        assert found, f"Connection {connection_id} not found in list"

        await api_client.delete(f"/source-connections/{connection_id}")
