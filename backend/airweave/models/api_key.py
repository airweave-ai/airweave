"""Api key model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase, UserMixin


class APIKey(OrganizationBase, UserMixin):
    """SQLAlchemy model for the APIKey table."""

    __tablename__ = "api_key"

    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    encrypted_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    last_used_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    last_used_ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    key_prefix: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    # Nullable during transition; make NOT NULL after backfill is verified
    key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("ix_api_key_key_hash", "key_hash", unique=True),)
