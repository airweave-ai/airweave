"""Tests for WorkerMetricsRegistry functionality.

Tests the worker metrics registry that tracks active syncs and worker pools.

These tests cover commits:
- 9527bc63d6fbe7b39f21271ae962ca472a9beb89: feat: extensive sync worker metrics
- 6b7cae7898c859cd51de4dbf6136389da264a6df: fix: remove deadlock risks and private API dependencies
"""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.temporal.metrics import WorkerMetricsRegistry


class MockAsyncWorkerPool:
    """Mock AsyncWorkerPool for testing."""

    def __init__(self, task_count: int = 5):
        """Initialize mock worker pool."""
        self.max_workers = 20
        self.pending_tasks = [MagicMock() for _ in range(task_count)]

    @property
    def active_and_pending_count(self) -> int:
        """Return total active and pending tasks."""
        return len(self.pending_tasks)


@pytest.fixture
def registry():
    """Create a fresh WorkerMetricsRegistry instance."""
    return WorkerMetricsRegistry()


@pytest.mark.asyncio
async def test_track_activity_basic(registry):
    """Test basic activity tracking adds and removes activities."""
    sync_job_id = uuid4()
    sync_id = uuid4()
    org_id = uuid4()

    # Initially no activities
    activities = await registry.get_active_activities()
    assert len(activities) == 0

    # Track activity
    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id,
        sync_id=sync_id,
        organization_id=org_id,
        metadata={"source_type": "slack", "org_name": "Test Org"},
    ):
        # Activity should be tracked
        activities = await registry.get_active_activities()
        assert len(activities) == 1
        assert activities[0]["sync_job_id"] == str(sync_job_id)
        # Note: sync_id is not exposed in get_active_activities(), only in internal storage
        assert activities[0]["metadata"]["source_type"] == "slack"

    # After context exits, activity should be removed
    activities = await registry.get_active_activities()
    assert len(activities) == 0


@pytest.mark.asyncio
async def test_register_worker_pool(registry):
    """Test worker pool registration for metrics tracking."""
    sync_id = uuid4()
    sync_job_id = uuid4()
    pool_id = f"sync_{sync_id}_job_{sync_job_id}"
    pool = MockAsyncWorkerPool(task_count=10)

    # Register pool
    registry.register_worker_pool(pool_id, pool)

    # Verify pool is tracked
    total = await registry.get_total_active_and_pending_workers()
    assert total == 10


@pytest.mark.asyncio
async def test_unregister_worker_pool(registry):
    """Test worker pool unregistration."""
    sync_id = uuid4()
    sync_job_id = uuid4()
    pool_id = f"sync_{sync_id}_job_{sync_job_id}"
    pool = MockAsyncWorkerPool(task_count=15)

    # Register and verify
    registry.register_worker_pool(pool_id, pool)
    total = await registry.get_total_active_and_pending_workers()
    assert total == 15

    # Unregister and verify
    registry.unregister_worker_pool(pool_id)
    total = await registry.get_total_active_and_pending_workers()
    assert total == 0


@pytest.mark.asyncio
async def test_multiple_worker_pools_aggregation(registry):
    """Test total count aggregates across multiple worker pools."""
    sync_id_1 = uuid4()
    sync_id_2 = uuid4()
    sync_id_3 = uuid4()

    pool_1 = MockAsyncWorkerPool(task_count=10)
    pool_2 = MockAsyncWorkerPool(task_count=15)
    pool_3 = MockAsyncWorkerPool(task_count=5)

    registry.register_worker_pool(f"sync_{sync_id_1}_job_{uuid4()}", pool_1)
    registry.register_worker_pool(f"sync_{sync_id_2}_job_{uuid4()}", pool_2)
    registry.register_worker_pool(f"sync_{sync_id_3}_job_{uuid4()}", pool_3)

    # Total should be sum of all pools
    total = await registry.get_total_active_and_pending_workers()
    assert total == 30


