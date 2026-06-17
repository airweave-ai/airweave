"""Concrete session repository."""

from typing import Any, Optional, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.datetime_utils import utc_now_naive
from airweave.domains.sessions.protocols import SessionRepositoryProtocol
from airweave.models.user_session import UserSession


class SessionRepository(SessionRepositoryProtocol):
    """Implements SessionRepositoryProtocol with direct DB access."""

    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> Optional[UserSession]:
        """Return session by Auth0 sid, or None if not found."""
        stmt = select(UserSession).where(UserSession.session_id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_user(self, db: AsyncSession, user_id: UUID) -> list[UserSession]:
        """Return all non-revoked sessions for a user."""
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
            .order_by(UserSession.last_active_at.desc().nullslast())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> UserSession:
        """Create a new session record."""
        now = utc_now_naive()
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else user_agent,
            last_active_at=now,
        )
        db.add(session)
        await db.flush()
        return session

    async def revoke(self, db: AsyncSession, session_id: str, *, user_id: UUID) -> None:
        """Mark a single session as revoked (scoped by user_id for defense-in-depth)."""
        stmt = (
            update(UserSession)
            .where(UserSession.session_id == session_id, UserSession.user_id == user_id)
            .values(is_revoked=True, modified_at=utc_now_naive())
        )
        await db.execute(stmt)
        await db.flush()

    async def revoke_all_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        except_session_id: Optional[str] = None,
    ) -> int:
        """Revoke all sessions for a user. Returns count of revoked sessions."""
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .values(is_revoked=True, modified_at=utc_now_naive())
        )
        if except_session_id is not None:
            stmt = stmt.where(UserSession.session_id != except_session_id)
        result = await db.execute(stmt)
        await db.flush()
        return int(cast("CursorResult[Any]", result).rowcount)

    async def update_last_active(self, db: AsyncSession, session_id: str) -> None:
        """Update last_active_at for a session."""
        stmt = (
            update(UserSession)
            .where(UserSession.session_id == session_id)
            .values(last_active_at=utc_now_naive())
        )
        await db.execute(stmt)
        await db.flush()
