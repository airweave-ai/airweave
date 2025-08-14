"""Service for data synchronization."""

from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.dag_service import dag_service
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import (
    CollectionNotFoundException,
    InvalidScheduleOperationException,
    MinuteLevelScheduleException,
    NotFoundException,
    ScheduleNotExistsException,
    ScheduleOperationException,
    SyncDagNotFoundException,
    SyncJobNotFoundException,
    SyncNotFoundException,
)
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.sync.factory import SyncFactory
from airweave.platform.temporal.schedule_service import temporal_schedule_service
from airweave.schemas import AuthContext


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self,
        db: AsyncSession,
        sync: schemas.SyncCreate,
        ctx: ApiContext,
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
            ctx (ApiContext): The API context.
            uow (UnitOfWork): The unit of work.

        Returns:
        -------
            schemas.Sync: The created sync.
        """
        sync = await crud.sync.create(
            db=db,
            obj_in=sync,
            ctx=ctx,
            uow=uow,
        )
        await uow.session.flush()
        await dag_service.create_initial_dag(db=db, sync_id=sync.id, ctx=ctx, uow=uow)
        return sync

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
    ) -> schemas.Sync:
        """Run a sync.

        Args:
        ----
            sync (schemas.Sync): The sync to run.
            sync_job (schemas.SyncJob): The sync job to run.
            dag (schemas.SyncDag): The DAG to run.
            collection (schemas.Collection): The collection to sync.
            source_connection (schemas.Connection): The source connection to sync.
            ctx (ApiContext): The API context.
            access_token (Optional[str]): Optional access token to use
                instead of stored credentials.

        Returns:
        -------
            schemas.Sync: The sync.
        """
        try:
            async with get_db_context() as db:
                # Create dedicated orchestrator instance
                orchestrator = await SyncFactory.create_orchestrator(
                    db=db,
                    sync=sync,
                    sync_job=sync_job,
                    dag=dag,
                    collection=collection,
                    source_connection=source_connection,
                    ctx=ctx,
                    access_token=access_token,
                )
        except Exception as e:
            logger.error(f"Error during sync orchestrator creation: {e}")
            # Fail the sync job if orchestrator creation failed
            await sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                failed_at=utc_now_naive(),
            )
            raise e

        # Run the sync with the dedicated orchestrator instance
        return await orchestrator.run()

    async def list_syncs(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        with_source_connection: bool = False,
    ) -> Union[List[schemas.Sync], List[schemas.SyncWithSourceConnection]]:
        """List all syncs for a user.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (ApiContext): The API context.
            skip (int): The number of syncs to skip.
            limit (int): The number of syncs to return.
            with_source_connection (bool): Whether to include source connections.

        Returns:
        -------
            Union[List[schemas.Sync], List[schemas.SyncWithSourceConnection]]: A list of syncs.
        """
        if with_source_connection:
            syncs = await crud.sync.get_all_syncs_join_with_source_connection(db=db, ctx=ctx)
        else:
            syncs = await crud.sync.get_multi(db=db, ctx=ctx, skip=skip, limit=limit)
        return syncs

    async def get_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
        with_connections: bool = False,
    ) -> schemas.Sync:
        """Get a specific sync by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync to get.
            ctx (ApiContext): The API context.
            with_connections (bool): Whether to include connections.

        Returns:
        -------
            schemas.Sync: The sync.

        Raises:
        ------
            SyncNotFoundException: If the sync is not found.
        """
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=with_connections)
        if not sync:
            raise SyncNotFoundException(f"Sync {sync_id} not found")
        return sync

    async def delete_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
        delete_data: bool = False,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Delete a sync configuration and optionally its associated data.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync to delete.
            ctx (ApiContext): The API context.
            delete_data (bool): Whether to delete the data.
            uow (Optional[UnitOfWork]): The unit of work.

        Returns:
        -------
            schemas.Sync: The deleted sync.

        Raises:
        ------
            SyncNotFoundException: If the sync is not found.
        """
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx)
        if not sync:
            raise SyncNotFoundException("Sync not found")

        if delete_data:
            # TODO: Implement data deletion logic, should be part of destination interface
            pass

        return await crud.sync.remove(db=db, id=sync_id, ctx=ctx, uow=uow)

    async def _create_and_run_sync_internal(
        self,
        sync_in: schemas.SyncCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Internal helper method for creating and running a sync.

        Args:
        ----
            sync_in (schemas.SyncCreate): The sync to create.
            ctx (ApiContext): The API context.
            uow (UnitOfWork): The unit of work to use.

        Returns:
        -------
            tuple[schemas.Sync, Optional[schemas.SyncJob]]: The created sync and job if run.
        """
        sync = await self.create(db=uow.session, sync=sync_in.to_base(), ctx=ctx, uow=uow)
        await uow.session.flush()
        sync_schema = schemas.Sync.model_validate(sync)

        sync_job = None
        if sync_in.run_immediately:
            sync_job_create = schemas.SyncJobCreate(sync_id=sync_schema.id)
            sync_job = await crud.sync_job.create(
                db=uow.session, obj_in=sync_job_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()
            await uow.session.refresh(sync_job)
            sync_job = schemas.SyncJob.model_validate(sync_job)

        return sync_schema, sync_job

    async def create_and_run_sync(
        self,
        db: AsyncSession,
        sync_in: schemas.SyncCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Create a new sync and optionally run it immediately.

        TODO: Make it run immediately if sync_in.run_immediately is True
            Currently, it expects the FastAPI endpoint to trigger the run
            in background. This should be replaced by decentralized orchestration.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_in (schemas.SyncCreate): The sync to create.
            ctx (ApiContext): The API context.
            uow (Optional[UnitOfWork]): Existing unit of work if provided, otherwise create new one.

        Returns:
        -------
            tuple[schemas.Sync, Optional[schemas.SyncJob]]: The created sync and job if run.
        """
        if uow is not None:
            # Use the provided UnitOfWork without managing its lifecycle
            return await self._create_and_run_sync_internal(sync_in, ctx, uow)
        else:
            # Create and manage our own UnitOfWork
            async with UnitOfWork(db) as local_uow:
                result = await self._create_and_run_sync_internal(sync_in, ctx, local_uow)
                await local_uow.commit()
                return result

    async def trigger_sync_run(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> tuple[schemas.Sync, schemas.SyncJob, schemas.SyncDag]:
        """Trigger a sync run.

        TODO: Does not actually run the sync, just creates the job and DAG.
        The actual sync run is triggered by background task in the endpoint.
        At some point this method will distribute to task queue.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync to run.
            ctx (ApiContext): The API context.

        Returns:
        -------
            tuple[schemas.Sync, schemas.SyncJob, schemas.SyncDag]: The sync, job, and DAG.

        Raises:
        ------
            SyncNotFoundException: If the sync is not found.
        """
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=True)
        if not sync:
            raise SyncNotFoundException("Sync not found")

        sync_schema = schemas.Sync.model_validate(sync)

        sync_job_in = schemas.SyncJobCreate(sync_id=sync_id)
        sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, ctx=ctx)
        await db.flush()
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)

        sync_dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync_id, ctx=ctx)
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)

        return sync_schema, sync_job_schema, sync_dag_schema

    async def list_sync_jobs(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        sync_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[List[str]] = None,
    ) -> List[schemas.SyncJob]:
        """List sync jobs, either for all syncs or a specific sync.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (ApiContext): The API context.
            sync_id (Optional[UUID]): The specific sync ID, if any.
            skip (int): The number of jobs to skip.
            limit (int): The number of jobs to return.
            status (Optional[List[str]]): Filter by job status.

        Returns:
        -------
            List[schemas.SyncJob]: A list of sync jobs.

        Raises:
        ------
            SyncNotFoundException: If the sync is not found (when sync_id is provided).
        """
        if sync_id:
            sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx)
            if not sync:
                raise SyncNotFoundException("Sync not found")
            return await crud.sync_job.get_all_by_sync_id(db=db, sync_id=sync_id)
        else:
            return await crud.sync_job.get_all_jobs(
                db=db, skip=skip, limit=limit, ctx=ctx, status=status
            )

    async def get_sync_job(
        self,
        db: AsyncSession,
        job_id: UUID,
        ctx: ApiContext,
        sync_id: Optional[UUID] = None,
    ) -> schemas.SyncJob:
        """Get a specific sync job.

        Args:
        ----
            db (AsyncSession): The database session.
            job_id (UUID): The ID of the job to get.
            ctx (ApiContext): The API context.
            sync_id (Optional[UUID]): The sync ID for validation.

        Returns:
        -------
            schemas.SyncJob: The sync job.

        Raises:
        ------
            SyncJobNotFoundException: If the job is not found or doesn't match the sync.
        """
        sync_job = await crud.sync_job.get(db=db, id=job_id, ctx=ctx)
        if not sync_job or (sync_id and sync_job.sync_id != sync_id):
            raise SyncJobNotFoundException("Sync job not found")
        return sync_job

    async def get_sync_dag(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SyncDag:
        """Get the DAG for a specific sync.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync.
            ctx (ApiContext): The API context.

        Returns:
        -------
            schemas.SyncDag: The sync DAG.

        Raises:
        ------
            SyncDagNotFoundException: If the DAG is not found.
        """
        dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync_id, ctx=ctx)
        if not dag:
            raise SyncDagNotFoundException(f"DAG for sync {sync_id} not found")
        return dag

    async def update_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        sync_update: schemas.SyncUpdate,
        ctx: ApiContext,
    ) -> schemas.Sync:
        """Update a sync configuration.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync to update.
            sync_update (schemas.SyncUpdate): The sync update data.
            ctx (ApiContext): The API context.

        Returns:
        -------
            schemas.Sync: The updated sync.

        Raises:
        ------
            SyncNotFoundException: If the sync is not found.
        """
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        if not sync:
            raise SyncNotFoundException(f"Sync {sync_id} not found")

        await crud.sync.update(db=db, db_obj=sync, obj_in=sync_update, ctx=ctx)
        updated_sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=True)
        return updated_sync

    async def create_minute_level_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cron_expression: str,
        auth_context: AuthContext,
    ) -> schemas.ScheduleResponse:
        """Create a minute-level schedule for incremental sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cron_expression: Cron expression (e.g., "*/1 * * * *")
            auth_context: Authentication context

        Returns:
            Schedule response with status and message
        """
        # Get the sync with all required data
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=True
        )
        if not sync:
            raise SyncNotFoundException(f"Sync {sync_id} not found")

        # Get the source connection separately
        source_connection = await crud.source_connection.get_by_sync_id(
            db=db, sync_id=sync_id, auth_context=auth_context
        )
        if not source_connection:
            raise NotFoundException(f"Source connection for sync {sync_id} not found")

        # Get required related data
        dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync_id, auth_context=auth_context)
        if not dag:
            raise SyncDagNotFoundException(f"Sync DAG for sync {sync_id} not found")

        collection = await crud.collection.get_by_readable_id(
            db=db, readable_id=source_connection.readable_collection_id, auth_context=auth_context
        )
        if not collection:
            raise CollectionNotFoundException(
                f"Collection {source_connection.readable_collection_id} not found"
            )

        # Create a sync job for the schedule
        sync_job_create = schemas.SyncJobCreate(sync_id=sync_id)
        sync_job = await crud.sync_job.create(
            db=db, obj_in=sync_job_create, auth_context=auth_context
        )

        # Convert to dict format for Temporal
        # Only refresh SQLAlchemy models (not Pydantic schemas)
        await db.refresh(dag)
        await db.refresh(sync_job)
        await db.refresh(collection)
        await db.refresh(source_connection)

        sync_dict = schemas.Sync.model_validate(sync).model_dump(mode="json")
        sync_job_dict = schemas.SyncJob.model_validate(sync_job).model_dump(mode="json")
        dag_dict = schemas.SyncDag.model_validate(dag).model_dump(mode="json")
        collection_dict = schemas.Collection.model_validate(collection).model_dump(mode="json")
        source_connection_dict = schemas.SourceConnection.model_validate(
            source_connection
        ).model_dump(mode="json")
        user_dict = {
            "email": auth_context.user.email,
            "organization_id": auth_context.organization_id,
            "auth_method": auth_context.auth_method,
        }

        try:
            # Create the Temporal schedule
            schedule_id = await temporal_schedule_service.create_minute_level_schedule(
                sync_id=sync_id,
                cron_expression=cron_expression,
                sync_dict=sync_dict,
                sync_job_dict=sync_job_dict,
                sync_dag_dict=dag_dict,
                collection_dict=collection_dict,
                source_connection_dict=source_connection_dict,
                user_dict=user_dict,
                db=db,
                auth_context=auth_context,
            )

            return schemas.ScheduleResponse(
                schedule_id=schedule_id,
                status="created",
                message=f"Minute-level schedule created successfully with cron: {cron_expression}",
            )

        except Exception as e:
            logger.error(f"Failed to create minute-level schedule for sync {sync_id}: {e}")
            # Check if the error is because schedule already exists
            if "Schedule already running" in str(e):
                # Get the existing schedule info
                existing_schedule = await temporal_schedule_service.get_sync_schedule_info(
                    sync_id=sync_id, db=db, auth_context=auth_context
                )
                if existing_schedule:
                    return schemas.ScheduleResponse(
                        schedule_id=existing_schedule.get("schedule_id", "unknown"),
                        status="exists",
                        message=(
                            f"Schedule already exists with cron: "
                            f"{existing_schedule.get('cron_expressions', [cron_expression])[0]}"
                        ),
                    )

            raise MinuteLevelScheduleException(
                f"Failed to create minute-level schedule: {str(e)}"
            ) from e

    async def update_minute_level_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cron_expression: str,
        auth_context: AuthContext,
    ) -> schemas.ScheduleResponse:
        """Update an existing minute-level schedule.

        Args:
            db: Database session
            sync_id: The sync ID
            cron_expression: New cron expression
            auth_context: Authentication context

        Returns:
            Schedule response with status and message
        """
        # Get the sync to check if it has a temporal schedule
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=False
        )
        if not sync:
            raise SyncNotFoundException(f"Sync {sync_id} not found")

        if not sync.temporal_schedule_id:
            raise InvalidScheduleOperationException(
                "Sync does not have a minute-level schedule to update"
            )

        user_dict = {
            "email": auth_context.user.email,
            "organization_id": auth_context.organization_id,
            "auth_method": auth_context.auth_method,
        }

        try:
            # Update the Temporal schedule
            await temporal_schedule_service.update_schedule(
                schedule_id=sync.temporal_schedule_id,
                cron_expression=cron_expression,
                sync_id=sync_id,
                user_dict=user_dict,
                db=db,
            )

            return schemas.ScheduleResponse(
                schedule_id=sync.temporal_schedule_id,
                status="updated",
                message=f"Minute-level schedule updated successfully with cron: {cron_expression}",
            )

        except Exception as e:
            logger.error(f"Failed to update minute-level schedule for sync {sync_id}: {e}")
            raise ScheduleOperationException(
                f"Failed to update minute-level schedule: {str(e)}"
            ) from e

    async def pause_minute_level_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        auth_context: AuthContext,
    ) -> schemas.ScheduleResponse:
        """Pause a minute-level schedule.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Schedule response with status and message
        """
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=False
        )
        if not sync:
            raise SyncNotFoundException("Sync not found")

        if not sync.temporal_schedule_id:
            raise ScheduleNotExistsException("Sync does not have a minute-level schedule to pause")

        user_dict = {
            "email": auth_context.user.email,
            "organization_id": auth_context.organization_id,
            "auth_method": auth_context.auth_method,
        }

        try:
            await temporal_schedule_service.pause_schedule(
                schedule_id=sync.temporal_schedule_id,
                sync_id=sync_id,
                user_dict=user_dict,
                db=db,
            )

            return schemas.ScheduleResponse(
                schedule_id=sync.temporal_schedule_id,
                status="paused",
                message="Minute-level schedule paused successfully",
            )

        except Exception as e:
            logger.error(f"Failed to pause minute-level schedule for sync {sync_id}: {e}")
            raise ScheduleOperationException(
                f"Failed to pause minute-level schedule: {str(e)}"
            ) from e

    async def resume_minute_level_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        auth_context: AuthContext,
    ) -> schemas.ScheduleResponse:
        """Resume a paused minute-level schedule.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Schedule response with status and message
        """
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=False
        )
        if not sync:
            raise SyncNotFoundException("Sync not found")

        if not sync.temporal_schedule_id:
            raise ScheduleNotExistsException("Sync does not have a minute-level schedule to resume")

        user_dict = {
            "email": auth_context.user.email,
            "organization_id": auth_context.organization_id,
            "auth_method": auth_context.auth_method,
        }

        try:
            await temporal_schedule_service.resume_schedule(
                schedule_id=sync.temporal_schedule_id,
                sync_id=sync_id,
                user_dict=user_dict,
                db=db,
            )

            return schemas.ScheduleResponse(
                schedule_id=sync.temporal_schedule_id,
                status="resumed",
                message="Minute-level schedule resumed successfully",
            )

        except Exception as e:
            logger.error(f"Failed to resume minute-level schedule for sync {sync_id}: {e}")
            raise ScheduleOperationException(
                f"Failed to resume minute-level schedule: {str(e)}"
            ) from e

    async def delete_minute_level_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        auth_context: AuthContext,
    ) -> schemas.ScheduleResponse:
        """Delete a minute-level schedule.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Schedule response with status and message
        """
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=False
        )
        if not sync:
            raise SyncNotFoundException("Sync not found")

        if not sync.temporal_schedule_id:
            raise ScheduleNotExistsException("Sync does not have a minute-level schedule to delete")

        user_dict = {
            "email": auth_context.user.email,
            "organization_id": auth_context.organization_id,
            "auth_method": auth_context.auth_method,
        }

        try:
            await temporal_schedule_service.delete_schedule(
                schedule_id=sync.temporal_schedule_id,
                sync_id=sync_id,
                user_dict=user_dict,
                db=db,
            )

            return schemas.ScheduleResponse(
                schedule_id=sync.temporal_schedule_id,
                status="deleted",
                message="Minute-level schedule deleted successfully",
            )

        except Exception as e:
            logger.error(f"Failed to delete minute-level schedule for sync {sync_id}: {e}")
            raise ScheduleOperationException(
                f"Failed to delete minute-level schedule: {str(e)}"
            ) from e

    async def get_minute_level_schedule_info(
        self,
        db: AsyncSession,
        sync_id: UUID,
        auth_context: AuthContext,
    ) -> Optional[dict]:
        """Get information about a minute-level schedule.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Schedule information if exists, None otherwise
        """
        # Verify sync exists and user has access
        sync = await crud.sync.get(
            db=db, id=sync_id, auth_context=auth_context, with_connections=False
        )
        if not sync:
            raise SyncNotFoundException("Sync not found")

        return await temporal_schedule_service.get_sync_schedule_info(sync_id, db, auth_context)


sync_service = SyncService()