@pytest.mark.asyncio
async def test_get_per_sync_worker_counts(registry):
    """Test per-sync worker count extraction."""
    sync_id_1 = uuid4()
    sync_id_2 = uuid4()

    pool_1 = MockAsyncWorkerPool(task_count=12)
    pool_2 = MockAsyncWorkerPool(task_count=8)

    registry.register_worker_pool(f"sync_{sync_id_1}_job_{uuid4()}", pool_1)
    registry.register_worker_pool(f"sync_{sync_id_2}_job_{uuid4()}", pool_2)

    counts = await registry.get_per_sync_worker_counts()

    # Should have 2 syncs
    assert len(counts) == 2

    # Find counts by sync_id
    counts_by_id = {c["sync_id"]: c["active_and_pending_worker_count"] for c in counts}
    assert counts_by_id[str(sync_id_1)] == 12
    assert counts_by_id[str(sync_id_2)] == 8


@pytest.mark.asyncio
async def test_get_per_sync_worker_counts_aggregates_duplicate_sync_ids(registry):
    """Test that multiple jobs for same sync aggregate their counts."""
    sync_id = uuid4()
    job_id_1 = uuid4()
    job_id_2 = uuid4()

    pool_1 = MockAsyncWorkerPool(task_count=10)
    pool_2 = MockAsyncWorkerPool(task_count=5)

    # Register two jobs for the same sync (shouldn't happen but handle it)
    registry.register_worker_pool(f"sync_{sync_id}_job_{job_id_1}", pool_1)
    registry.register_worker_pool(f"sync_{sync_id}_job_{job_id_2}", pool_2)

    counts = await registry.get_per_sync_worker_counts()

    # Should aggregate to single sync_id
    assert len(counts) == 1
    assert counts[0]["sync_id"] == str(sync_id)
    assert counts[0]["active_and_pending_worker_count"] == 15  # 10 + 5


@pytest.mark.asyncio
async def test_get_per_connector_metrics(registry):
    """Test connector-type aggregated metrics."""
    sync_id_1 = uuid4()
    sync_id_2 = uuid4()
    sync_id_3 = uuid4()
    org_id = uuid4()

    pool_1 = MockAsyncWorkerPool(task_count=20)
    pool_2 = MockAsyncWorkerPool(task_count=15)
    pool_3 = MockAsyncWorkerPool(task_count=10)

    # Track activities with different connector types
    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=uuid4(),
        sync_id=sync_id_1,
        organization_id=org_id,
        metadata={"source_type": "slack", "org_name": "Org 1"},
    ):
        # Register worker pool for this activity (match by activity_id)
        activity_id = f"run_sync_activity-{list(registry._active_activities.keys())[0].split('-')[1]}"
        registry._worker_pools[list(registry._active_activities.keys())[0]] = pool_1

        async with registry.track_activity(
            activity_name="run_sync_activity",
            sync_job_id=uuid4(),
            sync_id=sync_id_2,
            organization_id=org_id,
            metadata={"source_type": "slack", "org_name": "Org 2"},
        ):
            registry._worker_pools[list(registry._active_activities.keys())[1]] = pool_2

            async with registry.track_activity(
                activity_name="run_sync_activity",
                sync_job_id=uuid4(),
                sync_id=sync_id_3,
                organization_id=org_id,
                metadata={"source_type": "notion", "org_name": "Org 3"},
            ):
                registry._worker_pools[list(registry._active_activities.keys())[2]] = pool_3

                # Get connector metrics
                metrics = await registry.get_per_connector_metrics()

                # Should have 2 connector types
                assert "slack" in metrics
                assert "notion" in metrics

                # Slack should aggregate 2 syncs
                assert metrics["slack"]["active_syncs"] == 2
                assert metrics["slack"]["active_and_pending_workers"] == 35  # 20 + 15

                # Notion should have 1 sync
                assert metrics["notion"]["active_syncs"] == 1
                assert metrics["notion"]["active_and_pending_workers"] == 10


@pytest.mark.asyncio
async def test_get_detailed_sync_metrics(registry):
    """Test detailed sync metrics extraction."""
    sync_id = uuid4()
    sync_job_id = uuid4()
    org_id = uuid4()

    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id,
        sync_id=sync_id,
        organization_id=org_id,
        metadata={
            "source_type": "google_drive",
            "org_name": "Test Organization",
            "connection_name": "My Drive",
        },
    ):
        detailed = await registry.get_detailed_sync_metrics()

        assert len(detailed) == 1
        assert detailed[0]["sync_id"] == str(sync_id)
        assert detailed[0]["sync_job_id"] == str(sync_job_id)
        assert detailed[0]["org_name"] == "Test Organization"
        assert detailed[0]["source_type"] == "google_drive"


