"""Models for handling ephemeral redirect sessions for OAuth flows."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase


class RedirectSession(OrganizationBase):
    """Ephemeral, one-time redirect mapping.

    Maps /source-connections/authorize/{code} -> final URL (app) with query params.

    Security:
    - Short TTL (configurable), one-time-use.
    - Code is unique & unguessable (generated elsewhere).
    """

    __tablename__ = "redirect_session"

    # Short code users will hit (8-char base62 recommended)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    # Absolute final URL to redirect to (e.g., app URL with ?status=... etc.)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Expiry; entries are consumed (deleted) on first use or when expired
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_redirect_session_expires_at", "expires_at"),)

    @staticmethod
    def default_expires_at(minutes: int = 5) -> datetime:
        """Generate a default expiration datetime for redirect sessions.

        Args:
            minutes: Number of minutes from now until expiration (default: 5)

        Returns:
            A datetime object representing the expiration time in UTC
        """
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
