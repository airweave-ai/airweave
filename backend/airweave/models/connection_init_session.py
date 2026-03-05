"""Ephemeral session model for unified source-connection initiation flow."""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.redirect_session import RedirectSession
    from airweave.models.source_connection import SourceConnection


class ConnectionInitStatus:
    """String constants representing ConnectionInitSession lifecycle states."""

    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ConnectionInitSession(OrganizationBase):
    """Short-lived, org-scoped session for completing OAuth-style flows.

    Stores the information needed to finalize creation of a SourceConnection.

    We store:
      - payload: the same core fields you pass to create a SourceConnection (name, collection, etc.)
      - overrides: BYOC client_id/secret, post-auth redirect_url, token-injection tokens, etc.
      - state: CSRF/state value sent to the OAuth provider
      - status/expires_at: lifecycle/TTL
    """

    __tablename__ = "connection_init_session"

    short_name: Mapped[str] = mapped_column(String, nullable=False)

    # Core inputs (name, description, collection, config_fields, cron, sync flag, etc.)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Overrides (client_id, client_secret, redirect_url, access_token, refresh_token, etc.)
    overrides: Mapped[dict] = mapped_column(JSON, nullable=False)

    # OAuth state + lifecycle
    state: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=ConnectionInitStatus.PENDING
    )

    # Expiration for security; default TTL ~30 minutes can be applied at creation
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Set when finalized (optional)
    final_connection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("connection.id", ondelete="SET NULL"), nullable=True
    )

    # Link to the redirect session for auth URL
    redirect_session_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("redirect_session.id", ondelete="SET NULL"), nullable=True
    )

    source_connection: Mapped[Optional["SourceConnection"]] = relationship(
        back_populates="connection_init_session"
    )

    redirect_session: Mapped[Optional["RedirectSession"]] = relationship("RedirectSession")

    __table_args__ = (Index("idx_connection_init_session_expires_at", "expires_at"),)

    @staticmethod
    def default_expires_at(minutes: int = 30) -> datetime:
        """Return a UTC expiry timestamp ``minutes`` from now."""
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
