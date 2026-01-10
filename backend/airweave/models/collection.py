"""Collection model."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.search_query import SearchQuery
    from airweave.models.source_connection import SourceConnection


class Collection(OrganizationBase, UserMixin):
    """Collection model."""

    __tablename__ = "collection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    readable_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    vector_size: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model_name: Mapped[str] = mapped_column(String, nullable=False)
    sync_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    if TYPE_CHECKING:
        search_queries: List["SearchQuery"]
        source_connections: List["SourceConnection"]

    source_connections: Mapped[list["SourceConnection"]] = relationship(
        "SourceConnection",
        back_populates="collection",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    search_queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery",
        back_populates="collection",
        lazy="noload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
