"""Models for entity relations."""

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base


class EntityRelation(Base):
    """Relation between two entity types."""

    __tablename__ = "entity_relation"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    from_entity_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_definition.id"), nullable=False
    )
    to_entity_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_definition.id"), nullable=False
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("organization.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "from_entity_definition_id",
            "to_entity_definition_id",
            "name",
            "organization_id",
            name="uq_entity_relation",
        ),
        Index("idx_entity_relation_from", "from_entity_definition_id"),
        Index("idx_entity_relation_to", "to_entity_definition_id"),
    )
