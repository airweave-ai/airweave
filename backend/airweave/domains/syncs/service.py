"""Sync execution service — runs a sync via SyncFactory + SyncOrchestrator.

Called exclusively from RunSyncActivity (Temporal worker).
"""

from typing import Optional

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.source_connections.error_classifier import classify_error
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
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> schemas.Sync:
        """Run a sync.

        Args:
            sync: The sync to run.
            sync_job: The sync job to run.
            collection: The collection to sync.
            source_connection: The source connection to sync.
            ctx: The API context.
            dense_embedder: Domain dense embedder instance.
            sparse_embedder: Domain sparse embedder instance.
            access_token: Optional access token instead of stored credentials.
            force_full_sync: If True, forces a full sync with orphaned entity deletion.
            execution_config: Optional execution config for sync behavior.

        Returns:
            The sync.
        """
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
                    dense_embedder=dense_embedder,
                    sparse_embedder=sparse_embedder,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")
            # (code blue) getattr because schemas.Connection lacks authentication_method.
            # Fix: add authentication_method to SyncContext in the pipeline refactor.
            auth_method = getattr(source_connection, "authentication_method", "") or ""
            classification = classify_error(e, auth_method)
            await self._sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                error_category=classification.category.value if classification.category else None,
                failed_at=utc_now_naive(),
            )
            raise e

        return await orchestrator.run()
