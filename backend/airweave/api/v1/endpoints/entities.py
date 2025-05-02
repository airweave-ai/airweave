"""API endpoints for entity definitions and relations."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.models.user import User

router = TrailingSlashRouter()


@router.get("/definitions/", response_model=List[schemas.EntityDefinition])
async def list_entity_definitions(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.EntityDefinition]:
    """List all entity definitions for the current user's organization."""
    return await crud.entity_definition.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/definitions/", response_model=schemas.EntityDefinition)
async def create_entity_definition(
    definition: schemas.EntityDefinitionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.EntityDefinition:
    """Create a new entity definition."""
    return await crud.entity_definition.create(db, obj_in=definition, user=current_user)


@router.put("/definitions/{definition_id}", response_model=schemas.EntityDefinition)
async def update_entity_definition(
    definition_id: UUID,
    definition: schemas.EntityDefinitionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.EntityDefinition:
    """Update an entity definition."""
    db_obj = await crud.entity_definition.get(db, id=definition_id)
    return await crud.entity_definition.update(
        db, db_obj=db_obj, obj_in=definition, user=current_user
    )


@router.get("/relations/", response_model=List[schemas.EntityRelation])
async def list_entity_relations(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.EntityRelation]:
    """List all entity relations for the current user's organization."""
    return await crud.entity_relation.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/relations/", response_model=schemas.EntityRelation)
async def create_entity_relation(
    relation: schemas.EntityRelationCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.EntityRelation:
    """Create a new entity relation."""
    return await crud.entity_relation.create(db, obj_in=relation, user=current_user)


@router.put("/relations/{relation_id}", response_model=schemas.EntityRelation)
async def update_entity_relation(
    relation_id: UUID,
    relation: schemas.EntityRelationUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.EntityRelation:
    """Update an entity relation."""
    db_obj = await crud.entity_relation.get(db, id=relation_id)
    return await crud.entity_relation.update(db, db_obj=db_obj, obj_in=relation, user=current_user)


@router.post("/definitions/by-ids/", response_model=List[schemas.EntityDefinition])
async def get_entity_definitions_by_ids(
    ids: List[UUID],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.EntityDefinition]:
    """Get multiple entity definitions by their IDs.

    Args:
        ids: List of entity definition IDs to fetch
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of entity definitions matching the provided IDs
    """
    return await crud.entity_definition.get_multi_by_ids(db, ids=ids)


@router.get("/definitions/by-source/", response_model=List[schemas.EntityDefinition])
async def get_entity_definitions_by_source_short_name(
    source_short_name: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
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
    current_user: User = Depends(deps.get_user),
) -> Optional[schemas.EntityCount]:
    """Get the count of entities for a specific sync.

    Args:
        sync_id: The sync ID to count entities for
        db: Database session
        current_user: Current authenticated user

    Returns:
        Count of entities for the specified sync ID
    """
    # will throw 403 if the user doesn't have access to the sync
    sync = await crud.sync.get(db, id=sync_id, current_user=current_user)
    # or return None if the sync doesn't exist
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    count = await crud.entity.get_count_by_sync_id(db, sync_id=sync_id)
    return schemas.EntityCount(count=count)
