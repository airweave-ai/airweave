"""Protocols for the sessions domain."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.user_session import UserSession


class SessionRepositoryProtocol(Protocol):
    """Per-session CRUD used by auth layer and session management endpoints."""

    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> Optional[UserSession]:
        """Return session by Auth0 sid, or None if not found."""
        ...

    async def get_active_by_user(self, db: AsyncSession, user_id: UUID) -> list[UserSession]:
        """Return all non-revoked sessions for a user."""
        ...

    async def create(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> UserSession:
        """Create a new session record."""
        ...

    async def revoke(self, db: AsyncSession, session_id: str, *, user_id: UUID) -> None:
        """Mark a single session as revoked (scoped by user_id for defense-in-depth)."""
        ...

    async def revoke_all_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        except_session_id: Optional[str] = None,
    ) -> int:
        """Revoke all sessions for a user. Returns count of revoked sessions."""
        ...

    async def update_last_active(self, db: AsyncSession, session_id: str) -> None:
        """Update last_active_at for a session."""
        ...
