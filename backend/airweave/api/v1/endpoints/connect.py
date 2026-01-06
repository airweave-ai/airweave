"""Connect session endpoints for frontend integration flows.

These endpoints enable short-lived session tokens that allow end customers
to manage source connections via a hosted UI (Plaid-style Connect modal).

Flow:
1. Customer server creates session via POST /connect/sessions (API key auth)
2. Frontend SDK uses session_token to:
   - GET /connect/sessions - verify session and get context
   - GET /connect/source-connections - list connections in collection
   - DELETE /connect/source-connections/{id} - remove a connection
"""

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics.contextual_service import (
    AnalyticsContext,
    ContextualAnalyticsService,
    RequestHeaders,
)
from airweave.analytics.service import analytics
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.core.source_connection_service import source_connection_service
from airweave.db.session import get_db
from airweave.platform.auth.state import make_state
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)

router = TrailingSlashRouter()


async def _build_session_context(
    db: AsyncSession,
    session: ConnectSessionContext,
) -> ApiContext:
    """Build an ApiContext from a connect session for service calls.

    This creates a minimal context that allows the session-authenticated
    endpoints to use existing services like source_connection_service.

    Args:
        db: Database session
        session: Decoded connect session context

    Returns:
        ApiContext scoped to the session's organization
    """
    # Fetch organization - skip access validation since session already validated
    org = await crud.organization.get(
        db, id=session.organization_id, skip_access_validation=True, enrich=True
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    request_id = str(uuid4())

    session_logger = logger.with_context(
        request_id=request_id,
        session_id=str(session.session_id),
        organization_id=str(session.organization_id),
        end_user_id=session.end_user_id,
        context_base="connect_session",
    )

    analytics_context = AnalyticsContext(
        auth_method="connect_session",
        organization_id=str(org.id),
        organization_name=org.name,
        request_id=request_id,
        user_id=session.end_user_id,  # Use end_user_id for analytics tracking
    )

    analytics_service = ContextualAnalyticsService(
        base_service=analytics,
        context=analytics_context,
        headers=RequestHeaders(request_id=request_id),
    )

    return ApiContext(
        request_id=request_id,
        organization=org,
        user=None,
        auth_method=AuthMethod.API_KEY,  # Treat as API key level access
        auth_metadata={
            "connect_session_id": str(session.session_id),
            "end_user_id": session.end_user_id,
        },
        logger=session_logger,
        analytics=analytics_service,
    )


@router.post("/sessions", response_model=ConnectSessionResponse)
async def create_session(
    session_in: ConnectSessionCreate,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> ConnectSessionResponse:
    """Create a connect session token for frontend integration flows.

    This endpoint is called server-to-server using your API key to create
    a short-lived session token. Pass this token to your frontend SDK
    to enable the Connect modal.

    The session token:
    - Expires in 10 minutes
    - Grants access only to the specified collection
    - Can be restricted to specific integrations via allowed_integrations
    - Supports different modes: all, connect, manage, reauth
    """
    # Validate collection exists and belongs to this organization
    collection = await crud.collection.get_by_readable_id(
        db, readable_id=session_in.readable_collection_id, ctx=ctx
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Generate unique session ID
    session_id = uuid4()

    # Create HMAC-signed token using existing state module
    token = make_state(
        {
            "sid": str(session_id),
            "oid": str(ctx.organization.id),
            "cid": session_in.readable_collection_id,
            "int": session_in.allowed_integrations,
            "mode": session_in.mode.value,
            "uid": session_in.end_user_id,
        }
    )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    if ctx.analytics:
        ctx.analytics.track_event(
            "connect_session_created",
            {
                "session_id": str(session_id),
                "collection_id": session_in.readable_collection_id,
                "mode": session_in.mode.value,
                "end_user_id": session_in.end_user_id,
                "allowed_integrations": session_in.allowed_integrations,
            },
        )

    ctx.logger.info(
        f"Created connect session {session_id} for collection {session_in.readable_collection_id}"
        + (f" (end_user: {session_in.end_user_id})" if session_in.end_user_id else "")
    )

    return ConnectSessionResponse(
        session_id=session_id,
        session_token=token,
        expires_at=expires_at,
    )


@router.get("/sessions", response_model=ConnectSessionContext)
async def get_session(
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> ConnectSessionContext:
    """Get the current session context from a session token.

    Use this endpoint to verify a session token is valid and retrieve
    the session details (collection, allowed integrations, mode, expiry).

    Authentication: Bearer <session_token>
    """
    return session


@router.get("/source-connections", response_model=List[schemas.SourceConnectionListItem])
async def list_source_connections(
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections in the session's collection.

    Returns all source connections within the collection that this session
    grants access to. If allowed_integrations was specified when creating
    the session, only connections of those types are returned.

    Authentication: Bearer <session_token>
    """
    # Build context for service call
    ctx = await _build_session_context(db, session)

    # Get connections for the collection
    connections = await source_connection_service.list(
        db,
        ctx=ctx,
        readable_collection_id=session.collection_id,
    )

    # Filter by allowed_integrations if specified
    if session.allowed_integrations:
        connections = [c for c in connections if c.short_name in session.allowed_integrations]

    return connections


@router.delete("/source-connections/{connection_id}", response_model=schemas.SourceConnection)
async def delete_source_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> schemas.SourceConnection:
    """Delete a source connection.

    Removes a source connection and all its synced data. This action:
    - Revokes any OAuth tokens
    - Cancels running sync jobs
    - Deletes synced entities from the destination

    The connection must belong to the session's collection.

    Authentication: Bearer <session_token>
    """
    # Build context for service call
    ctx = await _build_session_context(db, session)

    # Get the connection to verify it belongs to this session's collection
    try:
        connection = await source_connection_service.get(db, id=connection_id, ctx=ctx)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Source connection not found") from e
        raise

    # Verify connection belongs to session's collection
    if connection.readable_collection_id != session.collection_id:
        raise HTTPException(
            status_code=403, detail="Source connection does not belong to this session's collection"
        )

    # Check if allowed_integrations restricts access to this connection type
    if session.allowed_integrations and connection.short_name not in session.allowed_integrations:
        raise HTTPException(
            status_code=403, detail="Session does not have access to this integration type"
        )

    ctx.logger.info(
        f"Deleting source connection {connection_id} via connect session {session.session_id}"
    )

    if ctx.analytics:
        ctx.analytics.track_event(
            "connect_source_connection_deleted",
            {
                "connection_id": str(connection_id),
                "session_id": str(session.session_id),
                "collection_id": session.collection_id,
                "end_user_id": session.end_user_id,
                "short_name": connection.short_name,
            },
        )

    # Delete the connection using existing service
    return await source_connection_service.delete(db, id=connection_id, ctx=ctx)
