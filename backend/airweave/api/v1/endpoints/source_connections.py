"""Source Connections API endpoints for managing data source integrations.

This module provides endpoints for creating, managing, and syncing source connections.
Source connections represent authenticated connections to external data sources
(like GitHub, Slack, or databases) that feed data into collections.

Key operations:
- Create connections with various authentication methods (Direct, OAuth, Auth Provider)
- Trigger manual syncs or configure scheduled syncs
- Monitor sync job status and history
- Update connection settings and credentials
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.protocols import EventBus
from airweave.core.shared_models import ActionType
from airweave.core.source_connection_service import source_connection_service
from airweave.db.session import get_db
from airweave.domains.source_connections.protocols import SourceConnectionServiceProtocol
from airweave.schemas.errors import (
    ConflictErrorResponse,
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)

router = TrailingSlashRouter()


# OAuth callback endpoints
@router.get("/callback")
async def oauth_callback(
    *,
    db: AsyncSession = Depends(get_db),
    event_bus: EventBus = Inject(EventBus),
    # OAuth2 parameters
    state: Optional[str] = Query(None, description="OAuth2 state parameter"),
    code: Optional[str] = Query(None, description="OAuth2 authorization code"),
    # OAuth1 parameters
    oauth_token: Optional[str] = Query(None, description="OAuth1 token parameter"),
    oauth_verifier: Optional[str] = Query(None, description="OAuth1 verifier"),
) -> Response:
    """Handle OAuth callback from user after they have authenticated with an OAuth provider.

    Supports both OAuth1 and OAuth2 callbacks:
    - OAuth2: Uses state + code parameters
    - OAuth1: Uses oauth_token + oauth_verifier parameters

    Completes the OAuth flow and redirects to the configured URL.
    This endpoint does not require authentication as it's accessed by users
    who are connecting their source.
    """
    # Determine OAuth1 vs OAuth2 based on parameters
    if oauth_token and oauth_verifier:
        # OAuth1 callback
        source_conn = await source_connection_service.complete_oauth1_callback(
            db,
            oauth_token=oauth_token,
            oauth_verifier=oauth_verifier,
        )
    elif state and code:
        # OAuth2 callback
        source_conn = await source_connection_service.complete_oauth2_callback(
            db,
            state=state,
            code=code,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid OAuth callback: missing required parameters. "
                "Expected either (state + code) for OAuth2 or "
                "(oauth_token + oauth_verifier) for OAuth1"
            ),
        )

    # Redirect to the app with success
    redirect_url = source_conn.auth.redirect_url

    if not redirect_url:
        # Fallback to app URL if redirect_url is not set
        from airweave.core.config import settings

        redirect_url = settings.app_url
    try:
        await event_bus.publish(
            SourceConnectionLifecycleEvent.auth_completed(
                organization_id=source_conn.organization_id,
                source_connection_id=source_conn.id,
                source_type=source_conn.short_name,
                collection_readable_id=source_conn.readable_collection_id,
            )
        )
    except Exception as e:
        logger.error(f"Failed to publish source_connection.auth_completed event: {e}")

    # Parse the redirect URL to preserve existing query parameters
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(redirect_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Add success parameters (using frontend-expected param names)
    query_params["status"] = ["success"]
    query_params["source_connection_id"] = [str(source_conn.id)]

    # Reconstruct the URL with all query parameters
    new_query = urlencode(query_params, doseq=True)
    final_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )

    return Response(
        status_code=303,
        headers={"Location": final_url},
    )


@router.post(
    "/",
    response_model=schemas.SourceConnection,
    summary="Create Source Connection",
    description="""Create a new source connection to sync data from an external source.

The authentication method determines the creation flow:

- **Direct**: Provide credentials (API key, token) directly. Connection is created immediately.
- **OAuth Browser**: Returns a connection with an `auth_url` to redirect users for authentication.
- **OAuth Token**: Provide an existing OAuth token. Connection is created immediately.
- **Auth Provider**: Use a pre-configured auth provider (e.g., Composio, Pipedream).

After successful authentication, data sync can begin automatically or on-demand.""",
    responses={
        200: {"model": schemas.SourceConnection, "description": "Created source connection"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def create(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_in: schemas.SourceConnectionCreate,
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    event_bus: EventBus = Inject(EventBus),
) -> schemas.SourceConnection:
    """Create a new source connection."""
    # Check if organization is allowed to create a source connection
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    # If sync_immediately is True or None (will be defaulted), check if we can process entities
    # Note: We check even for None because it may default to True based on auth method
    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.ENTITIES)

    result = await source_connection_service.create(
        db,
        obj_in=source_connection_in,
        ctx=ctx,
    )

    # Publish source_connection.created event
    try:
        await event_bus.publish(
            SourceConnectionLifecycleEvent.created(
                organization_id=ctx.organization.id,
                source_connection_id=result.id,
                source_type=result.short_name,
                collection_readable_id=result.readable_collection_id,
                is_authenticated=result.is_authenticated,
            )
        )
    except Exception as e:
        ctx.logger.warning(f"Failed to publish source_connection.created event: {e}")

    return result


@router.get(
    "/",
    response_model=List[schemas.SourceConnectionListItem],
    summary="List Source Connections",
    description="""Retrieve all source connections for your organization.

