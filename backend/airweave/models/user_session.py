"""User session model for per-session tracking."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.user import User


class UserSession(Base):
    """Tracks individual Auth0 sessions for a user.

    Each session maps to an Auth0 ``sid`` claim injected by
    the Post Login Action. Enables per-session visibility and
    targeted revocation.
    """

    __tablename__ = "user_session"
    __table_args__ = (Index("ix_user_session_user_id_is_revoked", "user_id", "is_revoked"),)

    user_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Reserved for future session-max-lifetime enforcement; not yet populated.
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="user_sessions", lazy="noload")
