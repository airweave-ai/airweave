"""Protocols for the syncs domain."""

from datetime import datetime
from typing import List, Optional, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.types import SyncProvisionResult
from airweave.models.sync import Sync
from airweave.models.sync_cursor import SyncCursor
from airweave.models.sync_job import SyncJob
from airweave.platform.sync.pipeline.entity_tracker import SyncStats
from airweave.schemas.source_connection import ScheduleConfig, SourceConnectionJob
from airweave.schemas.sync import SyncCreate, SyncUpdate
from airweave.schemas.sync_job import SyncJobCreate, SyncJobUpdate


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

    async def update(
        self,
        db: AsyncSession,
        db_obj: SyncJob,
        obj_in: SyncJobUpdate,
        ctx: ApiContext,
    ) -> SyncJob:
        """Update an existing sync job."""
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

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Create a new sync with its connection associations."""
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


class SyncRecordServiceProtocol(Protocol):
    """Sync record management: create syncs and trigger runs."""

    async def create_sync(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Create a Sync record and optionally a PENDING SyncJob.

        All writes happen inside the caller's UoW (no commit).
        """
        ...

    async def trigger_sync_run(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Trigger a manual sync run.

        Returns (sync_schema, sync_job_schema).
        Raises HTTPException if a job is already active.
        """
        ...


class SyncJobServiceProtocol(Protocol):
    """Sync job status management."""

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        ctx: ApiContext,
        stats: Optional[SyncStats] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details."""
        ...


class SyncLifecycleServiceProtocol(Protocol):
    """Sync lifecycle: provision, run, get jobs, cancel."""

    async def provision_sync(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        collection_id: UUID,
        collection_readable_id: str,
        source_entry: SourceRegistryEntry,
        schedule_config: Optional[ScheduleConfig],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Optional[SyncProvisionResult]:
        """Create sync + job + Temporal schedule atomically.

        Returns None for federated search sources (no sync needed).
        """
        ...

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Trigger a sync run for a source connection."""
        ...

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """Get sync jobs for a source connection."""
        ...

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job for a source connection."""
        ...
