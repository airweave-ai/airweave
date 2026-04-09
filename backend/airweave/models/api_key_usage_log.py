"""API key usage log model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base


class APIKeyUsageLog(Base):
    """Tracks individual API key usage events for audit and analytics."""

    __tablename__ = "api_key_usage_log"

    api_key_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_key.id", ondelete="SET NULL"), nullable=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ip_address: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_api_key_usage_log_key_ts", "api_key_id", "timestamp"),
        Index("ix_api_key_usage_log_org_ts", "organization_id", "timestamp"),
        Index("ix_api_key_usage_log_timestamp", "timestamp"),
    )
