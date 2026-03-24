"""Worker metrics subdomain for Temporal workers.

Public API:
    worker_metrics          -- global WorkerMetricsRegistry singleton
    WorkerMetricsRegistry   -- the registry class itself (for tests / typing)
    WorkerPoolProtocol      -- structural protocol for tracked worker pools
    WorkerMetricsSnapshot   -- frozen snapshot passed to gauge adapters
    ConnectorSnapshot       -- per-connector slice of a snapshot
"""

from airweave.domains.temporal.metrics.registry import (
    WorkerMetricsRegistry,
    WorkerPoolProtocol,
    worker_metrics,
)
from airweave.domains.temporal.metrics.snapshot import ConnectorSnapshot, WorkerMetricsSnapshot

__all__ = [
    "ConnectorSnapshot",
    "WorkerMetricsRegistry",
    "WorkerMetricsSnapshot",
    "WorkerPoolProtocol",
    "worker_metrics",
]
