"""OAuth Authorization Code model for MCP OAuth 2.1."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    pass


class OAuthAuthorizationCode(OrganizationBase, UserMixin):
    """One-time authorization codes issued during OAuth flow.

    These codes are exchanged for access tokens and must be:
    - Single-use only
    - Short-lived (10 minutes)
    - Bound to specific client_id and redirect_uri
    """

    __tablename__ = "oauth_authorization_code"

    code_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(
        String, ForeignKey("oauth_client.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)  # "read:collection"
    code_challenge: Mapped[str] = mapped_column(
        String, nullable=True
    )  # PKCE challenge (S256 hash)
    code_challenge_method: Mapped[str] = mapped_column(
        String, nullable=True
    )  # "S256" for PKCE
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=True
    )  # Mark as used to prevent reuse
