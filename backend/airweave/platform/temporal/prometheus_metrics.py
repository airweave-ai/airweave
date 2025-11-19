"""Prometheus metrics for Temporal workers."""

from prometheus_client import CollectorRegistry, Gauge, Info, generate_latest

# Create a custom registry for worker metrics
# (separate from any other Prometheus metrics in the system)
worker_registry = CollectorRegistry()

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

# Gauge for worker capacity
worker_max_workflow_polls = Gauge(
    "airweave_worker_max_workflow_polls",
    "Maximum concurrent workflow polls",
    ["worker_id"],
    registry=worker_registry,
)

worker_max_activity_polls = Gauge(
    "airweave_worker_max_activity_polls",
    "Maximum concurrent activity polls",
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
    max_workflow_polls: int = 8,
    max_activity_polls: int = 16,
) -> None:
    """Update all Prometheus worker metrics.

    Args:
        worker_id: Unique identifier for the worker
        status: Worker status string ("running", "draining", "stopped")
        uptime_seconds: Worker uptime in seconds
        active_activities_count: Number of currently executing activities
        active_sync_jobs_count: Number of unique sync jobs being processed
        task_queue: Task queue name this worker is polling
        max_workflow_polls: Max concurrent workflow polls
        max_activity_polls: Max concurrent activity polls
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
    worker_max_workflow_polls.labels(worker_id=worker_id).set(max_workflow_polls)
    worker_max_activity_polls.labels(worker_id=worker_id).set(max_activity_polls)


def get_prometheus_metrics() -> bytes:
    """Generate Prometheus metrics in text format.

    Returns:
        Prometheus metrics in text format (bytes)
    """
    return generate_latest(worker_registry)
