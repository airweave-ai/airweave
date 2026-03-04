"""Worker configuration."""

from dataclasses import dataclass
from datetime import timedelta

from airweave.core.config import settings


@dataclass(frozen=True)
class WorkerConfig:
    """Worker configuration - all tunables in one place.

    Attributes:
        task_queue: Temporal task queue name
        metrics_port: Port for control server (health, metrics, drain)
        graceful_shutdown_timeout_seconds: How long to wait for activities to complete

        max_concurrent_workflow_polls: Max concurrent workflow task polls
        max_concurrent_activity_polls: Max concurrent activity task polls

        sticky_queue_schedule_to_start_timeout: Sticky queue optimization
        nonsticky_to_sticky_poll_ratio: Ratio for sticky queue polling

        default_heartbeat_throttle_interval: How often to send heartbeats
        max_heartbeat_throttle_interval: Max heartbeat interval

        disable_sandbox: Disable Temporal sandbox (debugging only)
    """

    task_queue: str
    metrics_port: int
    graceful_shutdown_timeout_seconds: int

    # Polling concurrency
    max_concurrent_workflow_polls: int = 8
    max_concurrent_activity_polls: int = 16

    # Sticky queue optimization
    sticky_queue_schedule_to_start_timeout: timedelta = timedelta(seconds=0.5)
    nonsticky_to_sticky_poll_ratio: float = 0.5

    # Heartbeat settings (affects cancel delivery speed)
    default_heartbeat_throttle_interval: timedelta = timedelta(seconds=2)
    max_heartbeat_throttle_interval: timedelta = timedelta(seconds=2)

    # Sandbox (disable only for debugging)
    disable_sandbox: bool = False

    # Temporal SDK built-in Prometheus exporter
    sdk_metrics_port: int = 9090

    @classmethod
    def from_settings(cls) -> "WorkerConfig":
        """Build config from environment settings."""
        return cls(
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            metrics_port=settings.WORKER_METRICS_PORT,
            graceful_shutdown_timeout_seconds=settings.TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT,
            disable_sandbox=settings.TEMPORAL_DISABLE_SANDBOX,
            sdk_metrics_port=settings.TEMPORAL_SDK_METRICS_PORT,
        )
