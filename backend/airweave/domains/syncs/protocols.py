"""Protocols for the syncs domain."""

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync import Sync
from airweave.models.sync_cursor import SyncCursor
from airweave.models.sync_job import SyncJob
from airweave.schemas.sync import SyncUpdate
from airweave.schemas.sync_job import SyncJobCreate


class SyncJobRepositoryProtocol(Protocol):
    """Data access for sync job records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SyncJob]:
        """Get a sync job by ID within org scope."""
        ...

    async def get_latest_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> Optional[SyncJob]:
        """Get the most recent sync job for a sync."""
        ...

    async def get_active_for_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Get all active (PENDING, RUNNING, CANCELLING) jobs for a sync."""
        ...

    async def get_all_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Get all jobs for a specific sync."""
        ...

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncJobCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SyncJob:
        """Create a new sync job."""
        ...


class SyncRepositoryProtocol(Protocol):
    """Data access for sync records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[schemas.Sync]:
        """Get a sync by ID, including connections."""
        ...

    async def get_without_connections(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[Sync]:
        """Get a sync by ID without connections."""
        ...

    async def update(
        self,
        db: AsyncSession,
        db_obj: Sync,
        obj_in: SyncUpdate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Sync:
        """Update an existing sync."""
        ...


class SyncCursorRepositoryProtocol(Protocol):
    """Data access for sync cursor records."""

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SyncCursor]:
        """Get the sync cursor for a given sync."""
        ...
