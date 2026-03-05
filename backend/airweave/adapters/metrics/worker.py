"""Worker metrics adapters (Prometheus + Fake).

Prometheus implementation owns all 11 gauges, the Info metric, and the
ProcessCollector for Temporal worker instrumentation.
"""

from prometheus_client import CollectorRegistry, Gauge, Info, ProcessCollector

from airweave.core.protocols.metrics import WorkerMetrics
from airweave.platform.temporal.worker_metrics_snapshot import WorkerMetricsSnapshot


class PrometheusWorkerMetrics(WorkerMetrics):
    """Prometheus-backed Temporal worker metrics."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._registry = registry
        self._previous_connector_labels: dict[str, set[str]] = {}

        # Process metrics (memory, CPU, file descriptors)
        ProcessCollector(registry=registry, namespace="airweave_worker")

        # Static worker information
        self._worker_info = Info(
            "airweave_worker",
            "Static information about this Temporal worker",
            registry=registry,
        )

        # Worker uptime
        self._uptime_seconds = Gauge(
            "airweave_worker_uptime_seconds",
            "Worker uptime in seconds since start",
            ["worker_id"],
            registry=registry,
        )

        # Worker status (0=stopped, 1=running, 2=draining)
        self._status = Gauge(
            "airweave_worker_status",
            "Worker status: 0=stopped, 1=running, 2=draining",
            ["worker_id"],
            registry=registry,
        )

        # Active activities
        self._active_activities = Gauge(
            "airweave_worker_active_activities",
            "Number of activities currently executing",
            ["worker_id"],
            registry=registry,
        )

        # Active sync jobs
        self._active_sync_jobs = Gauge(
            "airweave_worker_active_sync_jobs",
            "Number of unique sync jobs currently being processed",
            ["worker_id"],
            registry=registry,
        )

        # Worker pool active+pending total
        self._pool_active_and_pending = Gauge(
            "airweave_worker_pool_active_and_pending_workers",
            "Number of workers with active or pending tasks (includes waiting + executing)",
            ["worker_id"],
            registry=registry,
        )

        # Per-connector active+pending
        self._pool_active_and_pending_by_connector = Gauge(
            "airweave_worker_pool_active_and_pending_by_connector",
            "Number of active and pending workers by connector type (includes waiting + executing)",
            ["worker_id", "connector_type"],
            registry=registry,
        )

        # Per-connector active syncs
        self._active_syncs_by_connector = Gauge(
            "airweave_worker_active_syncs_by_connector",
            "Number of active syncs by connector type",
            ["worker_id", "connector_type"],
            registry=registry,
        )

        # Config value gauges
        self._sync_max_workers_config = Gauge(
            "airweave_worker_sync_max_workers_config",
            "Configured max async workers per sync (SYNC_MAX_WORKERS)",
            ["worker_id"],
            registry=registry,
        )

        self._thread_pool_size_config = Gauge(
            "airweave_worker_thread_pool_size_config",
            "Configured thread pool size per worker pod (SYNC_THREAD_POOL_SIZE)",
            ["worker_id"],
            registry=registry,
        )

        # Thread pool active count
        self._thread_pool_active = Gauge(
            "airweave_worker_thread_pool_active",
            "Number of threads currently executing in the shared thread pool",
            ["worker_id"],
            registry=registry,
        )

    # -- WorkerMetrics protocol method --

    def update(self, snapshot: WorkerMetricsSnapshot) -> None:
        wid = snapshot.worker_id

        # Static info
        self._worker_info.info(
            {
                "worker_id": wid,
                "task_queue": snapshot.task_queue,
            }
        )

        # Status mapping
        status_value = {"stopped": 0, "running": 1, "draining": 2}.get(snapshot.status, 0)

        # Scalar gauges
        self._uptime_seconds.labels(worker_id=wid).set(snapshot.uptime_seconds)
        self._status.labels(worker_id=wid).set(status_value)
        self._active_activities.labels(worker_id=wid).set(snapshot.active_activities_count)
        self._active_sync_jobs.labels(worker_id=wid).set(snapshot.active_sync_jobs_count)
        self._pool_active_and_pending.labels(worker_id=wid).set(
            snapshot.worker_pool_active_and_pending_count
        )

        # Per-connector gauges
        current_connector_labels: set[str] = set()

        for connector_type, cs in snapshot.connector_metrics.items():
            current_connector_labels.add(connector_type)

            self._pool_active_and_pending_by_connector.labels(
                worker_id=wid, connector_type=connector_type
            ).set(cs.active_and_pending_workers)

            self._active_syncs_by_connector.labels(
                worker_id=wid, connector_type=connector_type
            ).set(cs.active_syncs)

        # Zero out connectors that finished since last scrape
        previous = self._previous_connector_labels.get(wid, set())
        for connector_type in previous - current_connector_labels:
            self._pool_active_and_pending_by_connector.labels(
                worker_id=wid, connector_type=connector_type
            ).set(0)
            self._active_syncs_by_connector.labels(
                worker_id=wid, connector_type=connector_type
            ).set(0)

        self._previous_connector_labels[wid] = current_connector_labels

        # Config gauges
        self._sync_max_workers_config.labels(worker_id=wid).set(snapshot.sync_max_workers)
        self._thread_pool_size_config.labels(worker_id=wid).set(snapshot.thread_pool_size)

        # Thread pool active
        self._thread_pool_active.labels(worker_id=wid).set(snapshot.thread_pool_active)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------


class FakeWorkerMetrics(WorkerMetrics):
    """In-memory spy implementing the WorkerMetrics protocol."""

    def __init__(self) -> None:
        self.snapshots: list[WorkerMetricsSnapshot] = []

    def update(self, snapshot: WorkerMetricsSnapshot) -> None:
        self.snapshots.append(snapshot)

    # -- test helpers --

    @property
    def last_snapshot(self) -> WorkerMetricsSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    def clear(self) -> None:
        self.snapshots.clear()
