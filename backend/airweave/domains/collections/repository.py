"""Collection repository wrapping crud.collection."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.models.collection import Collection


class CollectionRepository(CollectionRepositoryProtocol):
    """Delegates to the crud.collection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        return await crud.collection.get(db, id, ctx)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        return await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
