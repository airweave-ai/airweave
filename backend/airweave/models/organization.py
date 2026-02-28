"""Organization models."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.billing_period import BillingPeriod
    from airweave.models.feature_flag import FeatureFlag
    from airweave.models.organization_billing import OrganizationBilling
    from airweave.models.source_rate_limit import SourceRateLimit
    from airweave.models.usage import Usage
    from airweave.models.user_organization import UserOrganization


class Organization(Base):
    """Organization model."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String, unique=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth0_org_id: Mapped[str] = mapped_column(String, nullable=True)  # Auth0 organization ID

    # Organization metadata for storing onboarding and other flexible data
    org_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default={})

    # Many-to-many relationship with users
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Relationship with usage
    usage: Mapped[List["Usage"]] = relationship(
        "Usage",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # One-to-one relationship with billing (optional for OSS compatibility)
    billing: Mapped[Optional["OrganizationBilling"]] = relationship(
        "OrganizationBilling",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
        uselist=False,  # One-to-one
    )

    # Relationship with billing periods
    billing_periods: Mapped[List["BillingPeriod"]] = relationship(
        "BillingPeriod",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="desc(BillingPeriod.period_start)",  # Most recent first
    )

    # Relationship with feature flags (loaded via selectinload in CRUD)
    feature_flags: Mapped[List["FeatureFlag"]] = relationship(
        "FeatureFlag",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Relationship with source rate limits
    source_rate_limits: Mapped[List["SourceRateLimit"]] = relationship(
        "SourceRateLimit",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (Index("idx_organization_auth0_org_id", "auth0_org_id"),)