@pytest.mark.asyncio
async def test_get_detailed_sync_metrics_filters_non_sync_activities(registry):
    """Test that detailed sync metrics only includes activities with sync_job_id."""
    sync_job_id = uuid4()

    # Activity with sync_job_id
    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id,
        sync_id=uuid4(),
        organization_id=uuid4(),
        metadata={"source_type": "slack", "org_name": "Org 1"},
    ):
        # Activity without sync_job_id (e.g., maintenance task)
        async with registry.track_activity(
            activity_name="cleanup_activity",
            metadata={"task_type": "maintenance"},
        ):
            detailed = await registry.get_detailed_sync_metrics()

            # Should only include the sync activity
            assert len(detailed) == 1
            assert detailed[0]["sync_job_id"] == str(sync_job_id)


@pytest.mark.asyncio
async def test_get_metrics_summary(registry):
    """Test complete metrics summary."""
    sync_job_id_1 = uuid4()
    sync_job_id_2 = uuid4()
    org_id = uuid4()

    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id_1,
        sync_id=uuid4(),
        organization_id=org_id,
        metadata={"source_type": "slack"},
    ):
        async with registry.track_activity(
            activity_name="run_sync_activity",
            sync_job_id=sync_job_id_2,
            sync_id=uuid4(),
            organization_id=org_id,
            metadata={"source_type": "notion"},
        ):
            summary = await registry.get_metrics_summary()

            assert "worker_id" in summary
            assert "uptime_seconds" in summary
            assert summary["active_activities_count"] == 2
            assert len(summary["active_sync_jobs"]) == 2
            assert str(sync_job_id_1) in summary["active_sync_jobs"]
            assert str(sync_job_id_2) in summary["active_sync_jobs"]


@pytest.mark.asyncio
async def test_concurrent_activity_tracking(registry):
    """Test that multiple concurrent activities are tracked correctly."""
    sync_ids = [uuid4() for _ in range(5)]
    org_id = uuid4()

    async def track_sync(sync_id):
        async with registry.track_activity(
            activity_name="run_sync_activity",
            sync_job_id=uuid4(),
            sync_id=sync_id,
            organization_id=org_id,
            metadata={"source_type": "slack"},
        ):
            await asyncio.sleep(0.1)

    # Start all activities concurrently
    tasks = [asyncio.create_task(track_sync(sync_id)) for sync_id in sync_ids]

    # Check during execution
    await asyncio.sleep(0.05)
    activities = await registry.get_active_activities()
    assert len(activities) == 5

    # Wait for completion
    await asyncio.gather(*tasks)

    # All should be cleaned up
    activities = await registry.get_active_activities()
    assert len(activities) == 0


@pytest.mark.asyncio
async def test_worker_pool_with_null_pool(registry):
    """Test that null/invalid pools are handled gracefully."""
    # Register null pool
    registry.register_worker_pool("test_pool", None)

    # Should not crash
    total = await registry.get_total_active_and_pending_workers()
    assert total == 0


@pytest.mark.asyncio
async def test_worker_pool_without_count_property(registry):
    """Test pools without active_and_pending_count property are skipped."""
    pool = MagicMock(spec=['max_workers'])  # Only has max_workers, not active_and_pending_count
    pool.max_workers = 20

    registry.register_worker_pool("test_pool", pool)

    # Should handle gracefully (pool without count property is skipped)
    total = await registry.get_total_active_and_pending_workers()
    assert total == 0


@pytest.mark.asyncio
async def test_duplicate_pool_registration_same_instance(registry):
    """Test duplicate registration of same pool instance logs warning."""
    pool_id = "test_pool"
    pool = MockAsyncWorkerPool(task_count=10)

    # First registration
    registry.register_worker_pool(pool_id, pool)

    # Second registration with same instance should log warning but succeed
    with patch("airweave.domains.temporal.metrics.registry._logger") as mock_logger:
        registry.register_worker_pool(pool_id, pool)
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_pool_id_collision_different_instances(registry):
    """Test collision detection when different pools use same ID."""
    pool_id = "test_pool"
    pool_1 = MockAsyncWorkerPool(task_count=10)
    pool_2 = MockAsyncWorkerPool(task_count=15)

    # First registration
    registry.register_worker_pool(pool_id, pool_1)

    # Second registration with different instance should raise ValueError
    with pytest.raises(ValueError, match="Pool ID.*collision detected"):
        registry.register_worker_pool(pool_id, pool_2)


