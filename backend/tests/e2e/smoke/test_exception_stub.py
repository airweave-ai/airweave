"""E2E tests for the exception_stub source.

Exercises the exception stub source through the public API to verify
that different error scenarios are handled correctly by the sync pipeline.
Uses direct auth (no external credentials needed).
"""

import asyncio
import uuid
from typing import Dict, Optional, Set, Tuple

import httpx
import pytest


class TestExceptionStub:
    """Test suite for the exception_stub source error handling flows."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _create_connection(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        config: Optional[Dict] = None,
        sync_immediately: bool = False,
    ) -> httpx.Response:
        """Create an exception_stub source connection, returning the raw response."""
        payload = {
            "name": f"Exception Stub {uuid.uuid4().hex[:8]}",
            "short_name": "exception_stub",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"stub_key": "test"}},
            "config": config or {},
            "sync_immediately": sync_immediately,
        }
        return await api_client.post("/source-connections", json=payload)

    async def _create_and_cleanup(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        config: Optional[Dict] = None,
    ) -> Dict:
        """Create an exception_stub connection, returning the connection dict.

        Caller must handle cleanup via DELETE.
        """
        response = await self._create_connection(api_client, collection, config)
        assert response.status_code == 200, (
            f"Failed to create exception_stub connection: {response.text}"
        )
        return response.json()

    async def _run_and_wait_terminal(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        timeout: int = 60,
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Trigger a sync and wait for a terminal status.

        Returns (job_dict, last_status). job_dict is None on timeout.
        """
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200, f"Failed to trigger sync: {response.text}"
        job = response.json()
        job_id = job["id"]

        terminal: Set[str] = {"completed", "failed", "cancelled"}
        last_status: Optional[str] = None
        elapsed = 0

        while elapsed < timeout:
            response = await api_client.get(f"/source-connections/{conn_id}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                matched = next((j for j in jobs if j["id"] == job_id), None)
                if matched:
                    last_status = matched["status"]
                    if last_status in terminal:
                        return matched, last_status

            await asyncio.sleep(1)
            elapsed += 1

        return None, last_status

    # ==================================================================
    # CONNECTION CREATION
    # ==================================================================

    @pytest.mark.asyncio
    async def test_create_connection(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Create an exception_stub connection and verify the response shape."""
        response = await self._create_connection(api_client, collection)
        assert response.status_code == 200

        conn = response.json()
        assert conn["short_name"] == "exception_stub"
        assert conn["auth"]["method"] == "direct"
        assert conn["auth"]["authenticated"] is True
        assert conn["status"] == "active"

        await api_client.delete(f"/source-connections/{conn['id']}")

    @pytest.mark.asyncio
    async def test_fail_on_validate(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """fail_on_validate=True should reject connection creation (validate runs during create)."""
        response = await self._create_connection(
            api_client,
            collection,
            config={
                "fail_on_validate": True,
                "exception_type": "source_auth_error",
            },
        )
        # validate() is called during direct auth creation and should fail
        assert response.status_code in (400, 403), (
            f"Expected 400/403 for fail_on_validate, got {response.status_code}: {response.text}"
        )

    # ==================================================================
    # BASELINE SYNC (NO ERROR)
    # ==================================================================

    @pytest.mark.asyncio
    async def test_baseline_sync_completes(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """When trigger_after exceeds entity_count, sync completes without error."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={"entity_count": 10, "trigger_after": 100, "seed": 42},
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "completed"
            assert job["entities_inserted"] > 0
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    # ==================================================================
    # TRIGGER POINT VARIATIONS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_immediate_failure(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """trigger_after=0 should fail immediately after the container entity."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={
                "entity_count": 10,
                "trigger_after": 0,
                "exception_type": "runtime_error",
            },
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
            assert job["error"] is not None
            assert "ExceptionStub" in job["error"]
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_midstream_failure(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """trigger_after=5 with entity_count=10 should fail midstream."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={
                "entity_count": 10,
                "trigger_after": 5,
                "exception_type": "runtime_error",
            },
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
            assert job["error"] is not None
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_failure_after_last_entity(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """trigger_after=-1 should yield all entities then fail."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={
                "entity_count": 5,
                "trigger_after": -1,
                "exception_type": "runtime_error",
            },
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
            assert job["error"] is not None
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    # ==================================================================
    # EXCEPTION TYPE VARIATIONS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_source_auth_error(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """source_auth_error should cause sync failure."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={
                "trigger_after": 0,
                "exception_type": "source_auth_error",
                "auth_provider_kind": "oauth",
            },
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
            assert job["error"] is not None
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_source_server_error(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """source_server_error should cause sync failure."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={"trigger_after": 0, "exception_type": "source_server_error"},
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_source_rate_limit_error(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """source_rate_limit_error should cause sync failure."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={"trigger_after": 0, "exception_type": "source_rate_limit_error"},
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_timeout_error(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """asyncio.TimeoutError should cause sync failure."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={"trigger_after": 0, "exception_type": "timeout"},
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    @pytest.mark.asyncio
    async def test_token_expired_error(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """token_expired should cause sync failure."""
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={"trigger_after": 0, "exception_type": "token_expired"},
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    # ==================================================================
    # CUSTOM ERROR MESSAGE
    # ==================================================================

    @pytest.mark.asyncio
    async def test_custom_error_message(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Custom error_message should appear in the failed job's error field."""
        custom_msg = "Custom E2E test error for verification"
        conn = await self._create_and_cleanup(
            api_client,
            collection,
            config={
                "trigger_after": 0,
                "exception_type": "runtime_error",
                "error_message": custom_msg,
            },
        )
        conn_id = conn["id"]

        try:
            job, status = await self._run_and_wait_terminal(api_client, conn_id)
            assert job is not None, f"Sync should reach terminal state (last: {status})"
            assert job["status"] == "failed"
            assert custom_msg in job["error"], (
                f"Expected custom message in error, got: {job['error']}"
            )
        finally:
            await api_client.delete(f"/source-connections/{conn_id}")

    # ==================================================================
    # DETERMINISM
    # ==================================================================

    @pytest.mark.asyncio
    async def test_deterministic_entity_count(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Two baseline syncs with the same seed should produce the same entity counts."""
        config = {"entity_count": 10, "trigger_after": 100, "seed": 777}

        conn1 = await self._create_and_cleanup(api_client, collection, config=config)
        conn2 = await self._create_and_cleanup(api_client, collection, config=config)

        try:
            job1, s1 = await self._run_and_wait_terminal(api_client, conn1["id"])
            job2, s2 = await self._run_and_wait_terminal(api_client, conn2["id"])

            assert job1 is not None, f"First sync should complete (last: {s1})"
            assert job2 is not None, f"Second sync should complete (last: {s2})"
            assert job1["status"] == "completed"
            assert job2["status"] == "completed"
            assert job1["entities_inserted"] == job2["entities_inserted"]
        finally:
            await api_client.delete(f"/source-connections/{conn1['id']}")
            await api_client.delete(f"/source-connections/{conn2['id']}")
