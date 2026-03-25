"""Tests for WorkerMetricsRegistry — coverage of missing lines."""

import pytest

from airweave.domains.temporal.metrics.registry import WorkerMetricsRegistry


class BadPool:
    """Pool whose active_and_pending_count succeeds on first access (isinstance)
    but raises on the second (actual usage inside try block)."""

    def __init__(self):
        self._access_count = 0

    @property
    def active_and_pending_count(self) -> int:
        self._access_count += 1
        if self._access_count > 1:
            raise RuntimeError("pool broken")
        return 0


@pytest.mark.unit
async def test_get_per_sync_worker_counts_parse_error():
    """Pool that raises during count access triggers the warning path."""
    registry = WorkerMetricsRegistry()
    registry._worker_pools["sync_abc_job_def"] = BadPool()

    result = await registry.get_per_sync_worker_counts()
    assert result == []
