"""Prometheus metrics for Temporal workers."""

from typing import Dict, Set

from prometheus_client import CollectorRegistry, Gauge, Info, ProcessCollector, generate_latest

# Create a custom registry for worker metrics
# (separate from any other Prometheus metrics in the system)
worker_registry = CollectorRegistry()

# Track previous connector labels per worker to detect finished syncs
# Format: {worker_id: set(connector_type)}
_previous_connector_labels: Dict[str, Set[str]] = {}

# Add process metrics (memory, CPU, file descriptors, etc.)
# This provides standard process-level metrics automatically
ProcessCollector(registry=worker_registry, namespace="airweave_worker")


# Info metric for static worker information
worker_info = Info(
    "airweave_worker",
    "Static information about this Temporal worker",
    registry=worker_registry,
)

# Gauge for worker uptime in seconds
worker_uptime_seconds = Gauge(
    "airweave_worker_uptime_seconds",
    "Worker uptime in seconds since start",
    ["worker_id"],
    registry=worker_registry,
)

# Gauge for worker status (0=stopped, 1=running, 2=draining)
worker_status = Gauge(
    "airweave_worker_status",
    "Worker status: 0=stopped, 1=running, 2=draining",
    ["worker_id"],
    registry=worker_registry,
)

# Gauge for number of active activities
worker_active_activities = Gauge(
    "airweave_worker_active_activities",
    "Number of activities currently executing",
    ["worker_id"],
    registry=worker_registry,
)

# Gauge for number of active sync jobs
worker_active_sync_jobs = Gauge(
    "airweave_worker_active_sync_jobs",
    "Number of unique sync jobs currently being processed",
    ["worker_id"],
    registry=worker_registry,
)

# Gauge for worker pool active and pending workers count
worker_pool_active_and_pending_workers = Gauge(
    "airweave_worker_pool_active_and_pending_workers",
    "Number of workers with active or pending tasks (includes waiting + executing)",
    ["worker_id"],
    registry=worker_registry,
)

worker_pool_active_and_pending_by_connector = Gauge(
    "airweave_worker_pool_active_and_pending_by_connector",
    "Number of active and pending workers by connector type (includes waiting + executing)",
    ["worker_id", "connector_type"],
    registry=worker_registry,
)

worker_active_syncs_by_connector = Gauge(
    "airweave_worker_active_syncs_by_connector",
    "Number of active syncs by connector type",
    ["worker_id", "connector_type"],
    registry=worker_registry,
)

# Config value gauges (from environment variables)
worker_sync_max_workers_config = Gauge(
    "airweave_worker_sync_max_workers_config",
    "Configured max async workers per sync (SYNC_MAX_WORKERS)",
    ["worker_id"],
    registry=worker_registry,
)

worker_thread_pool_size_config = Gauge(
    "airweave_worker_thread_pool_size_config",
    "Configured thread pool size per worker pod (SYNC_THREAD_POOL_SIZE)",
    ["worker_id"],
    registry=worker_registry,
)

# Active thread pool usage
worker_thread_pool_active = Gauge(
    "airweave_worker_thread_pool_active",
    "Number of threads currently executing in the shared thread pool",
    ["worker_id"],
    registry=worker_registry,
)


def update_worker_metrics(
    worker_id: str,
    status: str,
    uptime_seconds: float,
    active_activities_count: int,
    active_sync_jobs_count: int,
    task_queue: str,
    worker_pool_active_and_pending_count: int = 0,
    connector_metrics: Dict[str, Dict[str, int]] = None,
    sync_max_workers: int = 20,
    thread_pool_size: int = 100,
    thread_pool_active: int = 0,
) -> None:
    """Update all Prometheus worker metrics.

    Args:
        worker_id: Unique identifier for the worker (pod ordinal like '0', '1', '2')
        status: Worker status string ("running", "draining", "stopped")
        uptime_seconds: Worker uptime in seconds
        active_activities_count: Number of currently executing activities
        active_sync_jobs_count: Number of unique sync jobs being processed
        task_queue: Task queue name this worker is polling
        worker_pool_active_and_pending_count: Number of workers with tasks (active + pending)
        connector_metrics: Dict mapping connector_type to metrics (active_syncs, pending)
        sync_max_workers: Configured SYNC_MAX_WORKERS value
        thread_pool_size: Configured SYNC_THREAD_POOL_SIZE value
        thread_pool_active: Number of threads currently executing in the shared thread pool
    """
    # Update info metric (static data)
    worker_info.info(
        {
            "worker_id": worker_id,
            "task_queue": task_queue,
        }
    )

    # Map status string to numeric value
    status_value = {"stopped": 0, "running": 1, "draining": 2}.get(status, 0)

    # Update all gauges
    worker_uptime_seconds.labels(worker_id=worker_id).set(uptime_seconds)
    worker_status.labels(worker_id=worker_id).set(status_value)
    worker_active_activities.labels(worker_id=worker_id).set(active_activities_count)
    worker_active_sync_jobs.labels(worker_id=worker_id).set(active_sync_jobs_count)

    # Update worker pool active and pending workers count
    worker_pool_active_and_pending_workers.labels(worker_id=worker_id).set(
        worker_pool_active_and_pending_count
    )

    # Update connector-type aggregated metrics and zero out finished connectors
    current_connector_labels = set()

    if connector_metrics:
        for connector_type, metrics in connector_metrics.items():
            current_connector_labels.add(connector_type)

            worker_pool_active_and_pending_by_connector.labels(
                worker_id=worker_id,
                connector_type=connector_type,
            ).set(metrics.get("active_and_pending_workers", 0))

            worker_active_syncs_by_connector.labels(
                worker_id=worker_id,
                connector_type=connector_type,
            ).set(metrics.get("active_syncs", 0))

    # Zero out connectors that finished since last update
    # This prevents stale gauges from showing old values after syncs complete
    previous_labels = _previous_connector_labels.get(worker_id, set())
    finished_connectors = previous_labels - current_connector_labels

    for connector_type in finished_connectors:
        worker_pool_active_and_pending_by_connector.labels(
            worker_id=worker_id,
            connector_type=connector_type,
        ).set(0)

        worker_active_syncs_by_connector.labels(
            worker_id=worker_id,
            connector_type=connector_type,
        ).set(0)

    # Update tracking for next scrape
    _previous_connector_labels[worker_id] = current_connector_labels

    # Update config value gauges
    worker_sync_max_workers_config.labels(worker_id=worker_id).set(sync_max_workers)
    worker_thread_pool_size_config.labels(worker_id=worker_id).set(thread_pool_size)

    # Update thread pool active threads
    worker_thread_pool_active.labels(worker_id=worker_id).set(thread_pool_active)


def get_prometheus_metrics() -> bytes:
    """Generate Prometheus metrics in text format.

    Returns:
        Prometheus metrics in text format (bytes)
    """
    return generate_latest(worker_registry)
