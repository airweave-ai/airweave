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
from airweave.schemas.source_connection import ScheduleConfig
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

    async def transition_status(
        self,
        db: AsyncSession,
        sync_id: UUID,
        expected: SyncStatus,
        target: SyncStatus,
    ) -> None:
        """Optimistic status update: SET status=target WHERE id=sync_id AND status=expected.

        Raises OptimisticLockError if the status changed since read.
        """
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
    """Unified sync service — the public interface for the syncs domain.

    Provides lifecycle (create, get, pause, resume, delete), job management
    (trigger_run, get_jobs, cancel_job), and execution (run) operations.
    All methods speak the sync domain language; no source_connection types
    cross this boundary.
    """

    # -- Lifecycle --

    async def create(
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
    ) -> SyncProvisionResult:
        """Create sync + optional job + Temporal schedule atomically."""
        ...

    async def get(self, db: AsyncSession, *, sync_id: UUID, ctx: BaseContext) -> schemas.Sync:
        """Get a sync by ID."""
        ...

    async def pause(
        self,
        sync_id: UUID,
        ctx: BaseContext,
        *,
        reason: str = "",
    ) -> SyncTransitionResult:
        """Pause a sync."""
        ...

    async def resume(
        self,
        sync_id: UUID,
        ctx: BaseContext,
        *,
        reason: str = "",
    ) -> SyncTransitionResult:
        """Resume a paused sync."""
        ...

    async def delete(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
        cancel_timeout_seconds: int = 15,
    ) -> None:
        """Cancel active workflows and schedule async cleanup."""
        ...

    # -- Jobs --

    async def resolve_destination_ids(self, db: AsyncSession, ctx: ApiContext) -> List[UUID]:
        """Resolve destination connection IDs (interim — will move to a registry)."""
        ...

    async def trigger_run(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Create a PENDING job and start the Temporal workflow."""
        ...

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[schemas.SyncJob]:
        """List jobs for a sync."""
        ...

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SyncJob:
        """Cancel a running sync job."""
        ...

    async def validate_force_full_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> None:
        """Validate and log force_full_sync intent."""
        ...

    # -- Execution --

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
