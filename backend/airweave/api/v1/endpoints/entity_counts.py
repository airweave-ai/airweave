"""Entity counts API endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.schemas.entity_count import EntityCountWithDefinition

router = APIRouter()


@router.get("/syncs/{sync_id}/counts", response_model=List[EntityCountWithDefinition])
async def get_entity_counts_for_sync(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[EntityCountWithDefinition]:
    """Get entity counts for a sync with entity definition details.

    This endpoint returns the count of entities grouped by entity type,
    along with details about each entity definition.
    """
    # Verify the sync belongs to the organization
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
    if not sync:
        raise HTTPException(
            status_code=404,
            detail=f"Sync {sync_id} not found",
        )

    # Get the counts with definition details
    counts = await crud.entity_count.get_counts_per_sync_and_type(db, sync_id)

    return counts


@router.get("/syncs/{sync_id}/total-count", response_model=int)
async def get_total_entity_count_for_sync(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> int:
    """Get total entity count across all types for a sync."""
    # Verify the sync belongs to the organization
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
    if not sync:
        raise HTTPException(
            status_code=404,
            detail=f"Sync {sync_id} not found",
        )

    # Get the total count
    total = await crud.entity_count.get_total_count_by_sync(db, sync_id)

    return total
