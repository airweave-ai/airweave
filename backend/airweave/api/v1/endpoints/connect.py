"""Connect session endpoints for frontend integration flows.

These endpoints enable short-lived session tokens that allow end customers
to manage source connections via a hosted UI (Plaid-style Connect modal).

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

Note: OAuth callbacks are handled by /source-connections/callback which validates
the connect session token stored in init session overrides.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, FrozenSet, List, Optional
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, Path
from fastapi.responses import StreamingResponse
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
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.config import settings
from airweave.core.exceptions import RateLimitExceededException
from airweave.core.logging import logger
from airweave.core.pubsub import core_pubsub
from airweave.core.rate_limiter_service import RateLimiter
from airweave.core.shared_models import AuthMethod
from airweave.core.source_connection_service import source_connection_service
from airweave.db.session import get_db
from airweave.platform.auth.state import make_state
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)

router = TrailingSlashRouter()

# Mode permission sets
MODES_VIEW: FrozenSet[schemas.ConnectSessionMode] = frozenset(
    {
        schemas.ConnectSessionMode.ALL,
        schemas.ConnectSessionMode.MANAGE,
        schemas.ConnectSessionMode.REAUTH,
    }
)
MODES_CREATE: FrozenSet[schemas.ConnectSessionMode] = frozenset(
    {
        schemas.ConnectSessionMode.ALL,
        schemas.ConnectSessionMode.CONNECT,
    }
)
MODES_DELETE: FrozenSet[schemas.ConnectSessionMode] = frozenset(
    {
        schemas.ConnectSessionMode.ALL,
        schemas.ConnectSessionMode.MANAGE,
    }
)

# SSE configuration
SSE_HEARTBEAT_INTERVAL_SECONDS = 30


def _check_session_mode(
    session: ConnectSessionContext,
    allowed_modes: FrozenSet[schemas.ConnectSessionMode],
    operation: str,
) -> None:
    """Validate session mode allows the requested operation."""
    if session.mode not in allowed_modes:
        raise HTTPException(
            status_code=403,
            detail=f"Session mode does not allow {operation}",
        )


def _sanitize_sse_error(error: Exception) -> str:
    """Return a safe error message for SSE client consumption."""
    if isinstance(error, HTTPException):
        return error.detail
    return "An unexpected error occurred"


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

    ctx = ApiContext(
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

    # Enforce rate limiting using the org's billing plan (same limits as API key auth)
    try:
        await RateLimiter.check_rate_limit(ctx)
    except RateLimitExceededException:
        raise
    except Exception as e:
        # Fail open on unexpected errors (Redis down, etc.) - same pattern as deps.py
        session_logger.error(f"Connect rate limit check failed: {e}. Allowing request.")

    return ctx


async def _build_source_schema(
    source: schemas.Source,
    ctx: ApiContext,
) -> Optional[schemas.Source]:
    """Build a Source schema with auth_fields and config_fields.

    This mirrors the logic in /sources/ endpoint but uses the Connect session context.

    Args:
        source: Source model from database
        ctx: API context for feature flag filtering

    Returns:
        Source schema with populated fields, or None if source is invalid
    """
    try:
        # Config class is always required
        if not source.config_class:
            return None

        # Auth fields - only for sources with auth_config_class (DIRECT auth)
        auth_fields = Fields(fields=[])
        if source.auth_config_class:
            try:
                auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
                auth_fields = Fields.from_config_class(auth_config_class)
            except AttributeError:
                return None

        # Get config fields
        try:
            config_class = resource_locator.get_config(source.config_class)
            config_fields_unfiltered = Fields.from_config_class(config_class)

            # Filter config fields based on organization's enabled features
            enabled_features = ctx.organization.enabled_features or []
            config_fields = config_fields_unfiltered.filter_by_features(enabled_features)
        except AttributeError:
            return None

        # Get supported auth providers
        supported_auth_providers = auth_provider_service.get_supported_providers_for_source(
            source.short_name
        )

        # Create source model with all fields
        source_dict = {
            **{key: getattr(source, key) for key in source.__dict__ if not key.startswith("_")},
            "auth_fields": auth_fields,
            "config_fields": config_fields,
            "supported_auth_providers": supported_auth_providers,
        }

        # In self-hosted mode, force requires_byoc for OAuth sources
        if settings.ENVIRONMENT == "self-hosted" and source.auth_methods:
            if "oauth_browser" in source.auth_methods or "oauth_token" in source.auth_methods:
                source_dict["requires_byoc"] = True

        return schemas.Source.model_validate(source_dict)

    except Exception as e:
        # Unexpected error - log for investigation
        ctx.logger.error(f"Unexpected error building source schema for {source.short_name}: {e}")
        return None


# =============================================================================
# Sources Endpoints (list available integrations)
# =============================================================================


@router.get("/sources", response_model=List[schemas.Source])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> List[schemas.Source]:
    """List available source integrations for the Connect session.

    Returns the catalog of data sources that can be connected within this session.
    If allowed_integrations was specified when creating the session, only those
    sources are returned.

    Authentication: Bearer <session_token>
    """
    # Build context for service call
    ctx = await _build_session_context(db, session)

    ctx.logger.info("Listing available sources for connect session")

    # Fetch all sources from database
    sources = await crud.source.get_all(db)

    # Filter by allowed_integrations if specified
    if session.allowed_integrations:
        sources = [s for s in sources if s.short_name in session.allowed_integrations]

    # Build full source schemas with auth/config fields
    result_sources = []
    for source in sources:
        source_schema = await _build_source_schema(source, ctx)
        if source_schema:
            result_sources.append(source_schema)

    ctx.logger.info(f"Returning {len(result_sources)} sources for connect session")
    return result_sources


@router.get("/sources/{short_name}", response_model=schemas.Source)
async def get_source(
    short_name: str = Path(
        ...,
        description="Technical identifier of the source type (e.g., 'github', 'stripe', 'slack')",
    ),
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> schemas.Source:
    """Get detailed information about a specific source integration.

    Returns the source details including authentication requirements and
    configuration fields needed to create a connection.

    Authentication: Bearer <session_token>
    """
    # Verify source is in allowed_integrations (if restricted)
    if session.allowed_integrations and short_name not in session.allowed_integrations:
        logger.warning(f"Access denied: attempted to access restricted source '{short_name}'")
        raise HTTPException(
            status_code=403,
            detail=f"Source '{short_name}' is not allowed for this session",
        )

    # Build context for service call
    ctx = await _build_session_context(db, session)

    # Fetch source from database
    source = await crud.source.get_by_short_name(db, short_name)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source not found: {short_name}")

    # Build full source schema
    source_schema = await _build_source_schema(source, ctx)
    if not source_schema:
        raise HTTPException(status_code=500, detail=f"Invalid source configuration: {short_name}")

    return source_schema


# =============================================================================
# Session Endpoints
# =============================================================================


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


@router.get("/sessions/{session_id}", response_model=ConnectSessionContext)
async def get_session(
    session_id: UUID,
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> ConnectSessionContext:
    """Get the current session context from a session token.

    Use this endpoint to verify a session token is valid and retrieve
    the session details (collection, allowed integrations, mode, expiry).

    Authentication: Bearer <session_token>
    """
    # Verify URL session_id matches the token's session_id
    if session_id != session.session_id:
        raise HTTPException(status_code=403, detail="Session ID does not match token")
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
    _check_session_mode(session, MODES_VIEW, "viewing source connections")

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


@router.get("/source-connections/{connection_id}", response_model=schemas.SourceConnection)
async def get_source_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> schemas.SourceConnection:
    """Get a source connection by ID.

    Returns full connection details including auth_url for pending_auth connections.

    Authentication: Bearer <session_token>
    """
    _check_session_mode(session, MODES_VIEW, "viewing source connections")

    # Build context for service call
    ctx = await _build_session_context(db, session)

    # Get the connection
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

    # Check if allowed_integrations restricts access
    if session.allowed_integrations and connection.short_name not in session.allowed_integrations:
        ctx.logger.warning(
            f"Access denied: attempted to access restricted source '{connection.short_name}'"
        )
        raise HTTPException(
            status_code=403, detail="Session does not have access to this integration type"
        )

    return connection


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
    _check_session_mode(session, MODES_DELETE, "deleting source connections")

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
        ctx.logger.warning(
            f"Access denied: attempted to access restricted source '{connection.short_name}'"
        )
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


@router.post("/source-connections", response_model=schemas.SourceConnection)
async def create_source_connection(
    source_connection_in: schemas.SourceConnectionCreate,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
    authorization: str = Header(..., alias="Authorization"),
) -> schemas.SourceConnection:
    """Create a new source connection via Connect session.

    Supports all authentication methods:
    - DirectAuthentication: Immediate creation with provided credentials
    - OAuthBrowserAuthentication: Returns shell connection with authentication URL
    - OAuthTokenAuthentication: Immediate creation with provided OAuth token
    - AuthProviderAuthentication: Using external auth provider

    The connection is created in the session's collection. Any readable_collection_id
    in the request body is ignored for security.

    Session mode must be 'connect' or 'all' to create connections.
    If allowed_integrations was set when creating the session, only those
    sources can be used.

    Authentication: Bearer <session_token>
    """
    _check_session_mode(session, MODES_CREATE, "creating source connections")

    # Verify source is in allowed integrations (if restricted)
    if session.allowed_integrations:
        if source_connection_in.short_name not in session.allowed_integrations:
            logger.warning(
                f"Access denied: attempted to access restricted source "
                f"'{source_connection_in.short_name}'"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Source '{source_connection_in.short_name}' not allowed for this session",
            )

    # SECURITY: Override collection_id from session (ignore request body)
    source_connection_in.readable_collection_id = session.collection_id

    # Build ApiContext from session
    ctx = await _build_session_context(db, session)

    ctx.logger.info(
        f"Creating source connection via connect session {session.session_id} "
        f"for source '{source_connection_in.short_name}' in collection '{session.collection_id}'"
    )

    # For OAuth flows, attach session context for callback validation
    # Extract token using shared utility
    session_token = deps.extract_bearer_token(authorization)

    # Attach connect session data for OAuth callback validation
    # Note: These temporary attributes are consumed by create_init_session for OAuth flows
    connect_context = {
        "session_id": str(session.session_id),
        "organization_id": str(session.organization_id),
        "collection_id": session.collection_id,
        "end_user_id": session.end_user_id,
    }
    source_connection_in._connect_session_token = session_token  # noqa: SLF001
    source_connection_in._connect_session_context = connect_context  # noqa: SLF001

    # Create the connection
    result = await source_connection_service.create(
        db,
        obj_in=source_connection_in,
        ctx=ctx,
    )

    if ctx.analytics:
        ctx.analytics.track_event(
            "connect_source_connection_created",
            {
                "session_id": str(session.session_id),
                "collection_id": session.collection_id,
                "short_name": source_connection_in.short_name,
                "end_user_id": session.end_user_id,
                "is_oauth_flow": not result.auth.authenticated,
            },
        )

    return result


# =============================================================================
# Sync Job Endpoints (real-time progress)
# =============================================================================


@router.get(
    "/source-connections/{connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
)
async def get_connection_jobs(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> List[schemas.SourceConnectionJob]:
    """Get sync jobs for a source connection.

    Returns the list of sync jobs associated with this source connection,
    ordered by creation time (most recent first). Use this to get job IDs
    for subscribing to real-time progress updates.

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
        ctx.logger.warning(
            f"Access denied: attempted to access restricted source '{connection.short_name}'"
        )
        raise HTTPException(
            status_code=403, detail="Session does not have access to this integration type"
        )

    # Get sync_id from connection
    if not connection.sync_id:
        # No sync configured yet, return empty list
        return []

    # Get jobs for the sync
    jobs = await crud.sync_job.get_all_by_sync_id(db, sync_id=connection.sync_id)

    # Convert SyncJob model to schema, then to SourceConnectionJob
    return [
        schemas.SyncJob.model_validate(job).to_source_connection_job(connection_id) for job in jobs
    ]


