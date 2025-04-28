"""User model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class User(OrganizationBase):
    """User model."""

    __tablename__ = "user"

    full_name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Define the relationship to Organization
    # Note: In async context, we'll handle eager loading in the CRUD class
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
