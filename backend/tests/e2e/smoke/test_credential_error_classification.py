"""E2E smoke tests for credential error classification.

Verifies that syncs with bad credentials produce the correct error_category
and that the source connection status becomes needs_reauth.
"""

import asyncio
from typing import Dict

import httpx
import pytest


class TestCredentialErrorClassification:
    """Tests that bad credentials produce correct error classification in the API."""

    async def _wait_for_sync_failure(
        self,
        api_client: httpx.AsyncClient,
        connection_id: str,
        timeout: int = 60,
        poll_interval: int = 2,
    ) -> Dict:
        """Poll until the source connection's latest sync job is failed."""
        elapsed = 0
        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            resp = await api_client.get(f"/source-connections/{connection_id}")
            if resp.status_code != 200:
                continue
            data = resp.json()
            sync_info = data.get("sync")
            if sync_info and sync_info.get("last_job"):
                job = sync_info["last_job"]
                if job.get("status") == "failed":
                    return data
        pytest.fail(f"Sync did not fail within {timeout}s for connection {connection_id}")

    @pytest.mark.asyncio
    async def test_bad_api_key_produces_api_key_invalid(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """A Stripe connection with an invalid API key should classify as api_key_invalid."""
        payload = {
            "name": "Bad Stripe Key Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_INVALID_KEY_00000000"}},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200, f"Failed to create connection: {response.text}"
        connection = response.json()
        connection_id = connection["id"]

        try:
            data = await self._wait_for_sync_failure(api_client, connection_id)

            assert data["status"] == "needs_reauth", (
                f"Expected needs_reauth, got {data['status']}"
            )
            assert data.get("error_category") == "api_key_invalid", (
                f"Expected api_key_invalid, got {data.get('error_category')}"
            )
            assert data.get("error_message"), "Expected error_message to be set"
        finally:
            await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_no_error_category_on_successful_sync(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """A connection with valid credentials should not have error_category set."""
        payload = {
            "name": "Good Stripe Key Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200, f"Failed to create connection: {response.text}"
        connection = response.json()
        connection_id = connection["id"]

        try:
            # Wait for sync to complete (not fail)
            elapsed = 0
            timeout = 120
            while elapsed < timeout:
                await asyncio.sleep(3)
                elapsed += 3
                resp = await api_client.get(f"/source-connections/{connection_id}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                sync_info = data.get("sync")
                if sync_info and sync_info.get("last_job"):
                    job = sync_info["last_job"]
                    if job.get("status") in ("completed", "failed"):
                        break

            assert data["status"] != "needs_reauth"
            assert data.get("error_category") is None
        finally:
            await api_client.delete(f"/source-connections/{connection_id}")
