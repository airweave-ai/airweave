"""CRUD operations for OAuth Authorization Code model."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.oauth_authorization_code import OAuthAuthorizationCode


class CRUDOAuthAuthorizationCode(
    CRUDBaseOrganization[
        OAuthAuthorizationCode,
        schemas.OAuthAuthorizationCodeCreate,
        schemas.OAuthAuthorizationCodeUpdate,
    ]
):
    """CRUD operations for OAuth authorization codes."""

    async def get_by_code(
        self, db: AsyncSession, *, code_hash: str
    ) -> Optional[OAuthAuthorizationCode]:
        """Get authorization code by hash.

        Args:
            db: Database session
            code_hash: SHA256 hash of the authorization code

        Returns:
            OAuthAuthorizationCode model or None if not found
        """
        query = select(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.code_hash == code_hash
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def mark_as_used(self, db: AsyncSession, *, code_id: UUID) -> None:
        """Mark authorization code as used.

        Args:
            db: Database session
            code_id: Authorization code ID
        """
        query = select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.id == code_id)
        result = await db.execute(query)
        code = result.scalar_one_or_none()
        
        if not code:
            raise NotFoundException(f"Authorization code {code_id} not found")
        
        code.used_at = utc_now_naive()
        await db.commit()

    async def cleanup_expired_codes(self, db: AsyncSession) -> int:
        """Delete expired authorization codes.

        Args:
            db: Database session

        Returns:
            Number of deleted codes
        """
        from sqlalchemy import delete

        now = utc_now_naive()
        query = delete(OAuthAuthorizationCode).where(OAuthAuthorizationCode.expires_at < now)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount


oauth_authorization_code = CRUDOAuthAuthorizationCode(OAuthAuthorizationCode)
