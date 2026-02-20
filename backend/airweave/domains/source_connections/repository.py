"""Source connection repository wrapping crud.source_connection."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.domains.source_connections.protocols import (
    SourceConnectionRepositoryProtocol,
)
from airweave.models.source_connection import SourceConnection


class SourceConnectionRepository(SourceConnectionRepositoryProtocol):
    """Delegates to the crud.source_connection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Get a source connection by ID."""
        return await crud.source_connection.get(db, id, ctx)

    async def count_by_organization(self, db: AsyncSession, organization_id: UUID) -> int:
        """Count source connections for an organization."""
        stmt = (
            select(func.count())
            .select_from(SourceConnection)
            .where(SourceConnection.organization_id == organization_id)
        )
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)
