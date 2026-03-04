"""Async test module for running and cancelling sync jobs.

Tests comprehensive sync job lifecycle including state transitions,
concurrent run prevention, cancellation scenarios, and deletion-during-sync
edge cases.

Uses the TimedSource (internal source with precise timing control) to
eliminate external service dependencies and make timing deterministic.
"""

import pytest
import httpx
import asyncio
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple


class TestRunningAndCancellingSyncs:
    """Test suite for sync job lifecycle management.

    Uses timed_source_connection_fast (20 entities / 2s) and
    timed_source_connection_medium (100 entities / 30s) fixtures.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _wait_for_job_status(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        job_id: str,
        expected_statuses: str | Set[str],
        timeout: int = 30,
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Wait for a job to reach any of the expected statuses.

        Args:
            api_client: HTTP client.
            conn_id: Source connection ID.
            job_id: Job ID to monitor.
            expected_statuses: Single status string or set of acceptable statuses.
            timeout: Maximum wait time in seconds.

        Returns:
            Tuple of (job_dict, last_seen_status). job_dict is None on timeout.
        """
        if isinstance(expected_statuses, str):
            expected_statuses = {expected_statuses}

        last_status: Optional[str] = None
        elapsed = 0
        poll_interval = 1

        while elapsed < timeout:
            response = await api_client.get(f"/source-connections/{conn_id}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                job = next((j for j in jobs if j["id"] == job_id), None)
                if job:
                    last_status = job["status"]
                    if last_status in expected_statuses:
                        return job, last_status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return None, last_status

    async def _wait_for_running(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        job_id: str,
        timeout: int = 15,
    ) -> Optional[Dict]:
        """Wait for a job to reach the running state (or a later state).

        Returns the job dict once it reaches running, completed, failed,
        cancelling, or cancelled (i.e., it has moved past pending).
        """
        job, _ = await self._wait_for_job_status(
            api_client,
            conn_id,
            job_id,
            {"running", "completed", "failed", "cancelling", "cancelled"},
            timeout=timeout,
        )
        return job

    async def _run_and_wait_for_running(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        timeout: int = 15,
    ) -> Dict:
        """Trigger a sync and wait for it to be actively running.

        Returns the job dict.
        """
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200, f"Failed to trigger sync: {response.text}"

        job = response.json()
        assert "id" in job

        running_job = await self._wait_for_running(
            api_client, conn_id, job["id"], timeout=timeout
        )
        assert running_job is not None, (
            f"Job {job['id']} did not move past pending within {timeout}s"
        )

        return running_job

    # ==================================================================
    # BASIC RUNNING TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_run_sync_job(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test basic sync job execution."""
        conn_id = timed_source_connection_fast["id"]

        # Trigger a sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200

        job = response.json()
        assert "id" in job
        assert job["status"] in ["pending", "running"]

        # Wait for the job to at least start
        running = await self._wait_for_running(api_client, conn_id, job["id"])
        assert running is not None

        # Check the source connection reflects the job
        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200

        connection = response.json()
        assert connection["sync"]["last_job"]["id"] == job["id"]

    @pytest.mark.asyncio
    async def test_cannot_run_while_already_running(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test that starting a new sync while one is running is prevented."""
        conn_id = timed_source_connection_medium["id"]

        # Start and wait for it to be running
        job = await self._run_and_wait_for_running(api_client, conn_id)

        # Try to start second sync - should fail
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 400

        error = response.json()
        error_detail = error["detail"].lower()
        assert "already running" in error_detail or "already pending" in error_detail

    @pytest.mark.asyncio
    async def test_can_run_after_completion(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test that a new sync can be started after previous one completes."""
        conn_id = timed_source_connection_fast["id"]

        # Run first sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        first_job = response.json()

        # Wait for completion
        completed, status = await self._wait_for_job_status(
            api_client, conn_id, first_job["id"], "completed", timeout=30
        )
        assert completed is not None, f"First job should complete (last status: {status})"

        # Now run second sync - should succeed
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        second_job = response.json()

        assert second_job["id"] != first_job["id"]

    # ==================================================================
    # CANCELLATION TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_cancel_running_sync_job(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test cancelling an in-progress sync job."""
        conn_id = timed_source_connection_medium["id"]

        # Start and wait for running
        job = await self._run_and_wait_for_running(api_client, conn_id)
        job_id = job["id"]

        # Cancel the sync job
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 200

        # Check immediate status - should be cancelling or already cancelled
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        assert response.status_code == 200

        jobs = response.json()
        our_job = next((j for j in jobs if j["id"] == job_id), None)
        assert our_job is not None
        assert our_job["status"] in ["cancelling", "cancelled"]

        # Wait for cancellation to complete
        cancelled, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=30
        )
        assert cancelled is not None, f"Job should reach cancelled (last status: {status})"

    @pytest.mark.asyncio
    async def test_cannot_cancel_non_existent_job(self, api_client: httpx.AsyncClient):
        """Test cancelling a non-existent job returns 404."""
        fake_job_id = "00000000-0000-0000-0000-000000000000"
        fake_conn_id = "00000000-0000-0000-0000-000000000001"

        response = await api_client.post(
            f"/source-connections/{fake_conn_id}/jobs/{fake_job_id}/cancel"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_job(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test that cancelling an already completed job is rejected."""
        conn_id = timed_source_connection_fast["id"]

        # Run sync to completion
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait for completion
        completed, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "completed", timeout=30
        )
        assert completed is not None, f"Job should complete (last status: {status})"
        assert completed["entities_inserted"] >= 0

        # Try to cancel completed job - should fail
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 400

        error = response.json()
        error_detail = error["detail"].lower()
        assert "already completed" in error_detail or "cannot cancel" in error_detail

    @pytest.mark.asyncio
    async def test_cannot_cancel_if_nothing_running(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test that cancellation fails when no job is running."""
        conn_id = timed_source_connection_fast["id"]

        # Try to cancel without any job running
        fake_job_id = "00000000-0000-0000-0000-000000000000"
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{fake_job_id}/cancel"
        )

        # Should return 404 since job doesn't exist
        assert response.status_code == 404

    # ==================================================================
    # STATE TRANSITION TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_cannot_run_while_in_cancelling_state(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test that new sync cannot start while another is being cancelled.

        Note: If cancellation completes before the second run request arrives,
        the run will succeed (200) which is correct behaviour -- the system is
        fast. We test both paths.
        """
        conn_id = timed_source_connection_medium["id"]

        # Start and wait for running
        job = await self._run_and_wait_for_running(api_client, conn_id)
        job_id = job["id"]

        # Cancel it
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 200

        # Immediately try to start new sync while cancelling.
        # Two valid outcomes:
        #   400 = we caught the CANCELLING window (sync still winding down)
        #   200 = cancellation completed fast; new sync starts fine
        response = await api_client.post(f"/source-connections/{conn_id}/run")

        if response.status_code == 400:
            # Caught the CANCELLING window -- verify the error message
            error = response.json()
            error_detail = error["detail"].lower()
            assert "a sync job is already" in error_detail and (
                "running" in error_detail
                or "cancelling" in error_detail
                or "pending" in error_detail
            )

            # Wait for cancellation to complete
            await self._wait_for_job_status(
                api_client, conn_id, job_id, "cancelled", timeout=30
            )

            # Now should be able to run
            response = await api_client.post(f"/source-connections/{conn_id}/run")
            assert response.status_code == 200
        else:
            # Cancellation completed fast; the second run succeeded immediately
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_job_state_transitions(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test that job goes through expected state transitions."""
        conn_id = timed_source_connection_fast["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Should start as pending
        assert job["status"] == "pending"

        # Wait for it to progress past pending
        progressed = await self._wait_for_running(api_client, conn_id, job_id)
        assert progressed is not None, "Job should move past pending"
        assert progressed["status"] in ["running", "completed"]

        # Wait for completion
        completed, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "completed", timeout=30
        )
        assert completed is not None, f"Job should complete (last status: {status})"
        assert completed["status"] == "completed"
        assert "started_at" in completed
        assert "completed_at" in completed

    # ==================================================================
    # CONCURRENT OPERATIONS TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_multiple_cancel_requests(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test that multiple cancel requests for same job are handled gracefully."""
        conn_id = timed_source_connection_medium["id"]

        # Start and wait for running
        job = await self._run_and_wait_for_running(api_client, conn_id)
        job_id = job["id"]

        # Send multiple cancel requests
        response1 = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        response2 = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        response3 = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )

        # First should succeed
        assert response1.status_code == 200

        # Others should either succeed (idempotent) or return appropriate error
        assert response2.status_code in [200, 400]
        assert response3.status_code in [200, 400]

    # ==================================================================
    # EDGE CASE: CANCEL AT DIFFERENT PHASES
    # ==================================================================

    @pytest.mark.asyncio
    async def test_cancel_early_before_entities_written(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test cancelling a sync very early, before many entities are processed.

        Uses the medium source (30s) so the sync is still in its early phase.
        Cancels as soon as the job transitions to running.
        """
        conn_id = timed_source_connection_medium["id"]

        # Trigger the sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait just until the job is running (don't wait for entities)
        running = await self._wait_for_running(api_client, conn_id, job_id, timeout=15)
        assert running is not None, "Job should reach running state"

        # Cancel immediately
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 200

        # Should reach cancelled
        cancelled, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=30
        )
        assert cancelled is not None, (
            f"Job should be cancelled after early cancel (last status: {status})"
        )

    @pytest.mark.asyncio
    async def test_cancel_midway_through_sync(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict
    ):
        """Test cancelling a sync roughly halfway through.

        Uses the medium source (100 entities / 30s) and waits ~15s before cancelling.
        """
        conn_id = timed_source_connection_medium["id"]

        # Start and wait for running
        job = await self._run_and_wait_for_running(api_client, conn_id)
        job_id = job["id"]

        # Wait for roughly half the sync duration
        await asyncio.sleep(12)

        # Cancel
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 200

        # Should reach cancelled
        cancelled, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=30
        )
        assert cancelled is not None, (
            f"Job should be cancelled after midway cancel (last status: {status})"
        )

    @pytest.mark.asyncio
    async def test_cancel_near_completion(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Test cancelling a sync right before it would complete.

        Uses the fast source (20 entities / 2s). The cancel may arrive after
        the sync has already completed, which should be handled gracefully.
        """
        conn_id = timed_source_connection_fast["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait long enough that the sync might be done or nearly done
        await asyncio.sleep(3)

        # Attempt cancel -- may succeed (200) or fail (400) if already completed
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code in [200, 400]

        # Either way, the job should reach a terminal state
        terminal, status = await self._wait_for_job_status(
            api_client,
            conn_id,
            job_id,
            {"completed", "cancelled"},
            timeout=20,
        )
        assert terminal is not None, (
            f"Job should reach a terminal state (last status: {status})"
        )

    # ==================================================================
    # EDGE CASE: DELETE SOURCE CONNECTION DURING ACTIVE SYNC
    # ==================================================================

    @pytest.mark.asyncio
    async def test_delete_source_connection_during_active_sync(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test deleting a source connection while its sync is actively running.

        The cancellation barrier should ensure the Temporal workflow terminates
        before cleanup runs, preventing orphaned data.
        """
        # Create a medium timed connection inline (we manage lifecycle ourselves)
        connection_data = {
            "name": f"Timed Delete Test {uuid.uuid4().hex[:8]}",
            "short_name": "timed",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"timed_key": "test"}},
            "config": {"entity_count": 100, "duration_seconds": 30, "seed": 99},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=connection_data)
        assert response.status_code == 200, f"Failed to create connection: {response.text}"
        connection = response.json()
        conn_id = connection["id"]

        try:
            # Start the sync and wait for it to be running
            job = await self._run_and_wait_for_running(api_client, conn_id)
            assert job is not None, "Sync should start running"

            # Wait a bit so some entities are written
            await asyncio.sleep(3)

            # Delete the source connection while sync is running
            response = await api_client.delete(f"/source-connections/{conn_id}")
            # Should succeed -- the barrier waits for the workflow to stop
            assert response.status_code == 200, (
                f"Delete should succeed (got {response.status_code}: {response.text})"
            )

            # Verify the source connection is gone
            response = await api_client.get(f"/source-connections/{conn_id}")
            assert response.status_code == 404
        except Exception:
            # Best effort cleanup if test fails
            try:
                await api_client.delete(f"/source-connections/{conn_id}")
            except Exception:
                pass
            raise

    # ==================================================================
    # COLLECTION DELETION TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_delete_collection_during_active_sync(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a collection while a sync inside it is actively running.

        The cancellation barrier should ensure all workflows terminate before
        cleanup runs and the CASCADE delete fires.
        """
        # Create a dedicated collection for this test
        collection_data = {"name": f"Delete Test Collection {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        readable_id = collection["readable_id"]

        try:
            # Create a timed connection inside the collection
            connection_data = {
                "name": f"Timed Collection Delete {uuid.uuid4().hex[:8]}",
                "short_name": "timed",
                "readable_collection_id": readable_id,
                "authentication": {"credentials": {"timed_key": "test"}},
                "config": {"entity_count": 100, "duration_seconds": 30, "seed": 101},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=connection_data)
            assert response.status_code == 200
            conn_id = response.json()["id"]

            # Start the sync and wait for it to be running
            job = await self._run_and_wait_for_running(api_client, conn_id)
            assert job is not None

            # Wait a bit for some entities to be written
            await asyncio.sleep(3)

            # Delete the entire collection while sync is running
            response = await api_client.delete(f"/collections/{readable_id}")
            assert response.status_code == 200, (
                f"Collection delete should succeed "
                f"(got {response.status_code}: {response.text})"
            )

            # Verify the collection is gone
            response = await api_client.get(f"/collections/{readable_id}")
            assert response.status_code == 404
        except Exception:
            # Best effort cleanup
            try:
                await api_client.delete(f"/collections/{readable_id}")
            except Exception:
                pass
            raise

    @pytest.mark.asyncio
    async def test_delete_collection_with_multiple_running_syncs(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a collection that has multiple source connections with active syncs.

        This exercises the barrier's ability to wait on multiple Temporal workflows
        concurrently. All workflows must reach terminal state before cleanup runs.
        """
        collection_data = {"name": f"Multi Sync Delete {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        readable_id = collection["readable_id"]

        try:
            conn_ids = []
            # Create two source connections in the same collection
            for i, (count, duration, seed) in enumerate([
                (80, 25, 201),
                (60, 20, 202),
            ]):
                connection_data = {
                    "name": f"Timed Multi {i} {uuid.uuid4().hex[:8]}",
                    "short_name": "timed",
                    "readable_collection_id": readable_id,
                    "authentication": {"credentials": {"timed_key": "test"}},
                    "config": {
                        "entity_count": count,
                        "duration_seconds": duration,
                        "seed": seed,
                    },
                    "sync_immediately": False,
                }
                response = await api_client.post(
                    "/source-connections", json=connection_data
                )
                assert response.status_code == 200, (
                    f"Failed to create connection {i}: {response.text}"
                )
                conn_ids.append(response.json()["id"])

            # Start syncs on both connections (use longer timeout since the
            # Temporal worker may need time to pick up the second job)
            for conn_id in conn_ids:
                job = await self._run_and_wait_for_running(
                    api_client, conn_id, timeout=30
                )
                assert job is not None, f"Sync for {conn_id} should start running"

            # Wait for some entities to be written across both syncs
            await asyncio.sleep(5)

            # Delete the collection -- barrier must wait for BOTH workflows
            response = await api_client.delete(f"/collections/{readable_id}")
            assert response.status_code == 200, (
                f"Collection delete with multiple running syncs should succeed "
                f"(got {response.status_code}: {response.text})"
            )

            # Verify everything is gone
            response = await api_client.get(f"/collections/{readable_id}")
            assert response.status_code == 404

            for conn_id in conn_ids:
                response = await api_client.get(f"/source-connections/{conn_id}")
                assert response.status_code == 404
        except Exception:
            try:
                await api_client.delete(f"/collections/{readable_id}")
            except Exception:
                pass
            raise

    @pytest.mark.asyncio
    async def test_delete_collection_with_mixed_sync_states(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a collection with one completed sync and one running sync.

        The barrier should only wait for the running sync while the completed
        sync's data is cleaned up immediately.
        """
        collection_data = {"name": f"Mixed State Delete {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        readable_id = collection["readable_id"]

        try:
            # Connection 1: fast sync that will complete before we delete
            conn1_data = {
                "name": f"Timed Fast Done {uuid.uuid4().hex[:8]}",
                "short_name": "timed",
                "readable_collection_id": readable_id,
                "authentication": {"credentials": {"timed_key": "test"}},
                "config": {"entity_count": 10, "duration_seconds": 1, "seed": 301},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=conn1_data)
            assert response.status_code == 200
            conn1_id = response.json()["id"]

            # Connection 2: slow sync that will be running when we delete
            conn2_data = {
                "name": f"Timed Slow Running {uuid.uuid4().hex[:8]}",
                "short_name": "timed",
                "readable_collection_id": readable_id,
                "authentication": {"credentials": {"timed_key": "test"}},
                "config": {"entity_count": 100, "duration_seconds": 30, "seed": 302},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=conn2_data)
            assert response.status_code == 200
            conn2_id = response.json()["id"]

            # Start the fast sync and wait for it to complete
            response = await api_client.post(f"/source-connections/{conn1_id}/run")
            assert response.status_code == 200
            fast_job = response.json()

            completed, status = await self._wait_for_job_status(
                api_client, conn1_id, fast_job["id"], "completed", timeout=30
            )
            assert completed is not None, (
                f"Fast sync should complete (last status: {status})"
            )

            # Start the slow sync and wait for it to be running
            slow_job = await self._run_and_wait_for_running(api_client, conn2_id)
            assert slow_job is not None

            # Wait a bit for the slow sync to make progress
            await asyncio.sleep(3)

            # Delete the collection: one sync completed, one running
            response = await api_client.delete(f"/collections/{readable_id}")
            assert response.status_code == 200, (
                f"Collection delete with mixed sync states should succeed "
                f"(got {response.status_code}: {response.text})"
            )

            # Verify everything is gone
            response = await api_client.get(f"/collections/{readable_id}")
            assert response.status_code == 404
        except Exception:
            try:
                await api_client.delete(f"/collections/{readable_id}")
            except Exception:
                pass
            raise

    @pytest.mark.asyncio
    async def test_delete_collection_while_sync_is_cancelling(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a collection while a sync is in the CANCELLING state.

        This exercises the edge case where a user cancels a sync, and before
        cancellation completes, deletes the collection. The barrier should
        recognize the CANCELLING job and wait for it to reach CANCELLED.
        """
        collection_data = {"name": f"Cancelling Delete {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        readable_id = collection["readable_id"]

        try:
            connection_data = {
                "name": f"Timed Cancelling {uuid.uuid4().hex[:8]}",
                "short_name": "timed",
                "readable_collection_id": readable_id,
                "authentication": {"credentials": {"timed_key": "test"}},
                "config": {"entity_count": 100, "duration_seconds": 30, "seed": 401},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=connection_data)
            assert response.status_code == 200
            conn_id = response.json()["id"]

            # Start sync and wait for running (longer timeout since previous
            # tests may have consumed Temporal worker capacity)
            job = await self._run_and_wait_for_running(
                api_client, conn_id, timeout=30
            )
            job_id = job["id"]

            # Cancel the sync -- puts it into CANCELLING state
            response = await api_client.post(
                f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
            )
            assert response.status_code == 200

            # Immediately delete the collection while the sync is still cancelling.
            # The barrier should detect the CANCELLING state and wait for terminal.
            response = await api_client.delete(f"/collections/{readable_id}")
            assert response.status_code == 200, (
                f"Collection delete during CANCELLING should succeed "
                f"(got {response.status_code}: {response.text})"
            )

            response = await api_client.get(f"/collections/{readable_id}")
            assert response.status_code == 404
        except Exception:
            try:
                await api_client.delete(f"/collections/{readable_id}")
            except Exception:
                pass
            raise

    @pytest.mark.asyncio
    async def test_delete_collection_after_completed_sync(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a collection after its sync has completed successfully.

        This is the clean path: no running workflows, just data cleanup.
        Verifies that cleanup handles the completed-sync case correctly.
        """
        collection_data = {"name": f"Clean Delete {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        readable_id = collection["readable_id"]

        try:
            connection_data = {
                "name": f"Timed Clean {uuid.uuid4().hex[:8]}",
                "short_name": "timed",
                "readable_collection_id": readable_id,
                "authentication": {"credentials": {"timed_key": "test"}},
                "config": {"entity_count": 10, "duration_seconds": 1, "seed": 501},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=connection_data)
            assert response.status_code == 200
            conn_id = response.json()["id"]

            # Run sync to completion (longer timeout since Temporal worker
            # may be busy finishing previous tests' cleanup)
            response = await api_client.post(f"/source-connections/{conn_id}/run")
            assert response.status_code == 200
            job = response.json()

            completed, status = await self._wait_for_job_status(
                api_client, conn_id, job["id"], "completed", timeout=60,
            )
            assert completed is not None, (
                f"Sync should complete (last status: {status})"
            )
            assert completed["entities_inserted"] > 0

            # Delete collection after sync is done
            response = await api_client.delete(f"/collections/{readable_id}")
            assert response.status_code == 200

            response = await api_client.get(f"/collections/{readable_id}")
            assert response.status_code == 404
        except Exception:
            try:
                await api_client.delete(f"/collections/{readable_id}")
            except Exception:
                pass
            raise

    # ==================================================================
    # RAPID LIFECYCLE TESTS
    # ==================================================================

    @pytest.mark.asyncio
    async def test_rapid_create_run_cancel_delete(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test the full rapid lifecycle: create -> run -> cancel -> delete.

        Exercises the entire lifecycle quickly to find race conditions in
        state transitions and cleanup.
        """
        # Create connection
        connection_data = {
            "name": f"Timed Rapid Lifecycle {uuid.uuid4().hex[:8]}",
            "short_name": "timed",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"timed_key": "test"}},
            "config": {"entity_count": 50, "duration_seconds": 15, "seed": 77},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=connection_data)
        assert response.status_code == 200
        conn_id = response.json()["id"]

        try:
            # Run
            response = await api_client.post(f"/source-connections/{conn_id}/run")
            assert response.status_code == 200
            job_id = response.json()["id"]

            # Wait for running
            running = await self._wait_for_running(api_client, conn_id, job_id)
            assert running is not None

            # Cancel
            response = await api_client.post(
                f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
            )
            assert response.status_code == 200

            # Wait for cancelled
            cancelled, status = await self._wait_for_job_status(
                api_client, conn_id, job_id, "cancelled", timeout=30
            )
            assert cancelled is not None, (
                f"Job should be cancelled (last status: {status})"
            )

            # Delete
            response = await api_client.delete(f"/source-connections/{conn_id}")
            assert response.status_code == 200

            # Verify gone
            response = await api_client.get(f"/source-connections/{conn_id}")
            assert response.status_code == 404
        except Exception:
            try:
                await api_client.delete(f"/source-connections/{conn_id}")
            except Exception:
                pass
            raise

    # ==================================================================
    # TEMPORAL-SPECIFIC TESTS
    # ==================================================================

    @pytest.mark.requires_temporal
    @pytest.mark.asyncio
    async def test_cancel_temporal_workflow(
        self, api_client: httpx.AsyncClient, timed_source_connection_medium: Dict, config
    ):
        """Test that cancellation properly cancels Temporal workflow."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = timed_source_connection_medium["id"]

        # Start and wait for running
        job = await self._run_and_wait_for_running(api_client, conn_id)
        job_id = job["id"]

        # Cancel via API
        response = await api_client.post(
            f"/source-connections/{conn_id}/jobs/{job_id}/cancel"
        )
        assert response.status_code == 200

        # Verify job reaches cancelled state
        cancelled, status = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=30
        )
        assert cancelled is not None, (
            f"Temporal workflow should be cancelled (last status: {status})"
        )
