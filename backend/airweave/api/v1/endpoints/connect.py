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
   - GET /connect/callback - OAuth callback handler
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, Path, Query
from fastapi.responses import Response
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
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.core.source_connection_service import source_connection_service
from airweave.crud import connection_init_session
from airweave.db.session import get_db
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.state import make_state, verify_state
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator
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

    except Exception:
        return None


def _redirect_with_error(redirect_url: str, error_type: str, error_message: str) -> Response:
    """Build redirect response with error parameters."""
    parsed = urlparse(redirect_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    query_params["status"] = ["error"]
    query_params["error_type"] = [error_type]
    query_params["error_message"] = [error_message]
    new_query = urlencode(query_params, doseq=True)
    final_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    return Response(status_code=303, headers={"Location": final_url})


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
    # Verify session mode allows viewing connections (CONNECT mode is add-only)
    if session.mode not in (
        schemas.ConnectSessionMode.ALL,
        schemas.ConnectSessionMode.MANAGE,
        schemas.ConnectSessionMode.REAUTH,
    ):
        raise HTTPException(
            status_code=403, detail="Session mode does not allow viewing source connections"
        )

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

    # Verify session mode allows deletion (only MANAGE and ALL are permitted)
    if session.mode not in (schemas.ConnectSessionMode.MANAGE, schemas.ConnectSessionMode.ALL):
        raise HTTPException(
            status_code=403, detail="Session mode does not allow deleting source connections"
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
    # Verify session mode allows connection creation
    if session.mode not in (
        schemas.ConnectSessionMode.ALL,
        schemas.ConnectSessionMode.CONNECT,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session mode does not allow creating source connections",
        )

    # Verify source is in allowed integrations (if restricted)
    if session.allowed_integrations:
        if source_connection_in.short_name not in session.allowed_integrations:
            raise HTTPException(
                status_code=403,
                detail=f"Source '{source_connection_in.short_name}' is not allowed for this session",
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
    # Extract token from Authorization header
    session_token = authorization[7:] if authorization.startswith("Bearer ") else authorization

    # Attach connect session data for OAuth callback validation
    # These are temporary attributes that will be read by create_init_session
    source_connection_in._connect_session_token = session_token
    source_connection_in._connect_session_context = {
        "session_id": str(session.session_id),
        "organization_id": str(session.organization_id),
        "collection_id": session.collection_id,
        "end_user_id": session.end_user_id,
    }

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
# OAuth Callback Endpoint
# =============================================================================


@router.get("/callback")
async def connect_oauth_callback(
    *,
    db: AsyncSession = Depends(get_db),
    # OAuth2 parameters
    state: Optional[str] = Query(None, description="OAuth2 state parameter"),
    code: Optional[str] = Query(None, description="OAuth2 authorization code"),
    # OAuth1 parameters
    oauth_token: Optional[str] = Query(None, description="OAuth1 token parameter"),
    oauth_verifier: Optional[str] = Query(None, description="OAuth1 verifier"),
) -> Response:
    """Handle OAuth callback for source connections created via Connect API.

    This endpoint handles the OAuth provider redirect after user authorization.
    It validates that the original Connect session is still valid before completing
    the connection.

    Supports both OAuth1 and OAuth2 callbacks:
    - OAuth2: Uses state + code parameters
    - OAuth1: Uses oauth_token + oauth_verifier parameters

    Redirects to the configured URL with status and source_connection_id.
    """
    # Find the init session
    init_session = None

    if oauth_token and oauth_verifier:
        # OAuth1 callback
        init_session = await connection_init_session.get_by_oauth_token_no_auth(
            db, oauth_token=oauth_token
        )
    elif state and code:
        # OAuth2 callback
        init_session = await connection_init_session.get_by_state_no_auth(db, state=state)
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth callback: missing required parameters",
        )

    if not init_session:
        raise HTTPException(status_code=404, detail="OAuth session not found or expired")

    if init_session.status != ConnectionInitStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"OAuth session already {init_session.status.value}"
        )

    # Check if this is a Connect API flow (has connect_session_token in overrides)
    connect_token = init_session.overrides.get("connect_session_token")
    redirect_url = init_session.overrides.get("redirect_url", settings.app_url)

    if connect_token:
        # Validate the Connect session is still valid
        # Use extended TTL (30 min) for OAuth flows
        max_age = init_session.overrides.get("connect_session_max_age", 30 * 60)
        try:
            verify_state(connect_token, max_age_seconds=max_age)
        except ValueError as e:
            # Session expired - redirect with error
            logger.warning(f"Connect session expired during OAuth flow: {e}")
            return _redirect_with_error(redirect_url, "session_expired", str(e))

    # Complete the OAuth flow using existing service methods
    try:
        if oauth_token and oauth_verifier:
            source_conn = await source_connection_service.complete_oauth1_callback(
                db,
                oauth_token=oauth_token,
                oauth_verifier=oauth_verifier,
            )
        else:
            source_conn = await source_connection_service.complete_oauth2_callback(
                db,
                state=state,
                code=code,
            )
    except HTTPException as e:
        logger.error(f"OAuth callback failed: {e.detail}")
        return _redirect_with_error(redirect_url, "error", e.detail)

    # Redirect with success
    connection_id = source_conn.id
    final_redirect_url = source_conn.auth.redirect_url or redirect_url

    # Build final URL with success parameters
    parsed = urlparse(final_redirect_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    query_params["status"] = ["success"]
    query_params["source_connection_id"] = [str(connection_id)]
    new_query = urlencode(query_params, doseq=True)
    final_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )

    return Response(status_code=303, headers={"Location": final_url})
