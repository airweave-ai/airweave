"""Entity count model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.entity_definition import EntityDefinition
    from airweave.models.sync import Sync


class EntityCount(Base):
    """Entity count model."""

    __tablename__ = "entity_count"

    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_entity_count_sync_id"),
        nullable=False,
    )
    entity_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "entity_definition.id", ondelete="CASCADE", name="fk_entity_count_entity_def_id"
        ),
        nullable=False,
    )
    count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    sync: Mapped["Sync"] = relationship(
        "Sync",
        lazy="noload",
    )

    entity_definition: Mapped["EntityDefinition"] = relationship(
        "EntityDefinition",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_definition_id",
            name="uq_sync_entity_definition",
        ),
        Index("idx_entity_count_sync_id", "sync_id"),
        Index("idx_entity_count_entity_def_id", "entity_definition_id"),
    )
