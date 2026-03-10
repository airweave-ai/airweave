"""Fake sync service for testing."""

from typing import Optional

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.platform.sync.config import SyncConfig


class FakeSyncService:
    """In-memory fake for SyncServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty call log."""
        self._calls: list[tuple] = []

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> schemas.Sync:
        """Record call and return the sync as-is."""
        self._calls.append(("run", sync, sync_job))
        return sync
