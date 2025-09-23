"""Refactored source connections API endpoints with clean abstractions."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.shared_models import ActionType
from airweave.core.source_connection_service import source_connection_service
from airweave.db.session import get_db

router = TrailingSlashRouter()


# OAuth callback endpoints
@router.get("/callback")
async def oauth_callback(
    *,
    db: AsyncSession = Depends(get_db),
    state: str = Query(..., description="OAuth state parameter"),
    code: str = Query(..., description="OAuth authorization code"),
) -> Response:
    """Handle OAuth callback from user after they have authenticated with an OAuth provider.

    Completes the OAuth flow and redirects to the configured URL.
    This endpoint does not require authentication as it's accessed by users
    who are connecting their source.
    """
    source_conn = await source_connection_service.complete_oauth_callback(
        db,
        state=state,
        code=code,
    )

    # Redirect to the app with success
    redirect_url = source_conn.auth.redirect_url
    if not redirect_url:
        # Fallback to app URL if redirect_url is not set
        from airweave.core.config import settings

        redirect_url = settings.app_url

    connection_id = source_conn.id
    return Response(
        status_code=303,
        headers={"Location": f"{redirect_url}?success=true&connection_id={connection_id}"},
    )


@router.post("/", response_model=schemas.SourceConnection)
async def create(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_in: schemas.SourceConnectionCreate,
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> schemas.SourceConnection:
    """Create a new source connection.

    The authentication configuration determines the flow:
    - DirectAuthentication: Immediate creation with provided credentials
    - OAuthBrowserAuthentication: Returns shell with authentication URL
    - OAuthTokenAuthentication: Immediate creation with provided token
    - AuthProviderAuthentication: Using external auth provider

    BYOC (Bring Your Own Client) is detected when client_id and client_secret
    are provided in OAuthBrowserAuthentication.
    """
    # Check if organization is allowed to create a source connection
    await guard_rail.is_allowed(ActionType.SOURCE_CONNECTIONS)

    # If sync_immediately is True, check if we can process entities
    if source_connection_in.sync_immediately:
        await guard_rail.is_allowed(ActionType.ENTITIES)

    result = await source_connection_service.create(
        db,
        obj_in=source_connection_in,
        ctx=ctx,
    )

    # Increment source connection usage after successful creation
    await guard_rail.increment(ActionType.SOURCE_CONNECTIONS)

    return result


@router.get("/", response_model=List[schemas.SourceConnectionListItem])
async def list(
    *,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    collection: Optional[str] = Query(None, description="Filter by collection readable ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections with minimal fields for performance."""
    return await source_connection_service.list(
        db,
        ctx=ctx,
        readable_collection_id=collection,
        skip=skip,
        limit=limit,
    )


@router.get("/{source_connection_id}", response_model=schemas.SourceConnection)
async def get(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Get a source connection with optional depth expansion."""
    result = await source_connection_service.get(
        db,
        id=source_connection_id,
        ctx=ctx,
    )
    return result


@router.patch("/{source_connection_id}", response_model=schemas.SourceConnection)
async def update(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    source_connection_in: schemas.SourceConnectionUpdate,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnection:
    """Update a source connection.

    Updateable fields:
    - name, description
    - config_fields
    - cron_schedule
    - auth_fields (direct auth only)
    """
    return await source_connection_service.update(
        db,
        id=source_connection_id,
        obj_in=source_connection_in,
        ctx=ctx,
    )


@router.delete("/{source_connection_id}", response_model=schemas.SourceConnection)
async def delete(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> schemas.SourceConnection:
    """Delete a source connection and all related data."""
    result = await source_connection_service.delete(
        db,
        id=source_connection_id,
        ctx=ctx,
    )

    # Decrement source connection usage after successful deletion
    await guard_rail.decrement(ActionType.SOURCE_CONNECTIONS)

    return result


@router.post("/{source_connection_id}/run", response_model=schemas.SourceConnectionJob)
async def run(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> schemas.SourceConnectionJob:
    """Trigger a sync run for a source connection.

    Runs are always executed through Temporal workflow engine.
    """
    # Check if organization is allowed to process entities
    await guard_rail.is_allowed(ActionType.ENTITIES)

    run = await source_connection_service.run(
        db,
        id=source_connection_id,
        ctx=ctx,
    )
    return run


@router.get("/{source_connection_id}/jobs", response_model=List[schemas.SourceConnectionJob])
async def get_source_connection_jobs(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    limit: int = Query(100, ge=1, le=1000),
) -> List[schemas.SourceConnectionJob]:
    """Get sync jobs for a source connection."""
    return await source_connection_service.get_jobs(
        db,
        id=source_connection_id,
        ctx=ctx,
        limit=limit,
    )


@router.post(
    "/{source_connection_id}/jobs/{job_id}/cancel", response_model=schemas.SourceConnectionJob
)
async def cancel_job(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    job_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnectionJob:
    """Cancel a running sync job for a source connection.

    This will update the job status in the database to CANCELLED and
    send a cancellation request to the Temporal workflow if it's running.
    """
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
