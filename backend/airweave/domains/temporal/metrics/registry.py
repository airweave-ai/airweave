"""Worker metrics registry for Temporal workers.

Provides a global registry for tracking active activities and metrics
about the worker's current workload.
"""

import asyncio
import os
import re
import socket
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Set, runtime_checkable
from uuid import UUID

from airweave.core.logging import logger as _logger
from airweave.core.protocols.worker_metrics_registry import SyncMetricDetail, SyncWorkerCount


@runtime_checkable
class WorkerPoolProtocol(Protocol):
    """Structural protocol for worker pools tracked by WorkerMetricsRegistry.

    AsyncWorkerPool (sync_pipeline) satisfies this implicitly.
    """

    @property
    def active_and_pending_count(self) -> int:
        """Number of workers with tasks active or queued."""
        ...


class WorkerMetricsRegistry:
    """Global registry for tracking active activities in this worker process."""

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        self._active_activities: Dict[str, Dict[str, Any]] = {}
        self._worker_pools: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._worker_start_time = datetime.now(timezone.utc)
        self._worker_id = self._generate_worker_id()

    def _generate_worker_id(self) -> str:
        """Generate a unique identifier for this worker.

        Uses Kubernetes pod name if available, otherwise hostname.
        """
        pod_name = os.environ.get("HOSTNAME")
        if pod_name and pod_name.startswith("airweave-worker"):
            return pod_name

        try:
            hostname = socket.gethostname()
            return hostname
        except Exception:
            return "unknown-worker"

    def get_pod_ordinal(self) -> str:
        """Extract pod ordinal from HOSTNAME for low-cardinality metrics.

        Examples:
            airweave-worker-0 -> '0'
            airweave-worker-12 -> '12'
            random-hostname -> 'unknown'

        Returns:
            Pod ordinal as string, or 'unknown' if not in expected format
        """
        hostname = os.environ.get("HOSTNAME", "unknown")
        if match := re.search(r"-(\d+)$", hostname):
            return match.group(1)
        return hostname

    @property
    def worker_id(self) -> str:
        """Get the unique worker ID."""
        return self._worker_id

    @property
    def uptime_seconds(self) -> float:
        """Get worker uptime in seconds."""
        return (datetime.now(timezone.utc) - self._worker_start_time).total_seconds()

    @asynccontextmanager
    async def track_activity(
        self,
        activity_name: str,
        sync_job_id: Optional[UUID] = None,
        sync_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        worker_pool: Optional[Any] = None,
    ):
        """Context manager to track an active activity."""
        activity_id = f"{activity_name}-{sync_job_id or 'unknown'}"
        start_time = datetime.now(timezone.utc)

        async with self._lock:
            self._active_activities[activity_id] = {
                "activity_name": activity_name,
                "sync_job_id": str(sync_job_id) if sync_job_id else None,
                "sync_id": str(sync_id) if sync_id else None,
                "organization_id": str(organization_id) if organization_id else None,
                "start_time": start_time.isoformat(),
                "metadata": metadata or {},
            }

            if worker_pool is not None:
                self._worker_pools[activity_id] = worker_pool

        try:
            yield
        finally:
            async with self._lock:
                self._active_activities.pop(activity_id, None)
                self._worker_pools.pop(activity_id, None)

    async def get_active_activities(self) -> List[Dict[str, Any]]:
        """Get list of currently active activities with duration info."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            activities = []

            for _activity_id, info in self._active_activities.items():
                start_time = datetime.fromisoformat(info["start_time"])
                duration = (now - start_time).total_seconds()

                activities.append(
                    {
                        "activity_name": info["activity_name"],
                        "sync_job_id": info["sync_job_id"],
                        "organization_id": info["organization_id"],
                        "start_time": info["start_time"],
                        "duration_seconds": round(duration, 2),
                        "metadata": info["metadata"],
                    }
                )

            return activities

    async def get_active_sync_job_ids(self) -> Set[str]:
        """Get set of sync job IDs currently being processed."""
        async with self._lock:
            return {
                info["sync_job_id"]
                for info in self._active_activities.values()
                if info["sync_job_id"]
            }

    async def get_detailed_sync_metrics(self) -> list[SyncMetricDetail]:
        """Get detailed metrics for each active sync."""
        async with self._lock:
            sync_metrics = []

            for info in self._active_activities.values():
                if info.get("sync_job_id"):
                    metadata = info.get("metadata", {})
                    sync_metrics.append(
                        {
                            "sync_id": info.get("sync_id", "unknown"),
                            "sync_job_id": info.get("sync_job_id", "unknown"),
                            "org_name": metadata.get("org_name", "unknown"),
                            "source_type": metadata.get("source_type", "unknown"),
                        }
                    )

            return sync_metrics

    async def get_total_active_and_pending_workers(self) -> int:
        """Get total active + pending workers across all tracked pools."""
        async with self._lock:
            total = 0
            for pool in self._worker_pools.values():
                if pool is not None and isinstance(pool, WorkerPoolProtocol):
                    total += pool.active_and_pending_count
            return total

    async def get_per_sync_worker_counts(self) -> list[SyncWorkerCount]:
        """Get worker count for each active sync.

        Aggregates by sync_id to reduce metric cardinality.
        """
        async with self._lock:
            results_by_sync: Dict[str, int] = {}

            for pool_id, pool in self._worker_pools.items():
                if not pool_id.startswith("sync_"):
                    continue

                if pool is None or not isinstance(pool, WorkerPoolProtocol):
                    continue

                try:
                    parts = pool_id.split("_job_")
                    if len(parts) != 2:
                        continue

                    sync_id = parts[0].replace("sync_", "")
                    count = pool.active_and_pending_count

                    if sync_id in results_by_sync:
                        results_by_sync[sync_id] += count
                    else:
                        results_by_sync[sync_id] = count

                except Exception as e:
                    _logger.warning(f"Failed to parse pool_id '{pool_id}': {e}")
                    continue

            return [
                {"sync_id": sync_id, "active_and_pending_worker_count": count}
                for sync_id, count in results_by_sync.items()
            ]

    def register_worker_pool(self, pool_id: str, worker_pool: Any) -> None:
        """Register a worker pool for metrics tracking (synchronous).

        Args:
            pool_id: Unique identifier (format: sync_{sync_id}_job_{sync_job_id})
            worker_pool: AsyncWorkerPool instance to track

        Raises:
            ValueError: If pool_id already registered with different pool instance
        """
        if pool_id in self._worker_pools:
            existing_pool = self._worker_pools[pool_id]

            if existing_pool is worker_pool:
                _logger.warning(
                    f"Worker pool '{pool_id}' already registered (duplicate call). "
                    f"This may indicate redundant registration logic that should be removed."
                )
                return

            else:
                raise ValueError(
                    f"Pool ID '{pool_id}' collision detected! "
                    f"A different pool instance is already registered with this ID. "
                    f"Existing pool: {existing_pool}, New pool: {worker_pool}"
                )

        self._worker_pools[pool_id] = worker_pool

    def unregister_worker_pool(self, pool_id: str) -> None:
        """Unregister a worker pool from metrics tracking (synchronous)."""
        self._worker_pools.pop(pool_id, None)

    async def get_per_connector_metrics(self) -> Dict[str, Dict[str, int]]:
        """Aggregate metrics by connector type for low-cardinality Prometheus metrics."""
        async with self._lock:
            connector_stats: Dict[str, Dict[str, int]] = {}

            for info in self._active_activities.values():
                if not info.get("sync_id"):
                    continue

                connector = info.get("metadata", {}).get("source_type", "unknown")

                if connector not in connector_stats:
                    connector_stats[connector] = {
                        "active_syncs": 0,
                        "active_and_pending_workers": 0,
                    }

                connector_stats[connector]["active_syncs"] += 1

            for activity_id, pool in self._worker_pools.items():
                if pool is None or not isinstance(pool, WorkerPoolProtocol):
                    continue

                activity_info = self._active_activities.get(activity_id)
                if activity_info:
                    connector = activity_info.get("metadata", {}).get("source_type", "unknown")

                    if connector not in connector_stats:
                        connector_stats[connector] = {
                            "active_syncs": 0,
                            "active_and_pending_workers": 0,
                        }

                    connector_stats[connector]["active_and_pending_workers"] += (
                        pool.active_and_pending_count
                    )

            return connector_stats

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary metrics about this worker."""
        activities = await self.get_active_activities()
        sync_job_ids = await self.get_active_sync_job_ids()

        return {
            "worker_id": self.worker_id,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "active_activities_count": len(activities),
            "active_sync_jobs": sorted(sync_job_ids),
            "active_activities": activities,
        }


# Global singleton instance
worker_metrics = WorkerMetricsRegistry()