@pytest.mark.asyncio
async def test_malformed_pool_id_parsing(registry):
    """Test that malformed pool IDs are handled gracefully."""
    pool = MockAsyncWorkerPool(task_count=10)

    # Register pool with malformed ID
    registry.register_worker_pool("malformed_id_no_underscores", pool)

    # Should not crash, just skip this pool
    counts = await registry.get_per_sync_worker_counts()
    assert len(counts) == 0


@pytest.mark.asyncio
async def test_pod_ordinal_extraction():
    """Test pod ordinal extraction from HOSTNAME environment variable."""
    test_cases = [
        ("airweave-worker-0", "0"),
        ("airweave-worker-5", "5"),
        ("airweave-worker-123", "123"),
        ("sync-worker-7", "7"),
        ("random-hostname", "random-hostname"),
        ("no-number-suffix", "no-number-suffix"),
    ]

    for hostname, expected_ordinal in test_cases:
        with patch.dict("os.environ", {"HOSTNAME": hostname}):
            registry = WorkerMetricsRegistry()
            assert registry.get_pod_ordinal() == expected_ordinal


@pytest.mark.asyncio
async def test_activity_duration_calculation(registry):
    """Test that activity duration is calculated correctly."""
    sync_job_id = uuid4()
    org_id = uuid4()

    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id,
        organization_id=org_id,
    ):
        # Wait a bit
        await asyncio.sleep(0.1)

        activities = await registry.get_active_activities()
        assert len(activities) == 1

        # Duration should be calculated
        duration = activities[0]["duration_seconds"]
        assert duration >= 0.1
        assert duration < 1.0  # Should be subsecond


@pytest.mark.asyncio
async def test_track_activity_with_worker_pool(registry):
    """Test tracking activity with associated worker pool (deprecated parameter)."""
    sync_job_id = uuid4()
    pool = MockAsyncWorkerPool(task_count=10)

    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job_id,
        worker_pool=pool,
    ):
        # Worker pool should be tracked
        total = await registry.get_total_active_and_pending_workers()
        assert total == 10

    # After context exits, pool should be removed
    total = await registry.get_total_active_and_pending_workers()
    assert total == 0


@pytest.mark.asyncio
async def test_no_deadlock_with_single_lock(registry):
    """Test that single async lock prevents deadlocks (commit 6b7cae789)."""
    # This test verifies that using a single asyncio.Lock instead of
    # separate locks for activities and pools prevents deadlock scenarios

    sync_id = uuid4()
    pool = MockAsyncWorkerPool(task_count=5)

    # Simulate concurrent operations that previously could deadlock
    async def concurrent_ops():
        async with registry.track_activity(
            activity_name="test_activity",
            sync_job_id=uuid4(),
            sync_id=sync_id,
        ):
            # These operations should not deadlock
            await registry.get_per_connector_metrics()
            await registry.get_total_active_and_pending_workers()
            await registry.get_per_sync_worker_counts()

    # Run multiple concurrent operations
    await asyncio.gather(*[concurrent_ops() for _ in range(10)])

    # Should complete without hanging
    activities = await registry.get_active_activities()
    assert len(activities) == 0


@pytest.mark.asyncio
async def test_connector_metrics_with_unknown_source_type(registry):
    """Test that activities without source_type are tracked as 'unknown'."""
    async with registry.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=uuid4(),
        sync_id=uuid4(),
        organization_id=uuid4(),
        metadata={},  # No source_type
    ):
        metrics = await registry.get_per_connector_metrics()

        # Should be tracked under 'unknown'
        assert "unknown" in metrics
        assert metrics["unknown"]["active_syncs"] == 1


@pytest.mark.asyncio
async def test_empty_registry_state(registry):
    """Test all methods handle empty registry state correctly."""
    # No activities, no pools
    assert await registry.get_active_activities() == []
    assert await registry.get_total_active_and_pending_workers() == 0
    assert await registry.get_per_sync_worker_counts() == []
    assert await registry.get_per_connector_metrics() == {}
    assert await registry.get_detailed_sync_metrics() == []

    summary = await registry.get_metrics_summary()
    assert summary["active_activities_count"] == 0
    assert summary["active_sync_jobs"] == []
    assert summary["active_activities"] == []
