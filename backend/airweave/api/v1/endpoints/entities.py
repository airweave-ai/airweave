"""API endpoints for entity definitions and relations."""

from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter

router = TrailingSlashRouter()


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
