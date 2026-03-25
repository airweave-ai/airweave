"""Protocols for Temporal workflow and schedule services."""

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import WorkflowHandle

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.context import BaseContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.temporal.types import ScheduleInfo


class TemporalWorkflowServiceProtocol(Protocol):
    """Workflow lifecycle management via Temporal.

    Responsible only for starting, cancelling, and cleaning up Temporal
    workflows. Does NOT cover schedule management (see
    TemporalScheduleServiceProtocol), workflow/activity definitions
    (domains/temporal/workflows/), or the worker runtime
    (domains/temporal/worker/).
    """

    async def run_source_connection_workflow(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> WorkflowHandle:
        """Start a source connection sync workflow."""
        ...

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: BaseContext) -> dict[str, bool]:
        """Request cancellation of a running workflow by sync job ID.

        Returns dict with 'success' and 'workflow_found' boolean keys.
        """
        ...

    async def start_cleanup_sync_data_workflow(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
        ctx: ApiContext,
    ) -> Optional[WorkflowHandle]:
        """Start a fire-and-forget cleanup workflow for deleted syncs."""
        ...

    async def is_temporal_enabled(self) -> bool:
        """Check if Temporal is enabled and reachable."""
        ...


class TemporalScheduleServiceProtocol(Protocol):
    """Schedule management: create/update and delete Temporal schedules."""

    async def create_or_update_schedule(
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: AsyncSession,
        ctx: ApiContext,
        uow: UnitOfWork,
        collection_readable_id: Optional[str] = None,
        connection_id: Optional[UUID] = None,
    ) -> str:
        """Create or update a Temporal schedule for a sync.

        Returns the schedule ID.
        """
        ...

    async def delete_all_schedules_for_sync(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> None:
        """Delete all schedules associated with a sync."""
        ...

    async def delete_schedule_handle(self, schedule_id: str) -> None:
        """Delete a Temporal schedule by ID without touching the DB.

        Ignores not-found errors. Used by activities and ORM listeners
        where the DB record is already gone.
        """
        ...

    async def pause_schedules_for_sync(
        self,
        sync_id: UUID,
        *,
        reason: str = "",
    ) -> None:
        """Pause all schedules for a sync (credential error)."""
        ...

    async def unpause_schedules_for_sync(
        self,
        sync_id: UUID,
    ) -> None:
        """Unpause all schedules for a sync (credential fixed)."""
        ...

    async def get_schedules_for_sync(self, sync_id: UUID) -> list[ScheduleInfo]:
        """Return schedule metadata for a sync via the SyncId search attribute."""
        ...

    async def ensure_system_schedules(self) -> None:
        """Create system-level singleton schedules if they don't already exist.

        Covers the stuck-job cleanup schedule and the API key expiration
        notification schedule. Called once during API server startup.
        """
        ...
