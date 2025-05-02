"""The API module that contains the endpoints for sources."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator

router = TrailingSlashRouter()


@router.get("/detail/{short_name}", response_model=schemas.SourceWithConfigFields)
async def read_source(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Source:
    """Get source by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the source.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.Source: The source object.

    """
    source = await crud.source.get_by_short_name(db, short_name)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.auth_config_class:
        auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
        fields = Fields.from_config_class(auth_config_class)
        source_with_config_fields = schemas.SourceWithConfigFields.model_validate(
            source, from_attributes=True
        )
        source_with_config_fields.config_fields = fields
        return source_with_config_fields
    return source


@router.get("/list", response_model=list[schemas.Source])
async def read_sources(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Source]:
    """Get all sources for the current user.

    Args:
    -----
        db: The database session
        user: The current user

    Returns:
    --------
        list[schemas.Source]: The list of sources.

    """
    sources = await crud.source.get_all(db)
    return sources
