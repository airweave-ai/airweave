"""Organization models."""

from typing import TYPE_CHECKING, List

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.user import User


class Organization(Base):
    """Organization model."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Add the users relationship (reciprocal to User.organization)
    users: Mapped[List["User"]] = relationship("User", back_populates="organization")
