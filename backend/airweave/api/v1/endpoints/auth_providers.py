"""Auth Provider endpoints for managing auth provider connections."""

from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.domains.auth_provider.protocols import AuthProviderServiceProtocol
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator

router = TrailingSlashRouter()


# TODO(code-blue): migrate /list and /detail/{short_name} to registry-only metadata schema.
# Current response model includes DB fields (id/created_at/modified_at/organization_id).
@router.get("/list", response_model=List[schemas.AuthProvider])
async def list_auth_providers(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.AuthProvider]:
    """Get all available auth providers."""
    auth_providers = await crud.auth_provider.get_multi(db, skip=skip, limit=limit)
    result_providers: list[schemas.AuthProvider] = []

    for provider in auth_providers:
        try:
            provider_dict = {
                key: getattr(provider, key) for key in provider.__dict__ if not key.startswith("_")
            }

            if not provider.auth_config_class:
                ctx.logger.warning(f"Auth provider {provider.short_name} has no auth_config_class")
                result_providers.append(provider)
                continue

            auth_config_class = resource_locator.get_auth_config(provider.auth_config_class)
            provider_dict["auth_fields"] = Fields.from_config_class(auth_config_class)

            if provider.config_class:
                try:
                    config_class = resource_locator.get_config(provider.config_class)
                    provider_dict["config_fields"] = Fields.from_config_class(config_class)
                except Exception as exc:
                    ctx.logger.error(
                        f"Error getting config fields for {provider.short_name}: {str(exc)}"
                    )
                    provider_dict["config_fields"] = None
            else:
                provider_dict["config_fields"] = None

            result_providers.append(schemas.AuthProvider.model_validate(provider_dict))
        except Exception as exc:
            ctx.logger.error(f"Error processing auth provider {provider.short_name}: {str(exc)}")
            result_providers.append(provider)

    return result_providers


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


@router.get("/detail/{short_name}", response_model=schemas.AuthProvider)
async def get_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProvider:
    """Get details of a specific auth provider."""
    auth_provider = await crud.auth_provider.get_by_short_name(db, short_name=short_name)
    if not auth_provider:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider not found: {short_name}",
        )

    if auth_provider.auth_config_class:
        try:
            auth_config_class = resource_locator.get_auth_config(auth_provider.auth_config_class)
            auth_fields = Fields.from_config_class(auth_config_class)
            provider_dict = {
                **{
                    key: getattr(auth_provider, key)
                    for key in auth_provider.__dict__
                    if not key.startswith("_")
                },
                "auth_fields": auth_fields,
            }

            if auth_provider.config_class:
                try:
                    config_class = resource_locator.get_config(auth_provider.config_class)
                    provider_dict["config_fields"] = Fields.from_config_class(config_class)
                except Exception as exc:
                    ctx.logger.error(f"Error getting config fields for {short_name}: {str(exc)}")
                    provider_dict["config_fields"] = None
            else:
                provider_dict["config_fields"] = None

            return schemas.AuthProvider.model_validate(provider_dict)
        except Exception as exc:
            ctx.logger.error(f"Failed to get auth config for {short_name}: {str(exc)}")

    return auth_provider


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
