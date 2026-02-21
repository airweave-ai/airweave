"""Source connection repository wrapping crud.source_connection."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.redirect_session import RedirectSession
from airweave.models.source_connection import SourceConnection


class SourceConnectionRepository(SourceConnectionRepositoryProtocol):
    """Delegates to the crud.source_connection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        return await crud.source_connection.get(db, id, ctx)

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        return await crud.source_connection.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)

    async def get_schedule_info(
        self, db: AsyncSession, source_connection: SourceConnection
    ) -> Optional[ScheduleInfo]:
        return await crud.source_connection.get_schedule_info(db, source_connection)

    async def get_init_session_with_redirect(
        self, db: AsyncSession, session_id: UUID, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        stmt = (
            select(ConnectionInitSession)
            .where(ConnectionInitSession.id == session_id)
            .where(ConnectionInitSession.organization_id == ctx.organization.id)
            .options(selectinload(ConnectionInitSession.redirect_session))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_stats(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionStats]:
        raw = await crud.source_connection.get_multi_with_stats(
            db, ctx=ctx, collection_id=collection_id, skip=skip, limit=limit
        )
        return [SourceConnectionStats.from_dict(d) for d in raw]

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[Dict[str, Any], Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> SourceConnection:
        return await crud.source_connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def create_init_session(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> ConnectionInitSession:
        return await crud.connection_init_session.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def create_redirect_session(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> RedirectSession:
        return await crud.redirect_session.create(
            db, code=code, final_url=final_url, expires_at=expires_at, ctx=ctx, uow=uow
        )

    async def generate_unique_redirect_code(self, db: AsyncSession, *, length: int = 8) -> str:
        return await crud.redirect_session.generate_unique_code(db, length=length)
