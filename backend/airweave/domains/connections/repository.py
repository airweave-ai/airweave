"""Connection repository wrapping crud.connection."""

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate


class ConnectionRepository(ConnectionRepositoryProtocol):
    """Delegates to the crud.connection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        return await crud.connection.get(db, id, ctx)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Connection]:
        return await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[ConnectionCreate, dict],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        return await crud.connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)
