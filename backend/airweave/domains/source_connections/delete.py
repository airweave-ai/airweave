"""Source connection deletion service."""

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import SyncJobStatus
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionDeletionServiceProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol, SyncLifecycleServiceProtocol
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.schemas.source_connection import SourceConnection as SourceConnectionSchema


class SourceConnectionDeletionService(SourceConnectionDeletionServiceProtocol):
    """Deletes a source connection and all related data.

    The flow is:
    1. Cancel any running sync workflows and wait for them to stop.
    2. CASCADE-delete the DB records (source connection, sync, jobs, entities).
    3. Fire-and-forget a Temporal cleanup workflow for the slow external
       data deletion (Vespa, ARF, schedules) which can take minutes.
    """

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        response_builder: ResponseBuilderProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
    ) -> None:
        self._sc_repo = sc_repo
        self._collection_repo = collection_repo
        self._sync_job_repo = sync_job_repo
        self._sync_lifecycle = sync_lifecycle
        self._response_builder = response_builder
        self._temporal_workflow_service = temporal_workflow_service

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        """Delete a source connection and all related data."""
        source_conn = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise NotFoundException("Source connection not found")

        # Capture attributes upfront to avoid lazy-loading issues after session changes
        sync_id = source_conn.sync_id
        collection = await self._collection_repo.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )
        if not collection:
            raise NotFoundException("Collection not found")
        collection_id = str(collection.id)
        organization_id = str(collection.organization_id)

        # Build response before deletion
        response = await self._response_builder.build_response(db, source_conn, ctx)

        # Cancel any running jobs and wait for the Temporal workflow to
        # terminate before we cascade-delete the DB rows.
        if sync_id:
            latest_job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
            if latest_job and latest_job.status in [
                SyncJobStatus.PENDING,
                SyncJobStatus.RUNNING,
                SyncJobStatus.CANCELLING,
            ]:
                if latest_job.status in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
                    ctx.logger.info(
                        f"Cancelling job {latest_job.id} for source connection {id} before deletion"
                    )
                    try:
                        await self._sync_lifecycle.cancel_job(
                            db,
                            source_connection_id=id,
                            job_id=latest_job.id,
                            ctx=ctx,
                        )
                    except Exception as e:
                        ctx.logger.warning(
                            f"Failed to cancel job {latest_job.id} during deletion: {e}"
                        )

                # BARRIER: Wait for the workflow to reach a terminal state so
                # the worker stops writing before we cascade-delete the rows.
                reached_terminal = await self._wait_for_sync_job_terminal_state(
                    db, sync_id, timeout_seconds=15
                )
                if not reached_terminal:
                    ctx.logger.warning(
                        f"Job for sync {sync_id} did not reach terminal state within 15s "
                        f"-- proceeding with deletion anyway"
                    )

        # Delete the source connection first (CASCADE removes sync, jobs, entities).
        await self._sc_repo.remove(db, id=id, ctx=ctx)

        # Fire-and-forget: schedule async cleanup of external data (Vespa, ARF,
        # Temporal schedules). This can take minutes for Vespa and must not
        # block the API response.
        if sync_id:
            try:
                await self._temporal_workflow_service.start_cleanup_sync_data_workflow(
                    sync_ids=[str(sync_id)],
                    collection_id=collection_id,
                    organization_id=organization_id,
                    ctx=ctx,
                )
            except Exception as e:
                ctx.logger.error(
                    f"Failed to schedule async cleanup for sync {sync_id}: {e}. "
                    f"Data may be orphaned in Vespa/ARF."
                )

        return response

    async def _wait_for_sync_job_terminal_state(
        self,
        db: AsyncSession,
        sync_id: UUID,
        *,
        timeout_seconds: int = 30,
        poll_interval: float = 1.0,
    ) -> bool:
        """Wait for the latest sync job to reach a terminal state.

        Polls the database until the job reaches COMPLETED, FAILED, or CANCELLED.
        Used as a cancellation barrier to prevent cleanup from running while
        a Temporal worker is still actively writing.

        Args:
            db: Database session.
            sync_id: Sync ID whose latest job to monitor.
            timeout_seconds: Maximum time to wait before giving up.
            poll_interval: Seconds between poll attempts.

        Returns:
            True if a terminal state was reached, False on timeout.
        """
        terminal_states = {
            SyncJobStatus.COMPLETED,
            SyncJobStatus.FAILED,
            SyncJobStatus.CANCELLED,
        }
        elapsed = 0.0
        while elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            # Expire cached ORM objects to force a fresh read from the database
            db.expire_all()
            job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
            if job and job.status in terminal_states:
                return True
        return False
