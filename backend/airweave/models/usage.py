"""Usage model for tracking organization subscription usage."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.billing_period import BillingPeriod
    from airweave.models.organization import Organization


class Usage(OrganizationBase):
    """Usage model for tracking organization subscription limits per billing period."""

    __tablename__ = "usage"

    # Link to billing period (unique constraint ensures one usage per period)
    billing_period_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("billing_period.id", ondelete="CASCADE"),
        nullable=True,  # Nullable initially for migration
        unique=True,
    )

    # Usage counters with server defaults
    entities: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    queries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="usage",
        lazy="noload",
    )

    billing_period: Mapped[Optional["BillingPeriod"]] = relationship(
        "BillingPeriod",
        back_populates="usage",
        lazy="noload",
    )

    __table_args__ = (
        # Index for efficient lookup by organization
        Index("ix_usage_organization_id", "organization_id"),
        # Index for efficient lookup by billing period
        Index("ix_usage_billing_period_id", "billing_period_id"),
    )
