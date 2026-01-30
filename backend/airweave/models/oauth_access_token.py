"""OAuth Access Token model for MCP OAuth 2.1."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    pass


class OAuthAccessToken(OrganizationBase, UserMixin):
    """Access tokens for MCP OAuth 2.1.

    These tokens:
    - Grant access to a specific collection
    - Have 1-hour TTL by default
    - Are revocable
    - Are cached in Redis for fast validation
    """

    __tablename__ = "oauth_access_token"

    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(
        String, ForeignKey("oauth_client.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
