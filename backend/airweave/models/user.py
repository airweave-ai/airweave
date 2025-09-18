"""User model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import UUID, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.search_query import SearchQuery
    from airweave.models.user_organization import UserOrganization


class User(Base):
    """User model."""

    __tablename__ = "user"

    full_name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Many-to-many relationship with organizations
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    # Search queries performed by this user
    search_queries: Mapped[List["SearchQuery"]] = relationship(
        "SearchQuery", back_populates="user", lazy="noload"
    )

    @property
    def primary_organization_id(self) -> UUID | None:
        """Get the primary organization ID from the relationship."""
        for user_org in self.user_organizations:
            if user_org.is_primary:
                return user_org.organization_id
        return None
