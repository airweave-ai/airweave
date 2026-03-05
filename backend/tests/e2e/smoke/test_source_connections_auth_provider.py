"""
Async test module for Auth Provider source connections.

Tests authentication via external auth providers like Composio and Pipedream.
"""

import pytest
import httpx
import time
import asyncio
from typing import Dict


SLEEP_TIME = 30


class TestAuthProviderAuthentication:
    """Test suite for auth provider source connections."""

    @pytest.mark.asyncio
    async def test_auth_provider_public_metadata_endpoints(self, api_client: httpx.AsyncClient):
        """Smoke-check /auth-providers/list and /auth-providers/detail/{short_name}."""
        list_response = await api_client.get("/auth-providers/list")
        list_response.raise_for_status()
        providers = list_response.json()

        if not providers:
            pytest.skip("No auth providers available in this environment")

        provider_short_name = providers[0]["short_name"]
        detail_response = await api_client.get(f"/auth-providers/detail/{provider_short_name}")
        detail_response.raise_for_status()
        detail = detail_response.json()
        assert detail["short_name"] == provider_short_name

    async def _wait_for_job_status(
        self,
        api_client: httpx.AsyncClient,
        connection_id: str,
        *,
        allowed_statuses: set[str] | None = None,
        timeout_seconds: int = SLEEP_TIME,
        interval_seconds: int = 3,
    ) -> Dict:
        """Poll the source connection until last_job.status is in allowed_statuses or timeout.

        Fails fast if the job status becomes 'failed'. Returns the latest connection payload.
        """
        if allowed_statuses is None:
            allowed_statuses = {"running", "completed"}

        end_time = time.time() + timeout_seconds
        last_payload: Dict | None = None

        while time.time() < end_time:
            resp = await api_client.get(f"/source-connections/{connection_id}")
            resp.raise_for_status()
            payload = resp.json()
            last_payload = payload

            sync = payload.get("sync") or {}
            last_job = sync.get("last_job") or {}
            status = (last_job.get("status") or "").lower()

            # If there is a status and it's failed, fail immediately
            if status == "failed":
                assert False, f"Sync job failed: {last_job}"

            # If status is one of the allowed ones, we're done
            if status in allowed_statuses:
                return payload

            await asyncio.sleep(interval_seconds)

        # Timed out: return last seen payload (may still be pending/created)
        return last_payload or {}

    @pytest.mark.asyncio
    async def test_composio_auth_provider(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        composio_auth_provider: Dict,
        config,
    ):
        """Test Composio auth provider for Asana."""

        # Create source connection using the auth provider fixture
        connection_payload = {
            "name": "Test Asana via Composio",
            "short_name": "asana",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing auth provider authentication with Asana",
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_ASANA_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_ASANA_ACCOUNT_ID,
                },
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        response.raise_for_status()
        connection = response.json()
        assert connection["id"]
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        assert connection["status"] == "active"
        assert connection["sync"] == None

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_composio_auth_provider_sync_immediately(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        composio_auth_provider: Dict,
        config,
    ):
        """Test Composio auth provider for Todoist."""

        # Create source connection using the auth provider fixture
        connection_payload = {
            "name": "Test Todoist via Composio",
            "short_name": "todoist",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing auth provider authentication with Todoist",
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_TODOIST_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_TODOIST_ACCOUNT_ID,
                },
            },
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        response.raise_for_status()
        connection = response.json()
        assert connection["id"]
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        assert connection["status"] == "active"
        # Initial state can be pending/created/running depending on timing
        assert connection["sync"]["last_job"]["status"].lower() in {
            "pending",
            "created",
            "running",
            "completed",
        }

        # Wait until the job is running or completed (or until timeout), and ensure it didn't fail
        updated_connection = await self._wait_for_job_status(
            api_client, connection["id"], allowed_statuses={"running", "completed"}
        )

        # Status may be 'syncing' while running, or 'active' if it already completed
        assert updated_connection["status"] in {"active", "syncing"}
        assert updated_connection["auth"]["method"] == "auth_provider"
        assert updated_connection["auth"]["authenticated"] == True
        assert updated_connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        # Ensure job is either still running or completed, but not failed
        assert updated_connection["sync"]["last_job"]["status"].lower() in {"running", "completed"}

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_pipedream_proxy_auth_provider(
        self, api_client: httpx.AsyncClient, collection: Dict, pipedream_auth_provider: Dict, config
    ):
        """Test Pipedream proxy auth provider for Google Drive."""
        import os

        pipedream_project_id = config.TEST_PIPEDREAM_PROJECT_ID
        pipedream_account_id = config.TEST_PIPEDREAM_ACCOUNT_ID
        pipedream_external_user_id = config.TEST_PIPEDREAM_EXTERNAL_USER_ID

        if not all(
            [
                pipedream_project_id,
                pipedream_account_id,
                pipedream_external_user_id,
            ]
        ):
            raise ValueError("Pipedream project config not set")

        # Create Google Drive connection via Pipedream
        connection_payload = {
            "name": "Test Google Drive via Pipedream",
            "short_name": "google_drive",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing Google Drive with Pipedream proxy authentication",
            "authentication": {
                "provider_readable_id": pipedream_auth_provider["readable_id"],
                "provider_config": {
                    "project_id": pipedream_project_id,
                    "account_id": pipedream_account_id,
                    "external_user_id": pipedream_external_user_id,
                    "environment": "development",
                },
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        assert (
            response.status_code == 200
        ), f"Failed to create Google Drive connection: {response.text}"
        connection = response.json()

        # Verify connection
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == pipedream_auth_provider["readable_id"]
        assert connection["status"] == "active"

        # Test sync
        response = await api_client.post(f"/source-connections/{connection['id']}/run")

        job = response.json()

        # Wait until the job is running or completed (or until timeout), and ensure it didn't fail
        updated_connection = await self._wait_for_job_status(
            api_client, connection["id"], allowed_statuses={"running", "completed"}
        )

        # Depending on timing, status can be 'syncing' (running) or 'active' (already completed)
        assert updated_connection["status"] in {"syncing", "active"}
        assert updated_connection["auth"]["method"] == "auth_provider"
        assert updated_connection["auth"]["authenticated"] == True
        assert updated_connection["auth"]["provider_id"] == pipedream_auth_provider["readable_id"]
        # Ensure job is either still running or completed, but not failed
        assert updated_connection["sync"]["last_job"]["status"].lower() in {"running", "completed"}

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_invalid_auth_provider(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test using non-existent auth provider."""
        connection_payload = {
            "name": "Test Invalid Provider",
            "short_name": "asana",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"provider_readable_id": "non-existent-provider-xyz"},
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        assert response.status_code == 404
        error = response.json()
        assert "not found" in error.get("detail", "").lower()
