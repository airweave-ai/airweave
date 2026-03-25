"""Protocols for the syncs domain."""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.context import BaseContext
from airweave.core.shared_models import SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.syncs.types import SyncProvisionResult, SyncTransitionResult
from airweave.models.sync import Sync
from airweave.models.sync_cursor import SyncCursor
from airweave.schemas.source_connection import ScheduleConfig, SourceConnectionJob
from airweave.schemas.sync import SyncCreate, SyncUpdate


class SyncRepositoryProtocol(Protocol):
    """Data access for sync records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: BaseContext) -> Optional[schemas.Sync]:
        """Get a sync by ID, including connections."""
        ...

    async def get_without_connections(
        self, db: AsyncSession, id: UUID, ctx: BaseContext
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

    async def resolve_destination_ids(self, db: AsyncSession, ctx: ApiContext) -> List[UUID]:
        """Resolve destination connection IDs based on feature flags."""
        ...

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


class SyncStateMachineProtocol(Protocol):
    """Validated, idempotent sync status transitions with schedule side effects."""

    async def transition(
        self,
        sync_id: UUID,
        target: SyncStatus,
        ctx: BaseContext,
        *,
        reason: str = "",
    ) -> SyncTransitionResult:
        """Execute a validated, idempotent sync status transition.

        Side effects (schedule pause/unpause) run after the DB commit.
        """
        ...


class SyncServiceProtocol(Protocol):
    """Sync execution: build orchestrator and run."""

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: BaseContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
        access_token: Optional[str] = None,
    ) -> schemas.Sync:
        """Run a sync via SyncFactory + SyncOrchestrator."""
        ...


class SyncLifecycleServiceProtocol(Protocol):
    """Sync lifecycle: provision, run, get jobs, cancel, teardown."""

    async def teardown_syncs_for_collection(
        self,
        db: AsyncSession,
        *,
        sync_ids: List[UUID],
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
        cancel_timeout_seconds: int = 15,
    ) -> None:
        """Cancel running workflows and schedule async cleanup for a collection's syncs."""
        ...

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
