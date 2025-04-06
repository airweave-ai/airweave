"""API endpoints for performing searches."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.core.search_service import search_service

router = APIRouter()


@router.get("/")
async def search(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID = Query(..., description="The ID of the sync to search within"),
    query: str = Query(..., description="Search query text"),
    user: schemas.User = Depends(deps.get_user),
) -> list[dict]:
    """Search for documents within a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to search within
        query: The search query text
        user: The current user

    Returns:
    --------
        list[dict]: A list of search results
    """
    results = await search_service.search(
        db=db,
        query=query,
        sync_id=sync_id,
        current_user=user,
    )
    return results
