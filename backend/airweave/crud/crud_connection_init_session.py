"""CRUD for ConnectionInitSession."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus

from ._base_organization import CRUDBaseOrganization


class CRUDConnectionInitSession(CRUDBaseOrganization[ConnectionInitSession, dict, dict]):
    """Basic CRUD scoped by organization."""

    async def get_by_state(
        self, db: AsyncSession, *, state: str, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        """Return the session matching the given OAuth/CSRF state for this org."""
        q = select(self.model).where(
            self.model.state == state,
            self.model.organization_id == ctx.organization.id,
        )
        res = await db.execute(q)
        return res.scalar_one_or_none()

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        final_connection_id: Optional[UUID],
        ctx: ApiContext,
    ) -> ConnectionInitSession:
        """Mark a session as completed and set its final connection ID."""
        obj = await self.get(db, id=session_id, ctx=ctx)
        if not obj:
            return None
        obj.status = ConnectionInitStatus.COMPLETED
        obj.final_connection_id = final_connection_id
        await db.flush()
        return obj


connection_init_session = CRUDConnectionInitSession(ConnectionInitSession)
