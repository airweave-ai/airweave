"""Collection model."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.source_connection import SourceConnection


class Collection(OrganizationBase, UserMixin):
    """Collection model."""

    __tablename__ = "collection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    readable_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    vector_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Status is now ephemeral - removed from database model

    # Relationships
    if TYPE_CHECKING:
        source_connections: List["SourceConnection"]

    source_connections: Mapped[list["SourceConnection"]] = relationship(
        "SourceConnection",
        back_populates="collection",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
