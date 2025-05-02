"""API endpoints for transformers."""

from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.crud.crud_transformer import transformer
from airweave.models.user import User
from airweave.schemas.transformer import Transformer, TransformerCreate, TransformerUpdate

router = TrailingSlashRouter()


@router.get("/", response_model=List[Transformer])
async def list_transformers(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """List all transformers for the current user's organization."""
    return await transformer.get_multi_by_organization(
        db, organization_id=current_user.organization_id
    )


@router.post("/", response_model=Transformer)
async def create_transformer(
    transformer_in: TransformerCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Create a new transformer."""
    return await transformer.create(db, obj_in=transformer_in, user=current_user)


@router.put("/{transformer_id}", response_model=Transformer)
async def update_transformer(
    transformer_id: str,
    transformer_in: TransformerUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Update a transformer."""
    db_obj = await transformer.get(db, id=transformer_id)
    return await transformer.update(db, db_obj=db_obj, obj_in=transformer_in, user=current_user)
