"""Sync execution service — runs a sync via SyncFactory + SyncOrchestrator.

Called exclusively from RunSyncActivity (Temporal worker).
"""

from typing import Optional

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.syncs.protocols import SyncJobServiceProtocol, SyncServiceProtocol
from airweave.platform.sync.config import SyncConfig
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
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> schemas.Sync:
        """Run a sync via SyncFactory + SyncOrchestrator."""
        try:
            async with get_db_context() as db:
                orchestrator = await SyncFactory.create_orchestrator(
                    db=db,
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    connection=source_connection,
                    ctx=ctx,
                    access_token=access_token,
                    force_full_sync=force_full_sync,
                    execution_config=execution_config,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")
            await self._sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                failed_at=utc_now_naive(),
            )
            raise e

        return await orchestrator.run()
