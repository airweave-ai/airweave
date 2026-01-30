"""OAuth Refresh Token model for MCP OAuth 2.1 (future use)."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    pass


class OAuthRefreshToken(OrganizationBase, UserMixin):
    """Refresh tokens for long-lived MCP sessions (future feature).

    These tokens:
    - Can be exchanged for new access tokens
    - Have 30-day TTL by default
    - Are bound to specific access tokens
    - Are revocable
    """

    __tablename__ = "oauth_refresh_token"

    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    access_token_id: Mapped[UUID] = mapped_column(
        ForeignKey("oauth_access_token.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        String, ForeignKey("oauth_client.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
