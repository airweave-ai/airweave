"""API endpoints for managing syncs."""

import asyncio
from typing import AsyncGenerator, List, Optional, Union
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.core.sync_service import sync_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.sync.pubsub import sync_pubsub

router = TrailingSlashRouter()


@router.get("/", response_model=Union[list[schemas.Sync], list[schemas.SyncWithSourceConnection]])
async def list_syncs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    with_source_connection: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Sync] | list[schemas.SyncWithSourceConnection]:
    """List all syncs for the current user.

    Args:
    -----
        db: The database session
        skip: The number of syncs to skip
        limit: The number of syncs to return
        with_source_connection: Whether to include the source connection in the response
        user: The current user

    Returns:
    --------
        list[schemas.Sync] | list[schemas.SyncWithSourceConnection]: A list of syncs
    """
    if with_source_connection:
        syncs = await crud.sync.get_all_syncs_join_with_source_connection(db=db, current_user=user)
    else:
        syncs = await crud.sync.get_all_for_user(db=db, current_user=user, skip=skip, limit=limit)
    return syncs


@router.get("/jobs", response_model=list[schemas.SyncJob])
async def list_all_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[List[str]] = Query(None, description="Filter by job status"),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.SyncJob]:
    """List all sync jobs across all syncs.

    Args:
    -----
        db: The database session
        skip: The number of jobs to skip
        limit: The number of jobs to return
        status: Filter by job status
        user: The current user

    Returns:
    --------
        list[schemas.SyncJob]: A list of all sync jobs
    """
    jobs = await crud.sync_job.get_all_jobs(
        db=db, skip=skip, limit=limit, current_user=user, status=status
    )
    return jobs


@router.get("/{sync_id}", response_model=schemas.Sync)
async def get_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Get a specific sync by ID.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to get
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The sync
    """
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")
    return sync


@router.post("/", response_model=schemas.Sync)
async def create_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_in: schemas.SyncCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.Sync:
    """Create a new sync configuration.

    Args:
    -----
        db: The database session
        sync_in: The sync to create
        user: The current user
        background_tasks: The background tasks

    Returns:
    --------
        sync (schemas.Sync): The created sync
    """
    async with UnitOfWork(db) as uow:
        sync = await sync_service.create(db=db, sync=sync_in.to_base(), current_user=user, uow=uow)
        await uow.session.flush()
        sync_schema = schemas.Sync.model_validate(sync)
        if sync_in.run_immediately:
            sync_job_create = schemas.SyncJobCreate(sync_id=sync_schema.id)
            sync_job = await crud.sync_job.create(
                db=db, obj_in=sync_job_create, current_user=user, uow=uow
            )
            await uow.commit()
            await uow.session.refresh(sync_job)
            # Add background task to run the sync
            sync_job_schema = schemas.SyncJob.model_validate(sync_job)
            background_tasks.add_task(sync_service.run, sync_schema, sync_job_schema, user)
        await uow.commit()
    return sync


@router.delete("/{sync_id}", response_model=schemas.Sync)
async def delete_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    delete_data: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Delete a sync configuration and optionally its associated data.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to delete
        delete_data: Whether to delete the data associated with the sync
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The deleted sync
    """
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    if delete_data:
        # TODO: Implement data deletion logic, should be part of destination interface
        pass

    return await crud.sync.remove(db=db, id=sync_id, current_user=user)


@router.post("/{sync_id}/run", response_model=schemas.SyncJob)
async def run_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SyncJob:
    """Trigger a sync run.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to run
        user: The current user
        background_tasks: The background tasks

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user, with_connections=True)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    sync_schema = schemas.Sync.model_validate(sync)

    sync_job_in = schemas.SyncJobCreate(sync_id=sync_id)
    sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, current_user=user)
    sync_job_schema = schemas.SyncJob.model_validate(sync_job)

    sync_dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync_id, current_user=user)
    sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)

    user_schema = schemas.User.model_validate(user)

    # will be swapped for redis queue
    background_tasks.add_task(
        sync_service.run, sync_schema, sync_job_schema, sync_dag_schema, user_schema
    )

    return sync_job


@router.get("/{sync_id}/jobs", response_model=list[schemas.SyncJob])
async def list_sync_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.SyncJob]:
    """List all jobs for a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        user: The current user

    Returns:
    --------
        list[schemas.SyncJob]: A list of sync jobs
    """
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    return await crud.sync_job.get_all_by_sync_id(db=db, sync_id=sync_id)


@router.get("/{sync_id}/job/{job_id}", response_model=schemas.SyncJob)
async def get_sync_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    job_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncJob:
    """Get details of a specific sync job.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        job_id: The ID of the job to get
        user: The current user

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    sync_job = await crud.sync_job.get(db=db, id=job_id, current_user=user)
    if not sync_job or sync_job.sync_id != sync_id:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return sync_job


@router.get("/job/{job_id}/subscribe")
async def subscribe_sync_job(
    job_id: UUID,
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint to subscribe to a sync job's progress.

    Args:
    -----
        job_id: The ID of the job to subscribe to
        request: The request object
        db: The database session

    Returns:
    --------
        StreamingResponse: The streaming response
    """
    # Get auth token from query parameter

    if settings.AUTH_ENABLED:
        token = request.query_params.get("token")
        if not token:
            logger.warning("SSE connection attempt without token")
            raise HTTPException(status_code=401, detail="Missing authentication token")

        # Authenticate the user from token parameter
        from airweave.api.deps import get_user_from_token

        user = await get_user_from_token(token, db)
        if not user:
            logger.warning(f"SSE connection with invalid token: {token[:10]}...")
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        logger.info(f"SSE sync subscription authenticated for user: {user.id}, job: {job_id}")

    queue = await sync_pubsub.subscribe(job_id)

    if not queue:
        raise HTTPException(status_code=404, detail="Sync job not found or completed")

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    update = await queue.get()
                    # Proper SSE format requires each message to start with "data: "
                    # and end with two newlines
                    yield f"data: {update.model_dump_json()}\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            sync_pubsub.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Important for nginx
        },
    )


@router.get("/{sync_id}/dag", response_model=schemas.SyncDag)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncDag:
    """Get the DAG for a specific sync."""
    dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync_id, current_user=user)
    if not dag:
        raise HTTPException(status_code=404, detail=f"DAG for sync {sync_id} not found")
    return dag


@router.patch("/{sync_id}", response_model=schemas.Sync)
async def update_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    sync_update: schemas.SyncUpdate = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Update a sync configuration.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to update
        sync_update: The sync update data
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The updated sync
    """
    sync = await crud.sync.get(db=db, id=sync_id, current_user=user, with_connections=False)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    updated_sync = await crud.sync.update(db=db, db_obj=sync, obj_in=sync_update, current_user=user)
    updated_sync = await crud.sync.get(db=db, id=sync_id, current_user=user, with_connections=True)
    return updated_sync
