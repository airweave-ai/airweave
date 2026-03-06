"""Entity count model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.sync import Sync


class EntityCount(Base):
    """Entity count model.

    Maintained by a PostgreSQL trigger on the entity table.
    """

    __tablename__ = "entity_count"

    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_entity_count_sync_id"),
        nullable=False,
    )
    entity_definition_short_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Registry short_name (e.g. asana_task_entity)",
    )
    count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    sync: Mapped["Sync"] = relationship(
        "Sync",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_definition_short_name",
            name="uq_sync_entity_def_short_name",
        ),
        Index("idx_entity_count_sync_id", "sync_id"),
        Index("idx_entity_count_entity_def_short_name", "entity_definition_short_name"),
    )
