"""Refactored source connections API endpoints with clean abstractions."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
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
    result = await source_connection_service.create(
        db,
        obj_in=source_connection_in,
        ctx=ctx,
    )
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
) -> schemas.SourceConnection:
    """Delete a source connection and all related data."""
    return await source_connection_service.delete(
        db,
        id=source_connection_id,
        ctx=ctx,
    )


@router.post("/{source_connection_id}/run", response_model=schemas.SourceConnectionJob)
async def run(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceConnectionJob:
    """Trigger a sync run for a source connection.

    Runs are always executed through Temporal workflow engine.
    """
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


@router.get("/{short_name}/oauth2_url", response_model=schemas.OAuth2AuthUrl)
async def get_oauth2_url(
    *,
    db: AsyncSession = Depends(get_db),
    short_name: str,
    client_id: Optional[str] = Query(None, description="Optional client ID for BYOC"),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OAuth2AuthUrl:
    """Get OAuth2 authorization URL for a source.

    This endpoint generates an OAuth2 authorization URL for the specified source.
    The URL can be used to redirect users to the OAuth provider for authentication.

    Args:
        short_name: The short name of the source (e.g., 'confluence', 'notion')
        client_id: Optional client ID for BYOC (Bring Your Own Client) scenarios

    Returns:
        OAuth2AuthUrl containing the authorization URL and metadata
    """
    try:
        # Get source and validate
        source = await crud.source.get_by_short_name(db, short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source not found: {short_name}")

        # Check if source supports OAuth
        if not source.oauth_type:
            raise HTTPException(
                status_code=400, detail=f"Source {short_name} does not support OAuth authentication"
            )

        # Get OAuth settings
        from airweave.platform.auth.settings import integration_settings

        oauth_settings = await integration_settings.get_by_short_name(short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not configured for source: {short_name}",
            )

        # Generate OAuth URL
        import secrets

        from airweave.core.config import settings as core_settings
        from airweave.platform.auth.services import oauth2_service

        state = secrets.token_urlsafe(24)
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=client_id,
            state=state,
        )

        return schemas.OAuth2AuthUrl(
            url=provider_auth_url,
        )

    except HTTPException:
        raise
    except Exception as e:
        ctx.logger.error(f"Failed to generate OAuth2 URL for {short_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate OAuth2 URL: {str(e)}")


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
