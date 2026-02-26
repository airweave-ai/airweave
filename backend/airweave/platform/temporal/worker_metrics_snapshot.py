"""Snapshot dataclasses for worker metrics.

Frozen value objects that capture worker state at a single point in time,
replacing the 11-parameter function signature of the old
``update_worker_metrics()`` call.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConnectorSnapshot:
    """Per-connector-type metrics at scrape time."""

    active_syncs: int
    active_and_pending_workers: int


@dataclass(frozen=True)
class WorkerMetricsSnapshot:
    """Complete worker metrics snapshot passed to the gauge adapter."""

    worker_id: str
    status: str
    uptime_seconds: float
    active_activities_count: int
    active_sync_jobs_count: int
    task_queue: str
    worker_pool_active_and_pending_count: int = 0
    connector_metrics: dict[str, ConnectorSnapshot] = field(default_factory=dict)
    sync_max_workers: int = 20
    thread_pool_size: int = 100
    thread_pool_active: int = 0
