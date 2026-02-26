"""Auth Provider endpoints for managing auth provider connections."""

from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.domains.auth_provider.protocols import AuthProviderServiceProtocol
from airweave.domains.auth_provider.types import AuthProviderMetadata

router = TrailingSlashRouter()


@router.get("/list", response_model=List[AuthProviderMetadata])
async def list_auth_providers(
    *,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> List[AuthProviderMetadata]:
    """Get all available auth providers."""
    return await auth_provider_service.list_metadata(ctx=ctx)


@router.get("/connections/", response_model=List[schemas.AuthProviderConnection])
async def list_auth_provider_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = 100,
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> List[schemas.AuthProviderConnection]:
    """Get all auth provider connections for the current organization."""
    return await auth_provider_service.list_connections(db, ctx=ctx, skip=skip, limit=limit)


@router.get("/connections/{readable_id}", response_model=schemas.AuthProviderConnection)
async def get_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> schemas.AuthProviderConnection:
    """Get details of a specific auth provider connection."""
    return await auth_provider_service.get_connection(db, readable_id=readable_id, ctx=ctx)


@router.get("/detail/{short_name}", response_model=AuthProviderMetadata)
async def get_auth_provider(
    *,
    short_name: str,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> AuthProviderMetadata:
    """Get details of a specific auth provider."""
    try:
        return await auth_provider_service.get_metadata(short_name=short_name, ctx=ctx)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Auth provider not found: {short_name}"
        ) from exc


@router.post("/", response_model=schemas.AuthProviderConnection)
async def connect_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_provider_connection_in: schemas.AuthProviderConnectionCreate,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> schemas.AuthProviderConnection:
    """Create a new auth provider connection with credentials."""
    return await auth_provider_service.create_connection(
        db, obj_in=auth_provider_connection_in, ctx=ctx
    )


@router.delete("/{readable_id}", response_model=schemas.AuthProviderConnection)
async def delete_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> schemas.AuthProviderConnection:
    """Delete an auth provider connection."""
    return await auth_provider_service.delete_connection(db, readable_id=readable_id, ctx=ctx)


@router.put("/{readable_id}", response_model=schemas.AuthProviderConnection)
async def update_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    auth_provider_connection_update: schemas.AuthProviderConnectionUpdate,
    ctx: ApiContext = Depends(deps.get_context),
    auth_provider_service: AuthProviderServiceProtocol = Inject(AuthProviderServiceProtocol),
) -> schemas.AuthProviderConnection:
    """Update an existing auth provider connection."""
    return await auth_provider_service.update_connection(
        db,
        readable_id=readable_id,
        obj_in=auth_provider_connection_update,
        ctx=ctx,
    )
