"""Client for querying Temporal worker metrics.

This module demonstrates how to query worker metrics endpoints
for building monitoring UIs.
"""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from airweave.core.logging import logger


class WorkerMetricsClient:
    """Client for querying worker metrics across multiple workers."""

    def __init__(self, worker_urls: List[str], timeout: int = 5):
        """Initialize the metrics client.

        Args:
            worker_urls: List of worker base URLs (e.g., ["http://worker-1:9091", "http://worker-2:9091"])
            timeout: Request timeout in seconds
        """
        self.worker_urls = worker_urls
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_worker_health(self, worker_url: str) -> Dict[str, Any]:
        """Get health status of a single worker.

        Args:
            worker_url: Base URL of the worker

        Returns:
            Dict with health status: {"url": str, "status": str, "healthy": bool}
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{worker_url}/health") as response:
                    status_text = await response.text()
                    return {
                        "url": worker_url,
                        "status": status_text,
                        "healthy": response.status == 200,
                    }
        except Exception as e:
            logger.error(f"Failed to check health for {worker_url}: {e}")
            return {
                "url": worker_url,
                "status": f"ERROR: {str(e)}",
                "healthy": False,
            }

    async def get_worker_metrics(self, worker_url: str) -> Optional[Dict[str, Any]]:
        """Get metrics from a single worker.

        Args:
            worker_url: Base URL of the worker

        Returns:
            Dict with worker metrics or None if failed
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{worker_url}/metrics") as response:
                    if response.status == 200:
                        data = await response.json()
                        data["url"] = worker_url  # Add URL for identification
                        return data
                    else:
                        logger.warning(
                            f"Worker {worker_url} returned non-200 status: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Failed to get metrics from {worker_url}: {e}")
            return None

    async def get_all_worker_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics from all configured workers.

        Returns:
            List of worker metrics dicts (excludes workers that failed to respond)
        """
        tasks = [self.get_worker_metrics(url) for url in self.worker_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None values and exceptions
        return [r for r in results if r is not None and not isinstance(r, Exception)]

    async def get_cluster_summary(self) -> Dict[str, Any]:
        """Get aggregated summary across all workers.

        Returns:
            Dict with cluster-wide statistics:
            - total_workers: Number of reachable workers
            - total_active_syncs: Total number of active sync jobs across all workers
            - workers: List of per-worker metrics
            - active_sync_jobs: Set of all active sync job IDs
        """
        all_metrics = await self.get_all_worker_metrics()

        total_active_syncs = 0
        all_sync_job_ids = set()

        for worker_metrics in all_metrics:
            total_active_syncs += worker_metrics.get("active_activities_count", 0)
            all_sync_job_ids.update(worker_metrics.get("active_sync_jobs", []))

        return {
            "total_workers": len(all_metrics),
            "total_active_syncs": total_active_syncs,
            "total_unique_sync_jobs": len(all_sync_job_ids),
            "workers": all_metrics,
            "active_sync_jobs": sorted(list(all_sync_job_ids)),
        }


async def example_usage():
    """Example of how to use the metrics client."""
    # In Kubernetes, you'd discover worker URLs via service discovery
    # For local development, you might have a single worker
    worker_urls = [
        "http://localhost:8888",  # Local development
        # In production with multiple workers:
        # "http://airweave-worker-0:8888",
        # "http://airweave-worker-1:8888",
        # "http://airweave-worker-2:8888",
    ]

    client = WorkerMetricsClient(worker_urls)

    print("=== Checking Worker Health ===")
    for url in worker_urls:
        health = await client.get_worker_health(url)
        print(f"{health['url']}: {health['status']} (healthy: {health['healthy']})")

    print("\n=== Getting Cluster Summary ===")
    summary = await client.get_cluster_summary()
    print(f"Total Workers: {summary['total_workers']}")
    print(f"Total Active Syncs: {summary['total_active_syncs']}")
    print(f"Unique Sync Jobs: {summary['total_unique_sync_jobs']}")

    print("\n=== Per-Worker Details ===")
    for worker in summary["workers"]:
        print(f"\nWorker: {worker['worker_id']} ({worker['url']})")
        print(f"  Status: {worker['status']}")
        print(f"  Uptime: {worker['uptime_seconds']}s")
        print(f"  Active Syncs: {worker['active_activities_count']}")
        for activity in worker.get("active_activities", []):
            print(
                f"    - {activity['activity_name']} "
                f"(job: {activity['sync_job_id']}, "
                f"duration: {activity['duration_seconds']}s)"
            )


if __name__ == "__main__":
    asyncio.run(example_usage())

