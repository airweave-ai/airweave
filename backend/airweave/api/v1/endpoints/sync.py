"""API endpoints for sync SSE subscriptions."""

import asyncio
import json
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi.responses import StreamingResponse

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.protocols import PubSub

router = TrailingSlashRouter()


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

    connection_id = f"{ctx}:{job_id}:{asyncio.get_event_loop().time()}"

    ps = await pubsub.subscribe("sync_job", job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for message in ps.listen():
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield 'data: {"type": "heartbeat"}\n\n'
                    last_heartbeat = current_time

                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                elif message["type"] == "subscribe":
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
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
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
    logger.info(f"SSE entity state subscription for user: {ctx}, job: {job_id}")

    channel = f"sync_job_state:{job_id}"
    logger.info(f"Subscribing to Redis channel: {channel}")

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
