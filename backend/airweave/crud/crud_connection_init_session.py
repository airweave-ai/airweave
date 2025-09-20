"""CRUD for ConnectionInitSession (with safe create override).

This keeps the global CRUD behavior unchanged and only filters unknown fields
(e.g., auto-injected audit keys) for ConnectionInitSession to avoid TypeError.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import (
    ConnectionInitSession,
    ConnectionInitStatus,
)

from ._base_organization import CRUDBaseOrganization


class CRUDConnectionInitSession(CRUDBaseOrganization[ConnectionInitSession, BaseModel, BaseModel]):
    """CRUD scoped by organization for ConnectionInitSession."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> ConnectionInitSession:
        """Create a new ConnectionInitSession, filtering unknown fields.

        - Ensures organization_id is set
        - Drops any keys not present as columns on the model (e.g., created_by_email)
        - Flushes (and commits only if no active UnitOfWork)
        """
        data = (
            obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else dict(obj_in)
        )

        # Ensure org id is set (defensive)
        data["organization_id"] = ctx.organization.id

        allowed_cols = {c.name for c in self.model.__table__.columns}
        filtered = {k: v for k, v in data.items() if k in allowed_cols}
        unknown = set(data) - allowed_cols
        if unknown:
            logger.warning(
                f"[ConnectionInitSession.create] Dropping unknown fields: {sorted(unknown)}"
            )

        obj = self.model(**filtered)
        db.add(obj)
        await db.flush()
        if not uow:
            await db.commit()
        return obj

    async def get_by_state(
        self,
        db: AsyncSession,
        *,
        state: str,
        ctx: ApiContext,
    ) -> Optional[ConnectionInitSession]:
        """Fetch a session by its state, scoped to the caller's org."""
        q = select(self.model).where(
            self.model.state == state,
            self.model.organization_id == ctx.organization.id,
        )
        res = await db.execute(q)
        return res.scalar_one_or_none()

    async def get_by_state_no_auth(
        self,
        db: AsyncSession,
        *,
        state: str,
    ) -> Optional[ConnectionInitSession]:
        """Fetch a session by its state without auth validation.

        Used for OAuth callbacks where the user is not yet authenticated.
        """
        q = select(self.model).where(
            self.model.state == state,
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
    ) -> Optional[ConnectionInitSession]:
        """Mark a session completed and store the resulting connection id."""
        obj = await self.get(db, id=session_id, ctx=ctx)
        if not obj:
            return None
        obj.status = ConnectionInitStatus.COMPLETED
        obj.final_connection_id = final_connection_id
        db.add(obj)
        await db.flush()
        return obj


# track_user=False is harmless here, but emphasizes we don't want audit
# fields for this ephemeral table
connection_init_session = CRUDConnectionInitSession(ConnectionInitSession, track_user=False)
