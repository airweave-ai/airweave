"""Worker metrics tracking for Temporal workers.

This module provides a global registry for tracking active activities
and metrics about the worker's current workload.
"""

import asyncio
import os
import socket
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID


class WorkerMetricsRegistry:
    """Global registry for tracking active activities in this worker process."""

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        self._active_activities: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
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
        organization_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager to track an active activity.

        Args:
            activity_name: Name of the activity
            sync_job_id: ID of the sync job being processed
            organization_id: ID of the organization
            metadata: Additional metadata about the activity

        Example:
            async with worker_metrics.track_activity(
                "run_sync_activity",
                sync_job_id=sync_job.id,
                organization_id=org.id,
            ):
                # Activity execution
                await sync_service.run(...)
        """
        activity_id = f"{activity_name}-{sync_job_id or 'unknown'}"
        start_time = datetime.now(timezone.utc)

        async with self._lock:
            self._active_activities[activity_id] = {
                "activity_name": activity_name,
                "sync_job_id": str(sync_job_id) if sync_job_id else None,
                "organization_id": str(organization_id) if organization_id else None,
                "start_time": start_time.isoformat(),
                "metadata": metadata or {},
            }

        try:
            yield
        finally:
            async with self._lock:
                self._active_activities.pop(activity_id, None)

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
