"""CRUD operations for OAuth Access Token model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.oauth_access_token import OAuthAccessToken


class CRUDOAuthAccessToken(
    CRUDBaseOrganization[OAuthAccessToken, schemas.OAuthAccessTokenCreate, schemas.OAuthAccessTokenUpdate]
):
    """CRUD operations for OAuth access tokens."""

    async def get_by_token(
        self, db: AsyncSession, *, token_hash: str
    ) -> Optional[OAuthAccessToken]:
        """Get access token by hash.

        Args:
            db: Database session
            token_hash: SHA256 hash of the access token

        Returns:
            OAuthAccessToken model or None if not found
        """
        query = select(OAuthAccessToken).where(OAuthAccessToken.token_hash == token_hash)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def revoke_token(self, db: AsyncSession, *, token_id: UUID) -> None:
        """Revoke an access token.

        Args:
            db: Database session
            token_id: Access token ID
        """
        query = select(OAuthAccessToken).where(OAuthAccessToken.id == token_id)
        result = await db.execute(query)
        token = result.scalar_one_or_none()
        
        if not token:
            raise NotFoundException(f"Access token {token_id} not found")
        
        token.revoked_at = utc_now_naive()
        await db.commit()

    async def cleanup_expired_tokens(self, db: AsyncSession) -> int:
        """Delete expired and revoked access tokens.

        Args:
            db: Database session

        Returns:
            Number of deleted tokens
        """
        from sqlalchemy import delete, or_

        now = utc_now_naive()
        query = delete(OAuthAccessToken).where(
            or_(
                OAuthAccessToken.expires_at < now,
                OAuthAccessToken.revoked_at.isnot(None),
            )
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount


oauth_access_token = CRUDOAuthAccessToken(OAuthAccessToken)
