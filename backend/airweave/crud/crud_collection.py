# airweave/crud/crud_collection.py

"""CRUD operations for collections."""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.collection import Collection
from airweave.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDBaseOrganization[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: BaseContext
    ) -> Optional[Collection]:
        """Get a collection by its readable ID."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        collection = result.scalar_one_or_none()

        if not collection:
            raise NotFoundException(f"Collection '{readable_id}' not found.")

        try:
            await self._validate_organization_access(ctx, collection.organization_id)
        except PermissionException:
            raise NotFoundException(f"Collection '{readable_id}' not found.")

        return collection

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        ctx: BaseContext,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Get multiple collections with pagination and optional search."""
        query = select(Collection).where(Collection.organization_id == ctx.organization.id)

        if search_query:
            search_pattern = f"%{search_query.lower()}%"
            query = query.where(
                (func.lower(Collection.name).like(search_pattern))
                | (func.lower(Collection.readable_id).like(search_pattern))
            )

        query = query.order_by(Collection.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def count(
        self, db: AsyncSession, ctx: BaseContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections for the organization."""
        query = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.organization_id == ctx.organization.id)
        )

        if search_query:
            search_pattern = f"%{search_query.lower()}%"
            query = query.where(
                (func.lower(Collection.name).like(search_pattern))
                | (func.lower(Collection.readable_id).like(search_pattern))
            )

        result = await db.execute(query)
        return result.scalar_one()


collection = CRUDCollection(Collection)
