"""Fake sync factory for testing."""

from typing import Optional
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.domains.sync_pipeline.config import SyncConfig


class FakeSyncFactory:
    """In-memory fake for SyncFactoryProtocol."""

    def __init__(self) -> None:
        self._calls: list[tuple] = []
        self._orchestrator = AsyncMock()

    async def create_orchestrator(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ):
        self._calls.append(("create_orchestrator", sync.id, sync_job.id))
        return self._orchestrator
