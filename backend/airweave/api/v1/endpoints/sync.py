"""API endpoints for managing syncs."""

import asyncio
import json
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.protocols import PubSub
from airweave.core.sync_service import sync_service
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol

router = TrailingSlashRouter()


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
    dense_embedder: DenseEmbedderProtocol = Inject(DenseEmbedderProtocol),
    sparse_embedder: SparseEmbedderProtocol = Inject(SparseEmbedderProtocol),
) -> schemas.Sync:
    """Create a new sync configuration.

    Args:
    -----
        db: The database session
        sync_in: The sync to create
        ctx: The current authentication context
        background_tasks: The background tasks
        dense_embedder: The dense embedder protocol instance
        sparse_embedder: The sparse embedder protocol instance

    Returns:
    --------
        sync (schemas.Sync): The created sync
    """
    sync, sync_job = await sync_service.create_and_run_sync(db=db, sync_in=sync_in, ctx=ctx)
    source_connection = await crud.source_connection.get(
        db=db, id=sync_in.source_connection_id, ctx=ctx
    )
    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection.readable_collection_id, ctx=ctx
    )
    collection = schemas.CollectionRecord.model_validate(collection, from_attributes=True)

    source_connection = schemas.SourceConnection.model_validate(
        source_connection, from_attributes=True
    )

    if sync_job and sync_in.run_immediately:
        background_tasks.add_task(
            sync_service.run,
            sync,
            sync_job,
            collection,
            source_connection,
            ctx,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
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
    ctx: ApiContext = Depends(deps.get_context),
    pubsub: PubSub = Inject(PubSub),
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint to subscribe to a sync job's progress.

    Args:
    -----
        job_id: The ID of the job to subscribe to
        ctx: The API context
        pubsub: PubSub adapter for event streaming

    Returns:
    --------
        StreamingResponse: The streaming response
    """
    logger.info(f"SSE sync subscription authenticated for user: {ctx}, job: {job_id}")

    # Track active SSE connections
    connection_id = f"{ctx}:{job_id}:{asyncio.get_event_loop().time()}"

    ps = await pubsub.subscribe("sync_job", job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for message in ps.listen():
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
            try:
                await ps.close()
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


@router.get("/job/{job_id}/subscribe-state")
async def subscribe_entity_state(
    job_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    pubsub: PubSub = Inject(PubSub),
) -> StreamingResponse:
    """SSE endpoint for total entity state updates during sync.

    Unlike the existing subscribe endpoint which provides differential progress updates,
    this endpoint provides absolute entity counts per type, making it ideal for
    real-time UI updates showing the current state of the data.

    Args:
    -----
        job_id: The ID of the job to subscribe to
        ctx: The API context
        pubsub: PubSub adapter for event streaming

    Returns:
    --------
        StreamingResponse: Server-sent events with entity state updates
    """
    logger.info(f"🎯 SSE entity state subscription for user: {ctx}, job: {job_id}")

    # Log the channel we're subscribing to
    channel = f"sync_job_state:{job_id}"
    logger.info(f"📡 Subscribing to Redis channel: {channel}")

    ps = await pubsub.subscribe("sync_job_state", job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            logger.info(f"Starting entity state event stream for job {job_id}")

            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30

            async for message in ps.listen():
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield 'data: {"type": "heartbeat"}\n\n'
                    last_heartbeat = current_time

                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                elif message["type"] == "subscribe":
                    logger.info(f"SSE subscribed to entity state channel for job {job_id}")

        except asyncio.CancelledError:
            logger.info(f"SSE entity state connection cancelled for job {job_id}")
        except Exception as e:
            logger.error(f"SSE entity state error for job {job_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            try:
                await ps.close()
            except Exception as e:
                logger.warning(f"Error closing entity state pubsub for job {job_id}: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
        },
    )


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
