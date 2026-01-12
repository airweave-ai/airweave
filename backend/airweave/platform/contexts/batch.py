"""Batch context for sync operations."""

from dataclasses import dataclass


@dataclass
class BatchContext:
    """Micro-batching configuration for entity processing.

    Controls HOW entities are processed (batching behavior).

    Attributes:
        should_batch: Whether to use micro-batched pipeline
        batch_size: Max entities per micro-batch
        max_batch_latency_ms: Max time before flushing partial batch
        force_full_sync: Whether to force full sync (triggers orphan cleanup)
    """

    should_batch: bool = True
    batch_size: int = 64
    max_batch_latency_ms: int = 200
    force_full_sync: bool = False
