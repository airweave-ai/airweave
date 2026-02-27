"""Protocols for Temporal workflow and schedule services."""

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import WorkflowHandle

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork


class TemporalWorkflowServiceProtocol(Protocol):
    """Workflow lifecycle management via Temporal.

    Responsible only for starting, cancelling, and cleaning up Temporal
    workflows. Does NOT cover schedule management (see
    TemporalScheduleServiceProtocol), workflow/activity definitions
    (platform/temporal/workflows/), or the worker runtime
    (platform/temporal/worker/).
    """

    async def run_source_connection_workflow(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> WorkflowHandle:
        """Start a source connection sync workflow."""
        ...

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: ApiContext) -> dict[str, bool]:
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
