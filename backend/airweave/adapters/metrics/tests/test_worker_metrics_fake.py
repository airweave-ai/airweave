"""Tests for FakeWorkerMetrics adapter."""

from airweave.adapters.metrics import FakeWorkerMetrics
from airweave.platform.temporal.worker_metrics_snapshot import (
    ConnectorSnapshot,
    WorkerMetricsSnapshot,
)


def _make_snapshot(**overrides) -> WorkerMetricsSnapshot:
    defaults = dict(
        worker_id="0",
        status="running",
        uptime_seconds=100.0,
        active_activities_count=3,
        active_sync_jobs_count=2,
        task_queue="test-queue",
    )
    defaults.update(overrides)
    return WorkerMetricsSnapshot(**defaults)


def test_records_snapshots():
    fake = FakeWorkerMetrics()
    snap = _make_snapshot()
    fake.update(snap)

    assert len(fake.snapshots) == 1
    assert fake.last_snapshot is snap


def test_last_snapshot_none_when_empty():
    fake = FakeWorkerMetrics()
    assert fake.last_snapshot is None


def test_clear_resets_state():
    fake = FakeWorkerMetrics()
    fake.update(_make_snapshot())
    fake.update(_make_snapshot(status="draining"))
    assert len(fake.snapshots) == 2

    fake.clear()
    assert len(fake.snapshots) == 0
    assert fake.last_snapshot is None


def test_snapshot_fields_accessible():
    fake = FakeWorkerMetrics()
    snap = _make_snapshot(
        connector_metrics={
            "slack": ConnectorSnapshot(active_syncs=2, active_and_pending_workers=15),
        },
        thread_pool_active=42,
    )
    fake.update(snap)

    last = fake.last_snapshot
    assert last.worker_id == "0"
    assert last.connector_metrics["slack"].active_syncs == 2
    assert last.thread_pool_active == 42
