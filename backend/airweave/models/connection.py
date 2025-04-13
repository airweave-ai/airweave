"""Connection model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.destination import Destination
    from airweave.models.embedding_model import EmbeddingModel
    from airweave.models.integration_credential import IntegrationCredential
    from airweave.models.source import Source


class Connection(Base):
    """Connection model to manage relationships between integrations and their credentials."""

    __tablename__ = "connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    integration_type: Mapped[IntegrationType] = mapped_column(
        SQLAlchemyEnum(IntegrationType), nullable=False
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        SQLAlchemyEnum(ConnectionStatus), default=ConnectionStatus.ACTIVE
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"), nullable=True)
    created_by_email: Mapped[str] = mapped_column(String, nullable=True)
    modified_by_email: Mapped[str] = mapped_column(String, nullable=True)

    # Foreign keys
    integration_credential_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("integration_credential.id"), nullable=True
    )
    short_name: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    integration_credential: Mapped[Optional["IntegrationCredential"]] = relationship(
        "IntegrationCredential", back_populates="connections"
    )
    source: Mapped[Optional["Source"]] = relationship(
        "Source",
        primaryjoin="and_(foreign(Connection.short_name)==remote(Source.short_name), "
        "Connection.integration_type=='SOURCE')",
        foreign_keys=[short_name],
        viewonly=True,
        lazy="noload",
    )
    destination: Mapped[Optional["Destination"]] = relationship(
        "Destination",
        primaryjoin="and_(foreign(Connection.short_name)==remote(Destination.short_name), "
        "Connection.integration_type=='DESTINATION')",
        foreign_keys=[short_name],
        viewonly=True,
        lazy="noload",
    )
    embedding_model: Mapped[Optional["EmbeddingModel"]] = relationship(
        "EmbeddingModel",
        primaryjoin="and_(foreign(Connection.short_name)==remote(EmbeddingModel.short_name), "
        "Connection.integration_type=='EMBEDDING_MODEL')",
        foreign_keys=[short_name],
        viewonly=True,
        lazy="noload",
    )

    __table_args__ = (
        # Enforce that organization_id, created_by_email, and modified_by_email are not null
        # except for the specific native connections
        CheckConstraint(
            """
            (short_name IN ('weaviate_native', 'neo4j_native', 'local_text2vec'))
            OR
            (organization_id IS NOT NULL AND created_by_email IS NOT NULL AND
            modified_by_email IS NOT NULL)
            """,
            name="ck_connection_native_or_complete",
        ),
    )