@router.get("/source-connections/{connection_id}/subscribe")
async def subscribe_to_connection_sync(  # noqa: C901 - SSE streaming complexity
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    session: ConnectSessionContext = Depends(deps.get_connect_session),
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint for real-time sync progress.

    Subscribe to receive real-time updates about sync progress for a source
    connection. The connection will emit events as entities are processed.

    Event types:
    - connected: Initial connection confirmation with job_id
    - heartbeat: Keep-alive signal (every 30 seconds)
    - Progress updates: Entity counts (inserted, updated, deleted, kept, skipped)
    - sync_complete: Final event when sync finishes

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

    # Check if allowed_integrations restricts access
    if session.allowed_integrations and connection.short_name not in session.allowed_integrations:
        ctx.logger.warning(
            f"Access denied: attempted to access restricted source '{connection.short_name}'"
        )
        raise HTTPException(
            status_code=403, detail="Session does not have access to this integration type"
        )

    # Get sync_id from connection
    if not connection.sync_id:
        raise HTTPException(status_code=404, detail="No sync configured for this connection")

    # Get the latest job (active or most recent)
    job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=connection.sync_id)
    if not job:
        raise HTTPException(status_code=404, detail="No sync jobs found for this connection")

    job_id = job.id
    ctx.logger.info(
        f"SSE subscription for connect session: connection={connection_id}, job={job_id}"
    )

    # Subscribe to Redis pubsub channel for this job
    pubsub = await core_pubsub.subscribe("sync_job", job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            # Send heartbeat to keep connection alive
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = SSE_HEARTBEAT_INTERVAL_SECONDS

            async for message in pubsub.listen():
                # Check if we need to send a heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield 'data: {"type": "heartbeat"}\n\n'
                    last_heartbeat = current_time

                if message["type"] == "message":
                    # Forward the sync progress update
                    yield f"data: {message['data']}\n\n"
                elif message["type"] == "subscribe":
                    logger.info(f"SSE subscribed to job {job_id} for connect session")

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for job {job_id}")
        except Exception as e:
            logger.error(f"SSE error for job {job_id}: {str(e)}")
            safe_message = _sanitize_sse_error(e)
            yield f"data: {json.dumps({'type': 'error', 'message': safe_message})}\n\n"
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
            "Access-Control-Allow-Origin": "*",
        },
    )
