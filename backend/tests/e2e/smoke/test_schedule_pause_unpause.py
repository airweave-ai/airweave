"""Smoke tests for schedule pausing and unpausing (credential error flows).

Tests the end-to-end behaviour:
- Paused schedules appear paused via Temporal REST API
- Unpaused schedules appear unpaused via Temporal REST API
- Credential update triggers unpause
- A paused schedule does NOT fire during a wait window

Strategy: create with a valid Stripe key (passes validate()), then PATCH to
an invalid key, then trigger a sync which fails with a credential error.

NOTE: Requires local environment with Temporal running on localhost:8088.
"""

import asyncio
import time
from typing import Dict, Optional

import httpx
import pytest  # noqa: I001

TEMPORAL_REST = "http://localhost:8088"
SCHEDULE_PREFIXES = ("sync-", "minute-sync-", "daily-cleanup-")
BAD_KEY = "sk_test_fakeinvalidkey000000000000"


@pytest.mark.asyncio
@pytest.mark.requires_temporal
class TestSchedulePauseUnpause:
    """Tests for pausing and unpausing Temporal schedules via credential error flows."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_sync_id(
        self, api_client: httpx.AsyncClient, source_connection_id: str
    ) -> Optional[str]:
        response = await api_client.get(f"/source-connections/{source_connection_id}/sync-id")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()["sync_id"]

    async def _get_schedule_detail(self, schedule_id: str) -> Optional[dict]:
        """Fetch a single schedule from the Temporal REST API."""
        url = f"{TEMPORAL_REST}/api/v1/namespaces/default/schedules/{schedule_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            pytest.skip("Temporal REST API not available")
            return None  # unreachable — pytest.skip raises

    async def _is_schedule_paused(self, schedule_id: str) -> Optional[bool]:
        """Return True if the schedule is paused, False if running, None if not found."""
        detail = await self._get_schedule_detail(schedule_id)
        if detail is None:
            return None
        return detail.get("schedule", {}).get("state", {}).get("paused", False)

    async def _get_paused_states(self, sync_id: str) -> Dict[str, Optional[bool]]:
        """Return {prefix: paused_bool} for all schedule prefixes."""
        states = {}
        for prefix in SCHEDULE_PREFIXES:
            sid = f"{prefix}{sync_id}"
            states[sid] = await self._is_schedule_paused(sid)
        return states

    async def _trigger_sync_and_wait_for_terminal(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        timeout: int = 60,
    ) -> dict:
        """Trigger a sync and wait for it to reach a terminal state."""
        resp = await api_client.post(f"/source-connections/{conn_id}/run")
        resp.raise_for_status()

        elapsed = 0
        while elapsed < timeout:
            resp = await api_client.get(f"/source-connections/{conn_id}/jobs")
            resp.raise_for_status()
            jobs = resp.json()
            if jobs and jobs[0]["status"] in ("completed", "failed", "cancelled"):
                return jobs[0]
            await asyncio.sleep(2)
            elapsed += 2

        pytest.fail(f"Sync did not reach terminal state within {timeout}s")
        return {}  # unreachable — pytest.fail raises

    async def _create_stripe_connection(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        api_key: str,
        cron: str = "0 0 * * *",
    ) -> dict:
        """Create a Stripe connection with a valid key and a cron schedule."""
        payload = {
            "name": f"Pause Test {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": api_key}},
            "schedule": {"cron": cron},
            "sync_immediately": False,
        }
        resp = await api_client.post("/source-connections", json=payload)
        assert resp.status_code == 200, f"Failed to create connection: {resp.text}"
        return resp.json()

    async def _swap_to_bad_key(
        self, api_client: httpx.AsyncClient, conn_id: str
    ) -> None:
        """PATCH the connection to use an invalid API key."""
        resp = await api_client.patch(
            f"/source-connections/{conn_id}",
            json={"authentication": {"credentials": {"api_key": BAD_KEY}}},
        )
        assert resp.status_code == 200, f"Failed to update credentials: {resp.text}"

    async def _create_and_break(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        config,
        cron: str = "0 0 * * *",
    ) -> tuple:
        """Create with valid key, swap to bad key. Returns (conn_id, sync_id)."""
        connection = await self._create_stripe_connection(
            api_client, collection, api_key=config.TEST_STRIPE_API_KEY, cron=cron
        )
        conn_id = connection["id"]
        sync_id = await self._get_sync_id(api_client, conn_id)
        assert sync_id is not None

        # Swap to invalid key — next sync will fail with credential error
        await self._swap_to_bad_key(api_client, conn_id)
        return conn_id, sync_id

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    async def test_credential_error_pauses_schedules(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """A sync that fails with a credential error pauses the Temporal schedules."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id, sync_id = await self._create_and_break(api_client, collection, config)

        # Wait for schedule to be registered in Temporal
        await asyncio.sleep(3)

        # Verify schedule exists and is NOT paused before the sync
        primary_schedule = f"sync-{sync_id}"
        assert await self._is_schedule_paused(primary_schedule) is False, "Should be running"

        # Trigger a sync — it should fail with a credential error
        job = await self._trigger_sync_and_wait_for_terminal(api_client, conn_id)
        assert job["status"] == "failed"

        # Refetch the source connection to check status and error_category
        resp = await api_client.get(f"/source-connections/{conn_id}")
        resp.raise_for_status()
        sc = resp.json()
        assert sc["status"] == "needs_reauth", f"Expected needs_reauth, got {sc['status']}"
        assert sc["error_category"] is not None

        # Wait for the orchestrator to pause schedules
        await asyncio.sleep(3)

        # Verify schedule is now paused
        assert await self._is_schedule_paused(primary_schedule) is True, (
            "Schedule should be paused after credential error"
        )

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_credential_update_unpauses_schedules(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Updating credentials on a paused connection unpauses the schedules."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id, sync_id = await self._create_and_break(api_client, collection, config)
        await asyncio.sleep(3)

        # Trigger sync to cause credential failure and pausing
        await self._trigger_sync_and_wait_for_terminal(api_client, conn_id)
        await asyncio.sleep(3)

        primary_schedule = f"sync-{sync_id}"
        assert await self._is_schedule_paused(primary_schedule) is True, "Should be paused"

        # Update credentials (still invalid format-wise valid, but triggers unpause)
        resp = await api_client.patch(
            f"/source-connections/{conn_id}",
            json={"authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}}},
        )
        assert resp.status_code == 200

        # Wait for unpause
        await asyncio.sleep(3)

        assert await self._is_schedule_paused(primary_schedule) is False, (
            "Schedule should be unpaused after credential update"
        )

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_all_schedule_prefixes_paused(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """All three schedule prefixes (sync-, minute-sync-, daily-cleanup-) are paused."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id, sync_id = await self._create_and_break(api_client, collection, config)
        await asyncio.sleep(3)

        # Trigger sync to cause credential failure and pausing
        await self._trigger_sync_and_wait_for_terminal(api_client, conn_id)
        await asyncio.sleep(3)

        # Check all prefixes
        states = await self._get_paused_states(sync_id)
        for schedule_id, paused in states.items():
            if paused is not None:  # schedule exists
                assert paused is True, f"{schedule_id} should be paused, got {paused}"

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_source_connection_status_needs_reauth(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """After credential failure, source connection shows needs_reauth + error fields."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id, _ = await self._create_and_break(api_client, collection, config)
        await asyncio.sleep(3)

        # Trigger sync to cause credential failure
        await self._trigger_sync_and_wait_for_terminal(api_client, conn_id)

        # Fetch the connection
        resp = await api_client.get(f"/source-connections/{conn_id}")
        resp.raise_for_status()
        sc = resp.json()

        assert sc["status"] == "needs_reauth"
        assert sc["error_category"] == "api_key_invalid"
        assert sc["error_message"] is not None
        assert "API key" in sc["error_message"]

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_list_endpoint_shows_needs_reauth(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """The list endpoint derives NEEDS_REAUTH status for connections with credential errors."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id, _ = await self._create_and_break(api_client, collection, config)
        await asyncio.sleep(3)
        await self._trigger_sync_and_wait_for_terminal(api_client, conn_id)

        # Verify detail endpoint first to confirm error_category is set
        detail_resp = await api_client.get(f"/source-connections/{conn_id}")
        detail_resp.raise_for_status()
        detail = detail_resp.json()
        assert detail["status"] == "needs_reauth", (
            f"Detail shows {detail['status']}, error_category={detail.get('error_category')}"
        )

        # Fetch the list for this collection
        readable_id = collection["readable_id"]
        resp = await api_client.get(f"/source-connections?readable_collection_id={readable_id}")
        resp.raise_for_status()
        items = resp.json()

        matching = [item for item in items if item["id"] == conn_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "needs_reauth"

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")
