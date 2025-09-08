"""API endpoints for entity definitions and relations."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter

router = TrailingSlashRouter()


@router.get("/definitions/", response_model=List[schemas.EntityDefinition])
async def list_entity_definitions(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.EntityDefinition]:
    """List all entity definitions for the current user's organization."""
    return await crud.entity_definition.get_multi(db, organization_id=ctx.organization.id)


@router.post("/definitions/", response_model=schemas.EntityDefinition)
async def create_entity_definition(
    definition: schemas.EntityDefinitionCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.EntityDefinition:
    """Create a new entity definition."""
    return await crud.entity_definition.create(db, obj_in=definition, ctx=ctx)


@router.post("/definitions/by-ids/", response_model=List[schemas.EntityDefinition])
async def get_entity_definitions_by_ids(
    ids: List[UUID],
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.EntityDefinition]:
    """Get multiple entity definitions by their IDs.

    Args:
        ids: List of entity definition IDs to fetch
        db: Database session
        ctx: Current authenticated user

    Returns:
        List of entity definitions matching the provided IDs
    """
    return await crud.entity_definition.get_multi_by_ids(db, ids=ids)


@router.get("/definitions/by-source/", response_model=List[schemas.EntityDefinition])
async def get_entity_definitions_by_source_short_name(
    source_short_name: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.EntityDefinition]:
    """Get all entity definitions for a given source."""
    entity_definitions = await crud.entity_definition.get_multi_by_source_short_name(
        db, source_short_name=source_short_name
    )
    entity_definition_schemas = [
        schemas.EntityDefinition.model_validate(entity_definition)
        for entity_definition in entity_definitions
    ]
    return entity_definition_schemas


@router.get("/count-by-sync/{sync_id}", response_model=schemas.EntityCount)
async def get_entity_count_by_sync_id(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> Optional[schemas.EntityCount]:
    """Get the count of entities for a specific sync.

    Args:
        sync_id: The sync ID to count entities for
        db: Database session
        ctx: Current authenticated user

    Returns:
        Count of entities for the specified sync ID
    """
    # will throw 403 if the user doesn't have access to the sync
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
    # or return None if the sync doesn't exist
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    count = await crud.entity.get_count_by_sync_id(db, sync_id=sync_id)
    return schemas.EntityCount(count=count)
