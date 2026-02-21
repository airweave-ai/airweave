"""Temporal worker for Airweave.

Package structure:
    config.py         - WorkerConfig dataclass
    control_server.py - HTTP server for health/metrics/drain
    wiring.py         - Activity and workflow registration (DI wiring)
    __init__.py       - TemporalWorker class and main() entry point
"""

import asyncio
import signal
from datetime import timedelta
from typing import Any

from temporalio.worker import Worker

from airweave.core.config import settings
from airweave.core.logging import logger

from .config import WorkerConfig
from .control_server import WorkerControlServer, WorkerState
from .wiring import create_activities, get_workflows

__all__ = [
    "TemporalWorker",
    "WorkerConfig",
    "WorkerControlServer",
    "WorkerState",
    "main",
]


# =============================================================================
# Temporal Worker
# =============================================================================


class TemporalWorker:
    """Temporal worker lifecycle management.

    Responsibilities:
        - Start/stop the Temporal worker
        - Manage control server for health/metrics/drain
        - Handle graceful shutdown
    """

    def __init__(self, config: WorkerConfig) -> None:
        """Initialize the Temporal worker.

        Worker metrics are wired inline here rather than through the shared
        Container because they are worker-process-only concerns.  The API
        server has its own MetricsService facade; putting worker gauges in
        the Container would pollute its dependency graph with adapters that
        only make sense inside a Temporal worker OS process.
        """
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer, PrometheusWorkerMetrics
        from airweave.platform.temporal.worker_metrics import worker_metrics as metrics_registry

        self._config = config
        self._worker: Worker | None = None
        self._state = WorkerState()

        registry = CollectorRegistry()
        self._control_server = WorkerControlServer(
            worker_state=self._state,
            config=config,
            registry=metrics_registry,
            worker_metrics=PrometheusWorkerMetrics(registry=registry),
            renderer=PrometheusMetricsRenderer(registry=registry),
        )

    async def start(self) -> None:
        """Start the worker and control server."""
        # Start control server first (non-blocking)
        try:
            await self._control_server.start()
        except Exception as e:
            logger.warning(f"Failed to start control server (metrics unavailable): {e}")

        # Connect to Temporal
        from airweave.platform.temporal.client import temporal_client

        client = await temporal_client.get_client()
        logger.info(f"Starting Temporal worker on task queue: {self._config.task_queue}")

        # Create worker
        self._worker = Worker(
            client,
            task_queue=self._config.task_queue,
            workflows=get_workflows(),
            activities=create_activities(),
            workflow_runner=self._get_sandbox_runner(),
            max_concurrent_workflow_task_polls=self._config.max_concurrent_workflow_polls,
            max_concurrent_activity_task_polls=self._config.max_concurrent_activity_polls,
            sticky_queue_schedule_to_start_timeout=self._config.sticky_queue_schedule_to_start_timeout,
            nonsticky_to_sticky_poll_ratio=self._config.nonsticky_to_sticky_poll_ratio,
            default_heartbeat_throttle_interval=self._config.default_heartbeat_throttle_interval,
            max_heartbeat_throttle_interval=self._config.max_heartbeat_throttle_interval,
            graceful_shutdown_timeout=timedelta(
                seconds=self._config.graceful_shutdown_timeout_seconds
            ),
        )

        # Wire up drain callback
        self._state.on_drain_requested = self._on_drain

        # Start worker (blocks until shutdown)
        self._state.running = True
        logger.info(
            f"Worker started with graceful shutdown timeout: "
            f"{self._config.graceful_shutdown_timeout_seconds}s"
        )
        await self._worker.run()

    async def stop(self) -> None:
        """Stop the worker and control server."""
        if self._worker and self._state.running:
            logger.info("Stopping worker gracefully")
            self._state.running = False
            await self._worker.shutdown()

        await self._control_server.stop()

        # Close Temporal client
        from airweave.platform.temporal.client import temporal_client

        await temporal_client.close()

    async def _on_drain(self) -> None:
        """Called when drain is requested via control server."""
        try:
            logger.info("Calling worker.shutdown() - stops polling for new work")
            if self._worker:
                await self._worker.shutdown()
            logger.info("Worker shutdown complete - process will exit")
        except Exception as e:
            logger.error(f"Error during worker shutdown: {e}")

    def _get_sandbox_runner(self):
        """Get the appropriate sandbox configuration."""
        if self._config.disable_sandbox:
            from temporalio.worker import UnsandboxedWorkflowRunner

            logger.warning("TEMPORAL SANDBOX DISABLED - Use only for debugging!")
            return UnsandboxedWorkflowRunner()

        from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

        logger.info("Using default sandboxed workflow runner")
        return SandboxedWorkflowRunner()


# =============================================================================
# Entry Point
# =============================================================================


async def main() -> None:
    """Main entry point for the worker process."""
    # 1. Initialize DI container (fail fast if wiring is broken)
    from airweave.core import container as container_mod
    from airweave.core.container import initialize_container

    logger.info("Initializing dependency injection container...")
    initialize_container(settings)
    logger.info("Container initialized successfully")

    # 2. Initialize converters with OCR from the container
    from airweave.platform.converters import initialize_converters

    initialize_converters(ocr_provider=container_mod.container.ocr_provider)

    # 3. Create worker with config
    config = WorkerConfig.from_settings()
    worker = TemporalWorker(config)

    # 3. Set up signal handlers
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. Run worker
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
