"""Sync execution service — runs a sync via SyncFactory + SyncOrchestrator.

Called exclusively from RunSyncActivity (Temporal worker).
"""

from uuid import UUID

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.syncs.protocols import SyncJobServiceProtocol, SyncServiceProtocol
from airweave.platform.sync.factory import SyncFactory


class SyncService(SyncServiceProtocol):
    """Runs a sync via SyncFactory + SyncOrchestrator.

    Stateless — the only production caller is RunSyncActivity.
    """

    def __init__(self, sync_job_service: SyncJobServiceProtocol) -> None:
        """Initialize with injected sync job service."""
        self._sync_job_service = sync_job_service

    async def run(
        self,
        sync_id: UUID,
        sync_job_id: UUID,
        ctx: BaseContext,
        force_full_sync: bool = False,
    ) -> schemas.Sync:
        """Run a sync.

        Opens a DB session and delegates all hydration to SyncFactory.
        """
        try:
            async with get_db_context() as db:
                orchestrator = await SyncFactory.create_orchestrator(
                    db=db,
                    sync_id=sync_id,
                    sync_job_id=sync_job_id,
                    ctx=ctx,
                    force_full_sync=force_full_sync,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")
            await self._sync_job_service.update_status(
                sync_job_id=sync_job_id,
                status=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                failed_at=utc_now_naive(),
            )
            raise e

        return await orchestrator.run()
