"""API endpoints for managing syncs."""

import asyncio
import json
from typing import AsyncGenerator, List, Optional, Union
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.sync_service import sync_service
from airweave.platform.sync.pubsub import sync_pubsub

router = TrailingSlashRouter()


@router.get("/", response_model=Union[list[schemas.Sync], list[schemas.SyncWithSourceConnection]])
async def list_syncs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    with_source_connection: bool = False,
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.Sync] | list[schemas.SyncWithSourceConnection]:
    """List all syncs for the current user.

    Args:
    -----
        db: The database session
        skip: The number of syncs to skip
        limit: The number of syncs to return
        with_source_connection: Whether to include the source connection in the response
        ctx: The current authentication context

    Returns:
    --------
        list[schemas.Sync] | list[schemas.SyncWithSourceConnection]: A list of syncs
    """
    return await sync_service.list_syncs(
        db=db,
        ctx=ctx,
        skip=skip,
        limit=limit,
        with_source_connection=with_source_connection,
    )


@router.get("/jobs", response_model=list[schemas.SyncJob])
async def list_all_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[List[str]] = Query(None, description="Filter by job status"),
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.SyncJob]:
    """List all jobs across all syncs.

    Args:
    -----
        db: The database session
        skip: The number of jobs to skip
        limit: The number of jobs to return
        status: Filter by job status
        ctx: The current authentication context

    Returns:
    --------
        list[schemas.SyncJob]: A list of all sync jobs
    """
    return await sync_service.list_sync_jobs(db=db, ctx=ctx, skip=skip, limit=limit, status=status)


@router.get("/{sync_id}", response_model=schemas.Sync)
async def get_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Sync:
    """Get a specific sync by ID.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to get
        ctx: The current authentication context

    Returns:
    --------
        sync (schemas.Sync): The sync
    """
    return await sync_service.get_sync(db=db, sync_id=sync_id, ctx=ctx)


@router.post("/", response_model=schemas.Sync)
async def create_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_in: schemas.SyncCreate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    background_tasks: BackgroundTasks,
) -> schemas.Sync:
    """Create a new sync configuration.

    Args:
    -----
        db: The database session
        sync_in: The sync to create
        ctx: The current authentication context
        background_tasks: The background tasks

    Returns:
    --------
        sync (schemas.Sync): The created sync
    """
    # Create the sync and sync job - kinda, not really, we'll do that in the background
    sync, sync_job = await sync_service.create_and_run_sync(db=db, sync_in=sync_in, ctx=ctx)
    source_connection = await crud.source_connection.get(
        db=db, id=sync_in.source_connection_id, ctx=ctx
    )
    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection.readable_collection_id, ctx=ctx
    )
    collection = schemas.Collection.model_validate(collection, from_attributes=True)

    source_connection = schemas.SourceConnection.model_validate(
        source_connection, from_attributes=True
    )

    # If job was created and should run immediately, start it in background
    if sync_job and sync_in.run_immediately:
        sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync.id, ctx=ctx)
        background_tasks.add_task(
            sync_service.run, sync, sync_job, sync_dag, collection, source_connection, ctx
        )

    return sync


@router.delete("/{sync_id}", response_model=schemas.Sync)
async def delete_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    delete_data: bool = False,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Sync:
    """Delete a sync configuration and optionally its associated data.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to delete
        delete_data: Whether to delete the data associated with the sync
        ctx: The current authentication context

    Returns:
    --------
        sync (schemas.Sync): The deleted sync
    """
    return await sync_service.delete_sync(db=db, sync_id=sync_id, ctx=ctx, delete_data=delete_data)


@router.post("/{sync_id}/run", response_model=schemas.SyncJob)
async def run_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    background_tasks: BackgroundTasks,
) -> schemas.SyncJob:
    """Trigger a sync run.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to run
        ctx: The current authentication context
        background_tasks: The background tasks

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    # Trigger the sync run - kinda, not really, we'll do that in the background
    sync, sync_job, sync_dag = await sync_service.trigger_sync_run(db=db, sync_id=sync_id, ctx=ctx)

    # Start the sync job in the background - this is where the sync actually runs
    background_tasks.add_task(sync_service.run, sync, sync_job, sync_dag, ctx)

    return sync_job


@router.get("/{sync_id}/jobs", response_model=list[schemas.SyncJob])
async def list_sync_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.SyncJob]:
    """List all jobs for a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        ctx: The current authentication context

    Returns:
    --------
        list[schemas.SyncJob]: A list of sync jobs
    """
    return await sync_service.list_sync_jobs(db=db, ctx=ctx, sync_id=sync_id)


@router.get("/{sync_id}/job/{job_id}", response_model=schemas.SyncJob)
async def get_sync_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    job_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SyncJob:
    """Get details of a specific sync job.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        job_id: The ID of the job to get
        ctx: The current authentication context

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    return await sync_service.get_sync_job(db=db, job_id=job_id, ctx=ctx, sync_id=sync_id)


