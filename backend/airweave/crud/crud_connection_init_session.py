"""CRUD for ConnectionInitSession (with safe create override).

This keeps the global CRUD behavior unchanged and only filters unknown fields
(e.g., auto-injected audit keys) for ConnectionInitSession to avoid TypeError.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
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
        ctx: BaseContext,
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
        ctx: BaseContext,
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

        Used for OAuth2 callbacks where the user is not yet authenticated.
        """
        q = select(self.model).where(
            self.model.state == state,
        )
        res = await db.execute(q)
        return res.scalar_one_or_none()

    async def get_by_oauth_token_no_auth(
        self,
        db: AsyncSession,
        *,
        oauth_token: str,
    ) -> Optional[ConnectionInitSession]:
        """Fetch a session by OAuth1 request token without auth validation.

        Used for OAuth1 callbacks. OAuth1 doesn't send our state parameter back,
        so we look up the session by the oauth_token stored in overrides.

        Args:
            db: Database session
            oauth_token: OAuth1 request token from the callback

        Returns:
            ConnectionInitSession if found, None otherwise
        """
        # Debug: Log what we're searching for
        logger.debug(f"Searching for OAuth1 session with oauth_token: {oauth_token}")

        # First, let's try to find ANY pending session and check its overrides
        all_pending = select(self.model).where(
            self.model.status == ConnectionInitStatus.PENDING,
        )
        all_res = await db.execute(all_pending)
        all_sessions = all_res.scalars().all()

        logger.debug(f"Found {len(all_sessions)} pending sessions")
        for session in all_sessions:
            oauth_token_value = session.overrides.get("oauth_token") if session.overrides else None
            logger.debug(
                f"Session {session.id}: overrides={session.overrides}, "
                f"has oauth_token={oauth_token_value}"
            )
            # Match manually
            if session.overrides and session.overrides.get("oauth_token") == oauth_token:
                logger.debug(f"Found matching session: {session.id}")
                return session

        logger.warning(f"No OAuth1 session found with oauth_token: {oauth_token}")
        return None

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        final_connection_id: Optional[UUID],
        ctx: BaseContext,
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
