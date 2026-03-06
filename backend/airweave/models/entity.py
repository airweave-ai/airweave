"""Entity model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.sync import Sync
    from airweave.models.sync_job import SyncJob


class Entity(OrganizationBase):
    """Entity model."""

    __tablename__ = "entity"

    # Override organization_id to disable index (table too large, better indexes exist)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=False,  # Disabled: billions of rows, not selective, better indexes on sync_id
    )

    sync_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_job.id", ondelete="CASCADE", name="fk_entity_sync_job_id"), nullable=False
    )
    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_entity_sync_id"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    entity_definition_short_name: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment="Entity definition short_name from the registry (e.g. asana_task_entity)",
    )
    hash: Mapped[str] = mapped_column(String, nullable=False)

    # Add back references
    sync_job: Mapped["SyncJob"] = relationship(
        "SyncJob",
        back_populates="entities",
        lazy="noload",
    )

    sync: Mapped["Sync"] = relationship(
        "Sync",
        back_populates="entities",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_id",
            "entity_definition_short_name",
            name="uq_sync_id_entity_id_entity_def_short_name",
        ),
        Index("idx_entity_sync_id", "sync_id"),
        Index("idx_entity_sync_job_id", "sync_job_id"),
        Index("idx_entity_entity_id", "entity_id"),
        Index("idx_entity_entity_def_short_name", "entity_definition_short_name"),
        Index("idx_entity_entity_id_sync_id", "entity_id", "sync_id"),
        Index(
            "idx_entity_sync_id_entity_def_short_name",
            "sync_id",
            "entity_definition_short_name",
        ),
    )
