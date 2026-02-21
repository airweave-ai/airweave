"""HTTP control server for worker health, metrics, and drain.

Endpoints:
    GET  /health  - Liveness/readiness probe
    GET  /metrics - Prometheus metrics
    GET  /status  - JSON debug status
    POST /drain   - Initiate graceful shutdown

Security Notes:
    - Local dev: Access via kubectl port-forward
    - Kubernetes: Internal ClusterIP service only
    - Exposes operational metadata (job IDs, org IDs) but no user data
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from aiohttp import web

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.core.protocols import (
    MetricsRenderer,
    WorkerMetrics,
    WorkerMetricsRegistryProtocol,
)
from airweave.platform.sync.async_helpers import get_active_thread_count
from airweave.platform.temporal.worker_metrics_snapshot import (
    ConnectorSnapshot,
    WorkerMetricsSnapshot,
)

from .config import WorkerConfig

# =============================================================================
# Worker State
# =============================================================================


@dataclass
class WorkerState:
    """Mutable worker state shared between components."""

    running: bool = False
    draining: bool = False
    on_drain_requested: Callable[[], Coroutine[Any, Any, None]] | None = field(default=None)


# =============================================================================
# Control Server
# =============================================================================


class WorkerControlServer:
    """HTTP server for worker health, metrics, and drain control."""

    def __init__(
        self,
        worker_state: WorkerState,
        config: WorkerConfig,
        registry: WorkerMetricsRegistryProtocol,
        worker_metrics: WorkerMetrics,
        renderer: MetricsRenderer,
    ) -> None:
        """Initialize the control server."""
        self._state = worker_state
        self._config = config
        self._registry = registry
        self._worker_metrics = worker_metrics
        self._renderer = renderer
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Start the control server."""
        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/status", self._handle_status)
        app.router.add_post("/drain", self._handle_drain)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._config.metrics_port)
        await site.start()

        logger.info(
            f"Control server started on 0.0.0.0:{self._config.metrics_port} "
            f"(endpoints: /health, /metrics, /status, /drain)"
        )

    async def stop(self) -> None:
        """Stop the control server."""
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception as e:
                logger.warning(f"Control server cleanup error: {e}")

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check for k8s probes."""
        if not self._state.running:
            return web.Response(text="NOT_RUNNING", status=503)
        if self._state.draining:
            return web.Response(text="DRAINING", status=503)
        return web.Response(text="OK", status=200)

    async def _handle_drain(self, request: web.Request) -> web.Response:
        """Handle drain request from PreStop hook."""
        logger.warning("DRAIN: Initiating graceful worker shutdown")
        self._state.draining = True

        if self._state.on_drain_requested:
            asyncio.create_task(self._state.on_drain_requested())

        return web.Response(text="Drain initiated")

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Metrics endpoint."""
        try:
            metrics_data = await self._collect_prometheus_metrics()
            return web.Response(
                body=metrics_data,
                content_type=self._renderer.content_type,
            )
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}", exc_info=True)
            return web.Response(text=f"Error: {str(e)}", status=500)

    async def _handle_status(self, request: web.Request) -> web.Response:
        """JSON status endpoint for debugging."""
        try:
            status_data = await self._collect_json_status()
            return web.json_response(status_data)
        except Exception as e:
            logger.error(f"Error generating JSON status: {e}", exc_info=True)
            return web.json_response(
                {"error": "Failed to generate status", "detail": str(e)}, status=500
            )

    # -------------------------------------------------------------------------
    # Metrics Collection
    # -------------------------------------------------------------------------

    async def _collect_prometheus_metrics(self) -> bytes:
        """Collect and format Prometheus metrics."""
        summary = await self._registry.get_metrics_summary()
        connector_metrics = await self._registry.get_per_connector_metrics()
        worker_pool_count = await self._registry.get_total_active_and_pending_workers()
        thread_pool_active = get_active_thread_count()

        snapshot = WorkerMetricsSnapshot(
            worker_id=self._registry.get_pod_ordinal(),
            status=self._get_status_string(),
            uptime_seconds=summary["uptime_seconds"],
            active_activities_count=summary["active_activities_count"],
            active_sync_jobs_count=len(summary["active_sync_jobs"]),
            task_queue=self._config.task_queue,
            worker_pool_active_and_pending_count=worker_pool_count,
            connector_metrics={
                ct: ConnectorSnapshot(
                    active_syncs=m.get("active_syncs", 0),
                    active_and_pending_workers=m.get("active_and_pending_workers", 0),
                )
                for ct, m in connector_metrics.items()
            },
            sync_max_workers=settings.SYNC_MAX_WORKERS,
            thread_pool_size=settings.SYNC_THREAD_POOL_SIZE,
            thread_pool_active=thread_pool_active,
        )

        self._worker_metrics.update(snapshot)
        return self._renderer.generate()

    async def _collect_json_status(self) -> dict[str, Any]:
        """Collect detailed JSON status for debugging."""
        metrics = await self._registry.get_metrics_summary()
        detailed_syncs = await self._registry.get_detailed_sync_metrics()
        per_sync_workers = await self._registry.get_per_sync_worker_counts()
        active_and_pending = await self._registry.get_total_active_and_pending_workers()
        thread_pool_active = get_active_thread_count()

        # Merge worker counts into detailed_syncs
        worker_counts_map = {
            s["sync_id"]: s["active_and_pending_worker_count"] for s in per_sync_workers
        }
        for sync in detailed_syncs:
            sync["workers_allocated"] = worker_counts_map.get(sync["sync_id"], 0)
            sync["duration_seconds"] = 0
            for activity in metrics["active_activities"]:
                if activity.get("sync_job_id") == sync["sync_job_id"]:
                    sync["duration_seconds"] = activity.get("duration_seconds", 0)
                    break

        # Process metrics (CPU, memory)
        cpu_percent, memory_mb = self._get_process_metrics()

        return {
            "worker_id": metrics["worker_id"],
            "status": self._get_status_string(),
            "uptime_seconds": metrics["uptime_seconds"],
            "task_queue": self._config.task_queue,
            "capacity": {
                "max_workflow_polls": self._config.max_concurrent_workflow_polls,
                "max_activity_polls": self._config.max_concurrent_activity_polls,
            },
            "active_activities_count": metrics["active_activities_count"],
            "active_syncs": detailed_syncs,
            "metrics": {
                "total_workers": settings.SYNC_MAX_WORKERS,
                "active_and_pending_workers": active_and_pending,
                "total_threads": settings.SYNC_THREAD_POOL_SIZE,
                "active_threads": thread_pool_active,
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
            },
        }

    def _get_status_string(self) -> str:
        """Get worker status as string."""
        if self._state.draining:
            return "draining"
        elif not self._state.running:
            return "stopped"
        return "running"

    def _get_process_metrics(self) -> tuple[float, int]:
        """Get CPU and memory usage."""
        try:
            import psutil

            process = psutil.Process()
            cpu_percent = round(process.cpu_percent(interval=0.1), 1)
            memory_mb = int(process.memory_info().rss / 1024 / 1024)
            return cpu_percent, memory_mb
        except ImportError:
            return 0.0, 0