@router.get("/job/{job_id}/subscribe")
async def subscribe_sync_job(
    job_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),  # Standard dependency injection
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint to subscribe to a sync job's progress.

    Args:
    -----
        job_id: The ID of the job to subscribe to
        ctx: The API context
        db: The database session

    Returns:
    --------
        StreamingResponse: The streaming response
    """
    logger.info(f"SSE sync subscription authenticated for user: {ctx}, job: {job_id}")

    # Track active SSE connections
    connection_id = f"{ctx}:{job_id}:{asyncio.get_event_loop().time()}"

    # Check if Redis monitoring is enabled
    from airweave.core.redis_client import redis_client
    if not redis_client.is_enabled:
        # Return a simple response indicating monitoring is disabled
        async def disabled_event_stream() -> AsyncGenerator[str, None]:
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"
            yield f"data: {json.dumps({'type': 'info', 'message': 'Real-time monitoring is disabled. Please check sync status via API.'})}\n\n"
            # Keep connection alive with periodic heartbeats
            while True:
                await asyncio.sleep(30)
                yield 'data: {"type": "heartbeat"}\n\n'
        
        return StreamingResponse(
            disabled_event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
            },
        )

    # Get a new pubsub instance subscribed to this job
    pubsub = await sync_pubsub.subscribe(job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for message in pubsub.listen():
                # Check if we need to send a heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield 'data: {"type": "heartbeat"}\n\n'
                    last_heartbeat = current_time

                if message["type"] == "message":
                    # Parse and forward the sync progress update
                    yield f"data: {message['data']}\n\n"
                elif message["type"] == "subscribe":
                    # Log subscription confirmation
                    logger.info(f"SSE subscribed to job {job_id} for connection {connection_id}")

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for job {job_id}, connection: {connection_id}")
        except Exception as e:
            logger.error(f"SSE error for job {job_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Clean up when SSE connection closes
            try:
                await pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub for job {job_id}: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",  # Adjust for your CORS needs
        },
    )


@router.get("/{sync_id}/dag", response_model=schemas.SyncDag)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SyncDag:
    """Get the DAG for a specific sync."""
    return await sync_service.get_sync_dag(db=db, sync_id=sync_id, ctx=ctx)


@router.patch("/{sync_id}", response_model=schemas.Sync)
async def update_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    sync_update: schemas.SyncUpdate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Sync:
    """Update a sync configuration.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to update
        sync_update: The sync update data
        ctx: The current authentication context

    Returns:
    --------
        sync (schemas.Sync): The updated sync
    """
    return await sync_service.update_sync(db=db, sync_id=sync_id, sync_update=sync_update, ctx=ctx)


# Minute-level schedule endpoints
@router.post("/{sync_id}/minute-level-schedule", response_model=schemas.ScheduleResponse)
async def create_minute_level_schedule(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    config: schemas.MinuteLevelScheduleConfig = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ScheduleResponse:
    """Create a minute-level schedule for incremental sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to schedule
        config: The minute-level schedule configuration
        ctx: The current authentication context

    Returns:
    --------
        schemas.ScheduleResponse: The schedule response with status and message
    """
    return await sync_service.create_minute_level_schedule(
        db=db,
        sync_id=sync_id,
        cron_expression=config.cron_expression,
        ctx=ctx,
    )


@router.put("/{sync_id}/minute-level-schedule", response_model=schemas.ScheduleResponse)
async def update_minute_level_schedule(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    config: schemas.MinuteLevelScheduleConfig = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ScheduleResponse:
    """Update an existing minute-level schedule.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync
        config: The minute-level schedule configuration
        ctx: The current authentication context

    Returns:
    --------
        schemas.ScheduleResponse: The schedule response with status and message
    """
    return await sync_service.update_minute_level_schedule(
        db=db,
        sync_id=sync_id,
        cron_expression=config.cron_expression,
        ctx=ctx,
    )


@router.post("/{sync_id}/minute-level-schedule/pause", response_model=schemas.ScheduleResponse)
async def pause_minute_level_schedule(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ScheduleResponse:
    """Pause a minute-level schedule.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync
        ctx: The current authentication context

    Returns:
    --------
        schemas.ScheduleResponse: The schedule response with status and message
    """
    return await sync_service.pause_minute_level_schedule(db=db, sync_id=sync_id, ctx=ctx)


@router.post("/{sync_id}/minute-level-schedule/resume", response_model=schemas.ScheduleResponse)
async def resume_minute_level_schedule(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ScheduleResponse:
    """Resume a paused minute-level schedule.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync
        ctx: The current authentication context

    Returns:
    --------
        schemas.ScheduleResponse: The schedule response with status and message
    """
    return await sync_service.resume_minute_level_schedule(db=db, sync_id=sync_id, ctx=ctx)


@router.delete("/{sync_id}/minute-level-schedule", response_model=schemas.ScheduleResponse)
async def delete_minute_level_schedule(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ScheduleResponse:
    """Delete a minute-level schedule.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync
        ctx: The current authentication context

    Returns:
    --------
        schemas.ScheduleResponse: The schedule response with status and message
    """
    return await sync_service.delete_minute_level_schedule(db=db, sync_id=sync_id, ctx=ctx)


@router.get("/{sync_id}/minute-level-schedule")
async def get_minute_level_schedule_info(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Get information about a minute-level schedule.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync
        ctx: The current authentication context

    Returns:
    --------
        dict: Schedule information if exists

    Raises:
    --------
        404: If no minute-level schedule exists for the sync
    """
    schedule_info = await sync_service.get_minute_level_schedule_info(
        db=db, sync_id=sync_id, ctx=ctx
    )

    if schedule_info is None:
        raise HTTPException(status_code=404, detail="No minute-level schedule found for this sync")

    return schedule_info
