"""Collection model."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.search_query import SearchQuery
    from airweave.models.source_connection import SourceConnection
    from airweave.models.vector_db_deployment_metadata import VectorDbDeploymentMetadata


class Collection(OrganizationBase, UserMixin):
    """Collection model."""

    __tablename__ = "collection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    readable_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    vector_db_deployment_metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("vector_db_deployment_metadata.id"), nullable=False
    )
    sync_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    vector_db_deployment_metadata: Mapped["VectorDbDeploymentMetadata"] = relationship(
        "VectorDbDeploymentMetadata", lazy="joined"
    )

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