Returns a lightweight list of source connections with essential fields for
display and navigation. Use the collection filter to see connections within
a specific collection.

For full connection details including sync history, use the GET /{id} endpoint.""",
    responses={
        200: {
            "model": List[schemas.SourceConnectionListItem],
            "description": "List of source connections",
        },
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def list(
    *,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    collection: Optional[str] = Query(
        None,
        description="Filter by collection readable ID",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Number of connections to skip for pagination",
        json_schema_extra={"example": 0},
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of connections to return (1-1000)",
        json_schema_extra={"example": 100},
    ),
    source_connection_service: SourceConnectionServiceProtocol = Inject(
        SourceConnectionServiceProtocol
    ),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections with minimal fields for performance."""
    return await source_connection_service.list(
        db,
        ctx=ctx,
        readable_collection_id=collection,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{source_connection_id}",
    response_model=schemas.SourceConnection,
    summary="Get Source Connection",
    description="""Retrieve details of a specific source connection.

Returns complete information about the connection including:
- Configuration settings
- Authentication status
- Sync schedule and history
- Entity statistics""",
    responses={
        200: {"model": schemas.SourceConnection, "description": "Source connection details"},
        404: {"model": NotFoundErrorResponse, "description": "Source Connection Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    source_connection_service: SourceConnectionServiceProtocol = Inject(
        SourceConnectionServiceProtocol
    ),
) -> schemas.SourceConnection:
    """Get a source connection with full details."""
    result = await source_connection_service.get(
        db,
        id=source_connection_id,
        ctx=ctx,
    )
    return result


@router.patch(
    "/{source_connection_id}",
    response_model=schemas.SourceConnection,
    summary="Update Source Connection",
    description="""Update an existing source connection's configuration.

You can modify:
- **Name and description**: Display information
- **Configuration**: Source-specific settings (e.g., repository name, filters)
- **Schedule**: Cron expression for automatic syncs
- **Authentication**: Update credentials (direct auth only)

Only include the fields you want to change; omitted fields retain their current values.""",
    responses={
        200: {"model": schemas.SourceConnection, "description": "Updated source connection"},
        404: {"model": NotFoundErrorResponse, "description": "Source Connection Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def update(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection to update (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    source_connection_in: schemas.SourceConnectionUpdate,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Update a source connection's configuration."""
    return await source_connection_service.update(
        db,
        id=source_connection_id,
        obj_in=source_connection_in,
        ctx=ctx,
    )


@router.delete(
    "/{source_connection_id}",
    response_model=schemas.SourceConnection,
    summary="Delete Source Connection",
    description="""Permanently delete a source connection and all its synced data.

**What happens when you delete:**

1. Any running sync is cancelled and the API waits (up to 15 s) for the
   worker to stop writing.
2. The source connection, sync configuration, job history, and entity
   metadata are cascade-deleted from the database.
3. A background cleanup workflow is scheduled to remove data from the
   vector database (Vespa) and raw data storage (ARF). This may take
   several minutes for large datasets but does **not** block the response.

The API returns immediately after step 2. Vector database cleanup happens
asynchronously -- the data becomes unsearchable as soon as the database
records are deleted.

**Warning**: This action cannot be undone.""",
    responses={
        200: {"model": schemas.SourceConnection, "description": "Deleted source connection"},
        404: {"model": NotFoundErrorResponse, "description": "Source Connection Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def delete(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection to delete (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    event_bus: EventBus = Inject(EventBus),
) -> schemas.SourceConnection:
    """Delete a source connection and all related data."""
    result = await source_connection_service.delete(
        db,
        id=source_connection_id,
        ctx=ctx,
    )

    # Publish source_connection.deleted event
    try:
        await event_bus.publish(
            SourceConnectionLifecycleEvent.deleted(
                organization_id=ctx.organization.id,
                source_connection_id=source_connection_id,
                source_type=result.short_name,
                collection_readable_id=result.readable_collection_id,
            )
        )
    except Exception as e:
        ctx.logger.warning(f"Failed to publish source_connection.deleted event: {e}")

    return result


@router.post(
    "/{source_connection_id}/run",
    response_model=schemas.SourceConnectionJob,
    summary="Run Sync",
    description="""Trigger a data synchronization job for a source connection.

Starts an asynchronous sync job that pulls the latest data from the connected
source. The job runs in the background and you can monitor its progress using
the jobs endpoint.

For continuous sync connections, this performs an incremental sync by default.
Use `force_full_sync=true` to perform a complete re-sync of all data.""",
    responses={
        200: {"model": schemas.SourceConnectionJob, "description": "Created sync job"},
        404: {"model": NotFoundErrorResponse, "description": "Source Connection Not Found"},
        409: {"model": ConflictErrorResponse, "description": "Sync Already Running"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def run(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection to sync (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    force_full_sync: bool = Query(
        False,
        description=(
            "Force a full sync ignoring cursor data. Only applies to continuous sync "
            "connections. Non-continuous connections always perform full syncs."
        ),
        json_schema_extra={"example": False},
    ),
) -> schemas.SourceConnectionJob:
    """Trigger a sync run for a source connection."""
    # Check if organization is allowed to process entities
    await guard_rail.is_allowed(ActionType.ENTITIES)

    run = await source_connection_service.run(
        db,
        id=source_connection_id,
        ctx=ctx,
        force_full_sync=force_full_sync,
    )
    return run


@router.get(
    "/{source_connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
    summary="List Sync Jobs",
    description="""Retrieve the sync job history for a source connection.

Returns a list of sync jobs ordered by creation time (newest first). Each job
includes status, timing information, and entity counts.

Job statuses:
- **PENDING**: Job is queued, waiting for the worker to pick it up
- **RUNNING**: Sync is actively pulling and processing data
- **COMPLETED**: Sync finished successfully
- **FAILED**: Sync encountered an unrecoverable error
- **CANCELLING**: Cancellation has been requested. The worker is
  gracefully stopping the pipeline and cleaning up destination data.
- **CANCELLED**: Sync was cancelled. The worker has fully stopped
  and destination data cleanup has been scheduled.""",
    responses={
        200: {
            "model": List[schemas.SourceConnectionJob],
            "description": "List of sync jobs",
        },
        404: {"model": NotFoundErrorResponse, "description": "Source Connection Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get_source_connection_jobs(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of jobs to return (1-1000)",
        json_schema_extra={"example": 100},
    ),
) -> List[schemas.SourceConnectionJob]:
    """Get sync jobs for a source connection."""
    return await source_connection_service.get_jobs(
        db,
        id=source_connection_id,
        ctx=ctx,
        limit=limit,
    )


@router.post(
    "/{source_connection_id}/jobs/{job_id}/cancel",
    response_model=schemas.SourceConnectionJob,
    summary="Cancel Sync Job",
    description="""Request cancellation of a running sync job.

**State lifecycle**: `PENDING` / `RUNNING` → `CANCELLING` → `CANCELLED`

1. The API immediately marks the job as **CANCELLING** in the database.
2. A cancellation signal is sent to the Temporal workflow.
3. The worker receives the signal, gracefully stops the sync pipeline
   (cancels worker pool, source stream), and marks the job as **CANCELLED**.

Already-processed entities are retained in the vector database.
If the worker is unresponsive, a background cleanup job will force the
transition to CANCELLED after 3 minutes.

**Note**: Only jobs in `PENDING` or `RUNNING` state can be cancelled.
Attempting to cancel a `COMPLETED`, `FAILED`, or `CANCELLED` job returns 400.""",
    responses={
        200: {"model": schemas.SourceConnectionJob, "description": "Job with cancellation status"},
        404: {"model": NotFoundErrorResponse, "description": "Job Not Found"},
        409: {"model": ConflictErrorResponse, "description": "Job Cannot Be Cancelled"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def cancel_job(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(
        ...,
        description="Unique identifier of the source connection (UUID)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the sync job to cancel (UUID)",
        json_schema_extra={"example": "660e8400-e29b-41d4-a716-446655440001"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnectionJob:
    """Cancel a running sync job."""
    return await source_connection_service.cancel_job(
        db,
        source_connection_id=source_connection_id,
        job_id=job_id,
        ctx=ctx,
    )


@router.post("/{source_connection_id}/make-continuous", response_model=schemas.SourceConnection)
async def make_continuous(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    cursor_field: Optional[str] = Query(None, description="Field to use for incremental sync"),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Convert source connection to continuous sync mode.

    Only available for sources that support incremental sync.
    """
    return await source_connection_service.make_continuous(
        db,
        id=source_connection_id,
        cursor_field=cursor_field,
        ctx=ctx,
    )


@router.get("/{source_connection_id}/sync-id", include_in_schema=False)
async def get_sync_id(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Get the sync_id for a source connection.

    This is a private endpoint not documented in Fern.
    Used internally for Temporal sync testing and debugging.
    """
    source_connection = await crud.source_connection.get(
        db,
        id=source_connection_id,
        ctx=ctx,
    )

    if not source_connection.sync_id:
        raise HTTPException(status_code=404, detail="No sync found for this source connection")

    return {"sync_id": str(source_connection.sync_id)}


@router.get("/authorize/{code}")
async def authorize_redirect(
    *,
    db: AsyncSession = Depends(get_db),
    code: str,
) -> Response:
    """Proxy redirect to OAuth provider.

    This endpoint is used to provide a short-lived, user-friendly URL
    that redirects to the actual OAuth provider authorization page.
    This endpoint does not require authentication as it's accessed by users
    who are not yet authenticated with the platform.
    """
    from airweave.crud import redirect_session

    redirect_info = await redirect_session.get_by_code(db, code=code)
    if not redirect_info:
        raise HTTPException(status_code=404, detail="Authorization link expired or invalid")

    # Redirect to the OAuth provider
    return Response(
        status_code=303,
        headers={"Location": redirect_info.final_url},
    )
