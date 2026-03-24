"""Sync execution service — runs a sync via SyncFactory + SyncOrchestrator.

Called exclusively from RunSyncActivity (Temporal worker).
"""

from typing import Optional

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.sync_pipeline.protocols import SyncFactoryProtocol
from airweave.domains.syncs.protocols import SyncJobStateMachineProtocol, SyncServiceProtocol


class SyncService(SyncServiceProtocol):
    """Runs a sync via SyncFactory + SyncOrchestrator.

    Stateless — the only production caller is RunSyncActivity.
    """

    def __init__(
        self,
        state_machine: SyncJobStateMachineProtocol,
        sync_factory: SyncFactoryProtocol,
    ) -> None:
        """Initialize with state machine and factory dependencies."""
        self._state_machine = state_machine
        self._sync_factory = sync_factory

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
        access_token: Optional[str] = None,
    ) -> schemas.Sync:
        """Run a sync."""
        try:
            async with get_db_context() as db:
                orchestrator = await self._sync_factory.create_orchestrator(
                    db=db,
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    connection=source_connection,
                    ctx=ctx,
                    force_full_sync=force_full_sync,
                    execution_config=execution_config,
                    access_token=access_token,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")
            await self._state_machine.transition(
                sync_job_id=sync_job.id,
                target=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
            )
            raise e

        return await orchestrator.run()
