"""Source rate limit model."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class SourceRateLimit(OrganizationBase, UserMixin):
    """Rate limit configuration for source API calls.

    Stores ONE limit per (organization, source) combination. The limit applies
    to all users/connections, but counts are tracked separately in Redis based
    on the source's rate_limit_level:
    - Connection-level (Notion): Redis tracks per user connection
    - Org-level (Google Drive): Redis tracks for entire org

    Example:
        Org 1 + Notion → limit=3 req/sec (applies to ALL Notion users)
        Org 1 + Google Drive → limit=800 req/min (applies to entire org)
    """

    __tablename__ = "source_rate_limits"

    source_short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    limit: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="source_rate_limits", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_short_name",
            name="uq_org_source_rate_limit",
        ),
    )
