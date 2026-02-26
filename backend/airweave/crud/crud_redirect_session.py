"""CRUD operations for RedirectSession model."""

import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.redirect_session import RedirectSession

_ALPHABET = string.ascii_letters + string.digits


# TODO: this into base crud


class CRUDRedirectSession:
    """Lightweight CRUD for RedirectSession (not using the org-scoped base helpers)."""

    async def generate_unique_code(
        self, db: AsyncSession, length: int = 8, max_attempts: int = 10
    ) -> str:
        """Generate a unique short code (base62). Retries to avoid collisions."""
        for _ in range(max_attempts):
            code = "".join(secrets.choice(_ALPHABET) for _ in range(length))
            existing = await self.get_by_code(db, code)
            if not existing:
                return code
        # Extremely unlikely; lengthen code if we somehow collided repeatedly
        return "".join(secrets.choice(_ALPHABET) for _ in range(length + 4))

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> RedirectSession:
        """Create a new redirect session with the given parameters.

        Args:
            db: Database session
            code: Unique code for the redirect session
            final_url: URL to redirect to after completion
            expires_at: Expiration datetime for the session
            ctx: API context containing organization info
            uow: Optional unit of work for transaction management

        Returns:
            The created RedirectSession instance
        """
        obj = RedirectSession(
            code=code,
            final_url=final_url,
            expires_at=expires_at,
            organization_id=ctx.organization.id,  # keep it org-scoped
        )
        db.add(obj)
        await db.flush()
        # Only commit if not part of a larger transaction
        if not uow:
            await db.commit()
            await db.refresh(obj)
        return obj

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[RedirectSession]:
        """Retrieve a redirect session by its unique code.

        Args:
            db: Database session
            code: The unique code to search for

        Returns:
            The RedirectSession if found, None otherwise
        """
        q = select(RedirectSession).where(RedirectSession.code == code)
        res = await db.execute(q)
        return res.scalar_one_or_none()

    async def consume(self, db: AsyncSession, code: str, uow: Optional[UnitOfWork] = None) -> None:
        """Delete the mapping (one-time use).

        Args:
            db: Database session
            code: The unique code to delete
            uow: Optional unit of work for transaction management
        """
        q = delete(RedirectSession).where(RedirectSession.code == code)
        await db.execute(q)
        # Only commit if not part of a larger transaction
        if not uow:
            await db.commit()

    @staticmethod
    def is_expired(rs: RedirectSession) -> bool:
        """Check if a redirect session has expired.

        Args:
            rs: The RedirectSession instance to check

        Returns:
            True if the session has expired, False otherwise
        """
        return rs.expires_at <= datetime.now(timezone.utc)


redirect_session = CRUDRedirectSession()
