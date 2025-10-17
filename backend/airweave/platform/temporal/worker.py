"""Temporal worker for Airweave."""

import asyncio
import signal
from datetime import timedelta
from typing import Any

from temporalio.worker import Worker

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.entities._base import ensure_file_entity_models
from airweave.platform.temporal.activities import (
    cleanup_stuck_sync_jobs_activity,
    create_sync_job_activity,
    mark_sync_job_cancelled_activity,
    run_sync_activity,
)
from airweave.platform.temporal.cleanup import self_destruct_orphaned_sync_activity
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.workflows import (
    CleanupStuckSyncJobsWorkflow,
    RunSourceConnectionWorkflow,
)


class TemporalWorker:
    """Temporal worker for processing workflows and activities."""

    def __init__(self) -> None:
        """Initialize the Temporal worker."""
        self.worker: Worker | None = None
        self.running = False

    async def start(self) -> None:
        """Start the Temporal worker."""
        try:
            # Ensure all FileEntity subclasses have their parent and chunk models created
            ensure_file_entity_models()

            client = await temporal_client.get_client()
            task_queue = settings.TEMPORAL_TASK_QUEUE
            logger.info(f"Starting Temporal worker on task queue: {task_queue}")

            # Get the appropriate sandbox configuration
            sandbox_config = self._get_sandbox_config()

            self.worker = Worker(
                client,
                task_queue=task_queue,
                workflows=[RunSourceConnectionWorkflow, CleanupStuckSyncJobsWorkflow],
                activities=[
                    run_sync_activity,
                    mark_sync_job_cancelled_activity,
                    create_sync_job_activity,
                    cleanup_stuck_sync_jobs_activity,
                    self_destruct_orphaned_sync_activity,
                ],
                workflow_runner=sandbox_config,
                max_concurrent_workflow_task_polls=8,
                max_concurrent_activity_task_polls=16,
                sticky_queue_schedule_to_start_timeout=timedelta(seconds=0.5),
                nonsticky_to_sticky_poll_ratio=0.5,
                # Speed up cancel delivery by flushing heartbeats frequently
                default_heartbeat_throttle_interval=timedelta(seconds=2),
                max_heartbeat_throttle_interval=timedelta(seconds=2),
            )

            self.running = True
            await self.worker.run()

        except Exception as e:
            logger.error(f"Error starting Temporal worker: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Temporal worker."""
        if self.worker and self.running:
            logger.info("Stopping Temporal worker...")
            self.running = False
            await self.worker.shutdown()

        # Always close temporal client to prevent resource leaks
        await temporal_client.close()

    def _get_sandbox_config(self):
        """Determine the appropriate sandbox configuration."""
        should_disable = settings.TEMPORAL_DISABLE_SANDBOX

        if should_disable:
            from temporalio.worker import UnsandboxedWorkflowRunner

            logger.warning("⚠️  TEMPORAL SANDBOX DISABLED - Use only for debugging!")
            return UnsandboxedWorkflowRunner()

        # Default production sandbox
        from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

        logger.info("Using default sandboxed workflow runner")
        return SandboxedWorkflowRunner()


async def main() -> None:
    """Main function to run the worker."""
    worker = TemporalWorker()

    # Handle shutdown signals
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
