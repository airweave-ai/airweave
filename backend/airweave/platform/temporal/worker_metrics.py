"""Worker metrics tracking for Temporal workers.

This module provides a global registry for tracking active activities
and metrics about the worker's current workload.
"""

import asyncio
import os
import re
import socket
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from airweave.core.protocols.worker_metrics_registry import SyncMetricDetail, SyncWorkerCount


class WorkerMetricsRegistry:
    """Global registry for tracking active activities in this worker process."""

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        self._active_activities: Dict[str, Dict[str, Any]] = {}
        self._worker_pools: Dict[str, Any] = {}  # Store worker pool references by pool_id
        self._lock = asyncio.Lock()  # Single async lock (no nesting, safe from deadlocks)
        self._worker_start_time = datetime.now(timezone.utc)
        self._worker_id = self._generate_worker_id()

    def _generate_worker_id(self) -> str:
        """Generate a unique identifier for this worker.

        Uses Kubernetes pod name if available, otherwise hostname.
        """
        # Try Kubernetes pod name first
        pod_name = os.environ.get("HOSTNAME")
        if pod_name and pod_name.startswith("airweave-worker"):
            return pod_name

        # Fall back to hostname
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
        """Context manager to track an active activity.

        Args:
            activity_name: Name of the activity
            sync_job_id: ID of the sync job being processed
            sync_id: ID of the sync configuration
            organization_id: ID of the organization
            metadata: Additional metadata about the activity
            worker_pool: Reference to the AsyncWorkerPool instance

        Example:
            async with worker_metrics.track_activity(
                "run_sync_activity",
                sync_job_id=sync_job.id,
                sync_id=sync.id,
                organization_id=org.id,
                metadata={"source_type": "slack", "org_name": "Acme Corp"},
                worker_pool=worker_pool,
            ):
                # Activity execution
                await sync_service.run(...)
        """
        activity_id = f"{activity_name}-{sync_job_id or 'unknown'}"
        start_time = datetime.now(timezone.utc)

        # Single lock for all operations (no nesting, safe from deadlocks)
        async with self._lock:
            self._active_activities[activity_id] = {
                "activity_name": activity_name,
                "sync_job_id": str(sync_job_id) if sync_job_id else None,
                "sync_id": str(sync_id) if sync_id else None,
                "organization_id": str(organization_id) if organization_id else None,
                "start_time": start_time.isoformat(),
                "metadata": metadata or {},
            }

            # Store worker pool reference if provided
            if worker_pool is not None:
                self._worker_pools[activity_id] = worker_pool

        try:
            yield
        finally:
            # Clean up on completion
            async with self._lock:
                self._active_activities.pop(activity_id, None)
                self._worker_pools.pop(activity_id, None)

    async def get_active_activities(self) -> List[Dict[str, Any]]:
        """Get list of currently active activities.

        Returns:
            List of dicts with activity information including:
            - activity_name
            - sync_job_id
            - organization_id
            - start_time
            - duration_seconds
            - metadata
        """
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
        """Get set of sync job IDs currently being processed.

        Returns:
            Set of sync job ID strings
        """
        async with self._lock:
            return {
                info["sync_job_id"]
                for info in self._active_activities.values()
                if info["sync_job_id"]
            }

    async def get_detailed_sync_metrics(self) -> list[SyncMetricDetail]:
        """Get detailed metrics for each active sync.

        Returns:
            List of dicts with sync metadata including:
            - sync_id: ID of the sync configuration
            - sync_job_id: ID of the sync job run
            - org_name: Organization name
            - source_type: Source connection type (short_name)
        """
        async with self._lock:
            sync_metrics = []

            for info in self._active_activities.values():
                if info.get("sync_job_id"):  # Only include activities with sync_job_id
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
        """Get total number of active and pending workers across all worker pools.

        Returns:
            Sum of active+pending workers across all tracked worker pools.
            Includes both executing tasks and tasks waiting for a worker slot.
        """
        async with self._lock:
            total = 0
            for pool in self._worker_pools.values():
                if pool is not None and hasattr(pool, "active_and_pending_count"):
                    total += pool.active_and_pending_count
            return total

    async def get_per_sync_worker_counts(self) -> list[SyncWorkerCount]:
        """Get worker count for each active sync.

        Returns:
            List of dicts with sync_id and active_and_pending_worker_count.
            Count includes both executing and waiting tasks.

        Note:
            If multiple jobs of the same sync run concurrently (shouldn't happen
            due to checks in trigger_sync_run), their counts will be aggregated.
            This reduces metric cardinality from ~4.5M to ~300 time series.
        """
        async with self._lock:
            # Use dict to aggregate by sync_id
            results_by_sync: Dict[str, int] = {}

            # Iterate through worker pools (format: sync_{sync_id}_job_{sync_job_id})
            for pool_id, pool in self._worker_pools.items():
                if not pool_id.startswith("sync_"):
                    continue

                if pool is None or not hasattr(pool, "active_and_pending_count"):
                    continue

                try:
                    # Parse pool_id to extract sync_id
                    # Format: sync_{sync_id}_job_{sync_job_id}
                    parts = pool_id.split("_job_")
                    if len(parts) != 2:
                        continue

                    sync_id = parts[0].replace("sync_", "")
                    count = pool.active_and_pending_count

                    # Aggregate if sync_id already exists (handles rare concurrent runs)
                    if sync_id in results_by_sync:
                        results_by_sync[sync_id] += count
                    else:
                        results_by_sync[sync_id] = count

                except Exception as e:
                    # Log but continue - don't break metrics for one bad pool_id
                    import logging

                    logging.warning(f"Failed to parse pool_id '{pool_id}': {e}")
                    continue

            # Convert to list of dicts
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

        Note:
            Uses asyncio.Lock internally. Safe to call from sync context but registration
            happens without lock protection (acceptable since called during setup phase).
        """
        import logging

        # Simple direct assignment without lock (called during orchestrator setup)
        # Lock not needed here as this is called before concurrent access begins
        if pool_id in self._worker_pools:
            existing_pool = self._worker_pools[pool_id]

            # Same pool, same ID = duplicate registration (warn but allow)
            if existing_pool is worker_pool:
                logging.warning(
                    f"Worker pool '{pool_id}' already registered (duplicate call). "
                    f"This may indicate redundant registration logic that should be removed."
                )
                return

            # Different pool, same ID = collision (ERROR)
            else:
                raise ValueError(
                    f"Pool ID '{pool_id}' collision detected! "
                    f"A different pool instance is already registered with this ID. "
                    f"Existing pool: {existing_pool}, New pool: {worker_pool}"
                )

        self._worker_pools[pool_id] = worker_pool

    def unregister_worker_pool(self, pool_id: str) -> None:
        """Unregister a worker pool from metrics tracking (synchronous).

        Args:
            pool_id: Unique identifier for the pool

        Note:
            Safe to call from sync context. Simple dict.pop() without lock protection
            (acceptable since called during cleanup phase).
        """
        # Simple removal without lock (called during orchestrator cleanup)
        self._worker_pools.pop(pool_id, None)

    async def get_per_connector_metrics(self) -> Dict[str, Dict[str, int]]:
        """Aggregate metrics by connector type for low-cardinality Prometheus metrics.

        Returns:
            Dict mapping connector_type to metrics:
            {
                "slack": {"active_syncs": 3, "active_and_pending_workers": 25},
                "notion": {"active_syncs": 2, "active_and_pending_workers": 10},
                ...
            }
        """
        # Single lock for all operations (no nesting, safe from deadlocks)
        async with self._lock:
            connector_stats: Dict[str, Dict[str, int]] = {}

            # Count active syncs per connector type
            for info in self._active_activities.values():
                if not info.get("sync_id"):  # Only count sync activities
                    continue

                connector = info.get("metadata", {}).get("source_type", "unknown")

                if connector not in connector_stats:
                    connector_stats[connector] = {
                        "active_syncs": 0,
                        "active_and_pending_workers": 0,
                    }

                connector_stats[connector]["active_syncs"] += 1

            # Add worker counts per connector (same lock, no nesting)
            for activity_id, pool in self._worker_pools.items():
                if pool is None or not hasattr(pool, "active_and_pending_count"):
                    continue

                # Get connector type from corresponding activity
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
        """Get summary metrics about this worker.

        Returns:
            Dict with worker metrics including:
            - worker_id: Unique identifier for this worker
            - uptime_seconds: How long the worker has been running
            - active_activities_count: Number of activities currently executing
            - active_sync_jobs: List of sync job IDs being processed
            - active_activities: Detailed list of active activities
        """
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
