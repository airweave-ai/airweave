"""Tests for WorkerMetricsRegistry — coverage of missing lines."""

import pytest

from airweave.domains.temporal.metrics.registry import WorkerMetricsRegistry


class BadPool:
    """Pool whose active_and_pending_count always raises."""

    @property
    def active_and_pending_count(self) -> int:
        raise RuntimeError("pool broken")


@pytest.mark.unit
async def test_get_per_sync_worker_counts_parse_error():
    """Pool that raises during count access triggers the warning path."""
    registry = WorkerMetricsRegistry()
    registry._worker_pools["sync_abc_job_def"] = BadPool()

    result = await registry.get_per_sync_worker_counts()
    assert result == []
