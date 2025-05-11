"""Service for data synchronization."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.dag_service import dag_service
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.sync.context import SyncContextFactory
from airweave.platform.sync.orchestrator import sync_orchestrator


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self,
        db: AsyncSession,
        sync: schemas.SyncCreate,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.Sync:
        """Create a new sync.

        This function creates a new sync and then creates the initial DAG for it. It uses an
        externally scoped unit of work to ensure that the sync and DAG are created in a single
        transaction, with rollback on error.

        Args:
        ----
            db (AsyncSession): The database session.
            sync (schemas.SyncCreate): The sync to create.
            current_user (schemas.User): The current user.
            uow (UnitOfWork): The unit of work.

        Returns:
        -------
            schemas.Sync: The created sync.
        """
        sync = await crud.sync.create(db=db, obj_in=sync, current_user=current_user, uow=uow)
        await uow.session.flush()
        await dag_service.create_initial_dag(
            db=db, sync_id=sync.id, current_user=current_user, uow=uow
        )
        return sync

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync.

        Args:
        ----
            sync (schemas.Sync): The sync to run.
            sync_job (schemas.SyncJob): The sync job to run.
            dag (schemas.SyncDag): The DAG to run.
            current_user (schemas.User): The current user.

        Returns:
        -------
            schemas.Sync: The sync.
        """
        try:
            async with get_db_context() as db:
                sync_context = await SyncContextFactory.create(
                    db, sync, sync_job, dag, current_user
                )
        except Exception as e:
            logger.error(f"Error during sync context creation: {e}")
            # Fail the sync job if concext creation failed
            await sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.FAILED,
                current_user=current_user,
                error=str(e),
                failed_at=datetime.now(),
            )
            raise e

        return await sync_orchestrator.run(sync_context)


sync_service = SyncService()
