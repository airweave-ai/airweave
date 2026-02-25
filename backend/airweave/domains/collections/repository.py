"""Collection repository wrapping crud.collection."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.models.collection import Collection


class CollectionRepository(CollectionRepositoryProtocol):
    """Delegates to the crud.collection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Get a collection by ID."""
        return await crud.collection.get(db, id, ctx)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Get a collection by readable ID."""
        try:
            return await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
        except NotFoundException:
            return None

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Get multiple collections with pagination and optional search."""
        return await crud.collection.get_multi(
            db, ctx=ctx, skip=skip, limit=limit, search_query=search_query
        )

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections."""
        return await crud.collection.count(db, ctx=ctx, search_query=search_query)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Collection:
        """Create a new collection."""
        return await crud.collection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Collection,
        obj_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Update an existing collection."""
        return await crud.collection.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx)

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Delete a collection by ID."""
        return await crud.collection.remove(db, id=id, ctx=ctx)
