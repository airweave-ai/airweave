"""Temporal worker for Airweave."""

import asyncio
import signal
from datetime import timedelta
from typing import Any

from aiohttp import web
from temporalio.worker import Worker

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.prometheus_metrics import (
    get_prometheus_metrics,
)
from airweave.platform.temporal.prometheus_metrics import (
    update_worker_metrics as update_prometheus_metrics,
)
from airweave.platform.temporal.worker_metrics import worker_metrics


class TemporalWorker:
    """Temporal worker for processing workflows and activities."""

    def __init__(self) -> None:
        """Initialize the Temporal worker."""
        self.worker: Worker | None = None
        self.running = False
        self.draining = False
        self.metrics_server = None

    async def start(self) -> None:
        """Start the Temporal worker."""
        try:
            # Start control server for /drain endpoint and metrics (non-blocking)
            try:
                await self._start_control_server()
            except Exception as e:
                logger.warning(f"Failed to start control server (metrics unavailable): {e}")

            client = await temporal_client.get_client()
            task_queue = settings.TEMPORAL_TASK_QUEUE
            logger.info(f"Starting Temporal worker on task queue: {task_queue}")

            # Get the appropriate sandbox configuration
            sandbox_config = self._get_sandbox_config()

            # Import workflows and activities from reorganized modules
            from airweave.platform.temporal.activities import (
                check_and_notify_expiring_keys_activity,
                cleanup_stuck_sync_jobs_activity,
                create_sync_job_activity,
                mark_sync_job_cancelled_activity,
                run_sync_activity,
                self_destruct_orphaned_sync_activity,
            )
            from airweave.platform.temporal.workflows import (
                APIKeyExpirationCheckWorkflow,
                CleanupStuckSyncJobsWorkflow,
                RunSourceConnectionWorkflow,
            )

            self.worker = Worker(
                client,
                task_queue=task_queue,
                workflows=[
                    RunSourceConnectionWorkflow,
                    CleanupStuckSyncJobsWorkflow,
                    APIKeyExpirationCheckWorkflow,
                ],
                activities=[
                    run_sync_activity,
                    mark_sync_job_cancelled_activity,
                    create_sync_job_activity,
                    cleanup_stuck_sync_jobs_activity,
                    self_destruct_orphaned_sync_activity,
                    check_and_notify_expiring_keys_activity,
                ],
                workflow_runner=sandbox_config,
                max_concurrent_workflow_task_polls=8,
                max_concurrent_activity_task_polls=16,
                sticky_queue_schedule_to_start_timeout=timedelta(seconds=0.5),
                nonsticky_to_sticky_poll_ratio=0.5,
                # Speed up cancel delivery by flushing heartbeats frequently
                default_heartbeat_throttle_interval=timedelta(seconds=2),
                max_heartbeat_throttle_interval=timedelta(seconds=2),
                # Configure graceful shutdown
                graceful_shutdown_timeout=timedelta(
                    seconds=settings.TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT
                ),
            )

            self.running = True
            logger.info(
                f"Worker started with graceful shutdown timeout: "
                f"{settings.TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT}s"
            )
            await self.worker.run()

        except Exception as e:
            logger.error(f"Error starting Temporal worker: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Temporal worker."""
        if self.worker and self.running:
            logger.info("Stopping worker gracefully")
            self.running = False
            await self.worker.shutdown()

        # Cleanup metrics server (continue shutdown even if this fails)
        if self.metrics_server:
            try:
                await self.metrics_server.cleanup()
            except (AttributeError, Exception) as e:
                logger.warning(f"Metrics server cleanup skipped: {e}")

        # Always close temporal client to prevent resource leaks
        await temporal_client.close()

    async def _start_control_server(self):
        """Start HTTP server for drain control and metrics.

        Security Notes:
        - In local development: Access via kubectl port-forward
        - In Kubernetes: Internal ClusterIP service only
        - Exposes operational metadata (job IDs, org IDs) but no user data
        """
        app = web.Application()
        app.router.add_post("/drain", self._handle_drain)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_prometheus_metrics)
        app.router.add_get("/status", self._handle_json_status)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", settings.WORKER_METRICS_PORT)
        await site.start()
        self.metrics_server = runner
        logger.info(
            f"Control server started on 0.0.0.0:{settings.WORKER_METRICS_PORT} "
            f"(endpoints: /health, /metrics, /status, /drain)"
        )

    async def _handle_drain(self, request):
        """Handle drain request from PreStop hook.

        Initiates graceful shutdown which:
        1. Stops polling the task queue for new activities
        2. Allows current activities to complete
        3. Worker process exits when all activities are done
        """
        logger.warning("🚨 DRAIN: Initiating graceful worker shutdown")

        # Mark as draining
        self.draining = True

        # Tell Temporal SDK to stop polling for new activities
        if self.worker:
            asyncio.create_task(self._shutdown_worker())

        return web.Response(text="Drain initiated")

    async def _shutdown_worker(self):
        """Shutdown worker to stop polling."""
        try:
            logger.info("Calling worker.shutdown() - stops polling for new work")
            if self.worker:
                await self.worker.shutdown()
            logger.info("Worker shutdown complete - activities finished, process will exit")
        except Exception as e:
            logger.error(f"Error during worker shutdown: {e}")

    async def _handle_health(self, request):
        """Health check endpoint.

        Returns:
            200 OK: Worker is running and accepting work
            503 Service Unavailable: Worker is not running or draining
        """
        if not self.running:
            return web.Response(text="NOT_RUNNING", status=503)
        if self.draining:
            return web.Response(text="DRAINING", status=503)
        return web.Response(text="OK", status=200)

    async def _handle_prometheus_metrics(self, request):
        """Prometheus metrics endpoint.

        Returns Prometheus-formatted metrics that can be scraped by Prometheus.
        Exposes worker status, uptime, active activities, and capacity metrics.
        """
        try:
            # Get current metrics from the registry
            metrics = await worker_metrics.get_metrics_summary()

            # Determine worker status
            status = "running"
            if self.draining:
                status = "draining"
            elif not self.running:
                status = "stopped"

            # Get connector-aggregated metrics (low cardinality)
            connector_metrics = await worker_metrics.get_per_connector_metrics()
            worker_pool_active_and_pending_count = (
                await worker_metrics.get_total_active_and_pending_workers()
            )

            # Get thread pool metrics
            from airweave.platform.sync.async_helpers import get_active_thread_count

            thread_pool_active = get_active_thread_count()

            # Update Prometheus metrics with low-cardinality data
            update_prometheus_metrics(
                worker_id=worker_metrics.get_pod_ordinal(),  # Use ordinal (0, 1, 2)
                status=status,
                uptime_seconds=metrics["uptime_seconds"],
                active_activities_count=metrics["active_activities_count"],
                active_sync_jobs_count=len(metrics["active_sync_jobs"]),
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                worker_pool_active_and_pending_count=worker_pool_active_and_pending_count,
                connector_metrics=connector_metrics,  # Connector-type aggregated data
                sync_max_workers=settings.SYNC_MAX_WORKERS,
                thread_pool_size=settings.SYNC_THREAD_POOL_SIZE,
                thread_pool_active=thread_pool_active,
            )

            # Generate and return Prometheus metrics
            prometheus_data = get_prometheus_metrics()
            return web.Response(
                body=prometheus_data,
                content_type="text/plain; version=0.0.4",
                charset="utf-8",
            )

        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}", exc_info=True)
            return web.Response(text=f"Error: {str(e)}", status=500)

    async def _handle_json_status(self, request):
        """JSON status endpoint for debugging and monitoring.

        Returns JSON with detailed worker information including per-sync details,
        resource metrics (CPU, memory), and worker pool utilization.
        """
        try:
            # Get metrics from the global registry
            metrics = await worker_metrics.get_metrics_summary()

            # Determine status
            status = "running"
            if self.draining:
                status = "draining"
            elif not self.running:
                status = "stopped"

            # Get detailed sync info with org names, connectors, worker counts
            detailed_syncs = await worker_metrics.get_detailed_sync_metrics()
            per_sync_workers = await worker_metrics.get_per_sync_worker_counts()

            # Merge worker counts into detailed_syncs
            worker_counts_map = {
                s["sync_id"]: s["active_and_pending_worker_count"] for s in per_sync_workers
            }

            for sync in detailed_syncs:
                sync["workers_allocated"] = worker_counts_map.get(sync["sync_id"], 0)
                # Add duration if available from activities
                for activity in metrics["active_activities"]:
                    if activity.get("sync_id") == sync["sync_id"]:
                        sync["duration_seconds"] = activity.get("duration_seconds", 0)
                        break
                else:
                    sync["duration_seconds"] = 0

            # Get thread pool metrics
            from airweave.platform.sync.async_helpers import get_active_thread_count

            thread_pool_active = get_active_thread_count()

            # Get process metrics using psutil
            try:
                import psutil

                process = psutil.Process()
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_info = process.memory_info()
                memory_mb = round(memory_info.rss / 1024 / 1024, 0)
            except ImportError:
                # Fallback if psutil not available
                cpu_percent = 0.0
                memory_mb = 0

            active_and_pending_workers = await worker_metrics.get_total_active_and_pending_workers()

            response_data = {
                "worker_id": metrics["worker_id"],
                "status": status,
                "uptime_seconds": metrics["uptime_seconds"],
                "task_queue": settings.TEMPORAL_TASK_QUEUE,
                "capacity": {
                    "max_workflow_polls": 8,
                    "max_activity_polls": 16,
                },
                "active_activities_count": metrics["active_activities_count"],
                "active_syncs": detailed_syncs,  # NEW: detailed sync info with org, connector
                "metrics": {  # NEW: resource metrics
                    "total_workers": settings.SYNC_MAX_WORKERS,
                    "active_and_pending_workers": active_and_pending_workers,
                    "total_threads": settings.SYNC_THREAD_POOL_SIZE,
                    "active_threads": thread_pool_active,
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_mb": int(memory_mb),
                },
            }

            return web.json_response(response_data)

        except Exception as e:
            logger.error(f"Error generating JSON status: {e}", exc_info=True)
            return web.json_response(
                {"error": "Failed to generate status", "detail": str(e)}, status=500
            )

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
