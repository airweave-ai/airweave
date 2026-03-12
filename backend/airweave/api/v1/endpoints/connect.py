"""Connect session endpoints for frontend integration flows.

Thin router — all business logic lives in domains/connect/service.py.

Flow:
1. Customer server creates session via POST /connect/sessions (API key auth)
2. Frontend SDK uses session_token to:
   - GET /connect/sessions/{session_id} - verify session and get context
   - GET /connect/sources - list available integrations
   - GET /connect/sources/{short_name} - get source details
   - POST /connect/source-connections - create a new connection
   - GET /connect/source-connections - list connections in collection
   - DELETE /connect/source-connections/{id} - remove a connection
   - GET /connect/source-connections/{id}/jobs - list sync jobs for connection
   - GET /connect/source-connections/{id}/subscribe - SSE for real-time sync progress
"""

import asyncio
import json
from typing import Any, AsyncGenerator, List
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.inject import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.protocols import PubSub
from airweave.db.session import get_db
from airweave.domains.connect.protocols import ConnectServiceProtocol
from airweave.domains.connect.types import SSE_HEARTBEAT_INTERVAL_SECONDS
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)

router = TrailingSlashRouter()


# =============================================================================
# Sources
# =============================================================================


@router.get("/sources", response_model=List[schemas.Source])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> List[schemas.Source]:
    """List available source integrations for the Connect session.

    Authentication: Bearer <session_token>
    """
    return await svc.list_sources(db, session)


@router.get("/sources/{short_name}", response_model=schemas.Source)
async def get_source(
    short_name: str = Path(
        ...,
        description="Technical identifier of the source type (e.g., 'github', 'stripe', 'slack')",
    ),
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> schemas.Source:
    """Get detailed information about a specific source integration.

    Authentication: Bearer <session_token>
    """
    return await svc.get_source(db, short_name, session)


# =============================================================================
# Sessions
# =============================================================================


@router.post("/sessions", response_model=ConnectSessionResponse)
async def create_session(
    session_in: ConnectSessionCreate,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> ConnectSessionResponse:
    """Create a connect session token for frontend integration flows.

    Called server-to-server using your API key.
    """
    return await svc.create_session(db, session_in, ctx)


@router.get("/sessions/{session_id}", response_model=ConnectSessionContext)
async def get_session(
    session_id: UUID,
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> ConnectSessionContext:
    """Get the current session context from a session token.

    Authentication: Bearer <session_token>
    """
    if session_id != session.session_id:
        raise HTTPException(status_code=403, detail="Session ID does not match token")
    return session


# =============================================================================
# Source Connections
# =============================================================================


@router.get("/source-connections", response_model=List[schemas.SourceConnectionListItem])
async def list_source_connections(
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections in the session's collection.

    Authentication: Bearer <session_token>
    """
    return await svc.list_source_connections(db, session)


@router.get("/source-connections/{connection_id}", response_model=schemas.SourceConnection)
async def get_source_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> schemas.SourceConnection:
    """Get a source connection by ID.

    Authentication: Bearer <session_token>
    """
    return await svc.get_source_connection(db, connection_id, session)


@router.delete("/source-connections/{connection_id}", response_model=schemas.SourceConnection)
async def delete_source_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> schemas.SourceConnection:
    """Delete a source connection.

    Authentication: Bearer <session_token>
    """
    return await svc.delete_source_connection(db, connection_id, session)


@router.post("/source-connections", response_model=schemas.SourceConnection)
async def create_source_connection(
    source_connection_in: schemas.SourceConnectionCreate,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    authorization: str = Header(..., alias="Authorization"),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> schemas.SourceConnection:
    """Create a new source connection via Connect session.

    Authentication: Bearer <session_token>
    """
    session_token = deps._extract_bearer_token(authorization)
    return await svc.create_source_connection(db, source_connection_in, session, session_token)


# =============================================================================
# Sync Jobs
# =============================================================================


@router.get(
    "/source-connections/{connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
)
async def get_connection_jobs(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
) -> List[schemas.SourceConnectionJob]:
    """Get sync jobs for a source connection.

    Authentication: Bearer <session_token>
    """
    return await svc.get_connection_jobs(db, connection_id, session)


# =============================================================================
# SSE
# =============================================================================


async def _sse_event_stream(
    ps: Any,
    job_id: UUID,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE events from a pubsub subscription.

    Args:
        ps: PubSub subscription object (has .listen() and .close()).
        job_id: Sync job ID to include in events.
    """
    try:
        yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

        last_heartbeat = asyncio.get_event_loop().time()

        async for message in ps.listen():
            current_time = asyncio.get_event_loop().time()
            if current_time - last_heartbeat > SSE_HEARTBEAT_INTERVAL_SECONDS:
                yield 'data: {"type": "heartbeat"}\n\n'
                last_heartbeat = current_time

            if message["type"] == "message":
                yield f"data: {message['data']}\n\n"
    except asyncio.CancelledError:
        logger.info(f"SSE connection cancelled for job {job_id}")
    except Exception as e:
        logger.error(f"SSE error for job {job_id}: {e}")
        detail = e.detail if isinstance(e, HTTPException) else "An unexpected error occurred"
        yield f"data: {json.dumps({'type': 'error', 'message': detail})}\n\n"
    finally:
        try:
            await ps.close()
        except Exception as e:
            logger.warning(f"Error closing pubsub for job {job_id}: {e}")


@router.get("/source-connections/{connection_id}/subscribe")
async def subscribe_to_connection_sync(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    svc: ConnectServiceProtocol = Inject(ConnectServiceProtocol),
    pubsub: PubSub = Inject(PubSub),
    sync_job_repo: SyncJobRepositoryProtocol = Inject(SyncJobRepositoryProtocol),
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time sync progress.

    Authentication: Bearer <session_token>
    """
    connection = await svc.get_source_connection(db, connection_id, session)

    if not connection.sync_id:
        raise HTTPException(status_code=404, detail="No sync configured for this connection")

    job = await sync_job_repo.get_latest_by_sync_id(  # type: ignore[call-arg]
        db, sync_id=connection.sync_id
    )
    if not job:
        raise HTTPException(status_code=404, detail="No sync jobs found for this connection")

    job_id = UUID(str(job.id))
    logger.info(f"SSE subscription: connection={connection_id}, job={job_id}")

    ps = await pubsub.subscribe("sync_job", job_id)

    return StreamingResponse(
        _sse_event_stream(ps, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
        },
    )
