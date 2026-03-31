"""Connection model."""

from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, event, text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.auth_provider import AuthProvider
    from airweave.models.integration_credential import IntegrationCredential
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync_connection import SyncConnection


class Connection(Base):
    """Connection model to manage relationships between integrations and their credentials.

    This is a system table that contains the connection information for all integrations.
    Not to be confused with the source connection model, which is a user-facing model that
    encompasses the connection and sync information for a specific source.
    """

    __tablename__ = "connection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    readable_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    integration_type: Mapped[IntegrationType] = mapped_column(
        SQLAlchemyEnum(IntegrationType), nullable=False
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        SQLAlchemyEnum(ConnectionStatus), default=ConnectionStatus.ACTIVE
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=True
    )
    created_by_email: Mapped[str] = mapped_column(String, nullable=True)
    modified_by_email: Mapped[str] = mapped_column(String, nullable=True)

    # Foreign keys
    integration_credential_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("integration_credential.id", ondelete="SET NULL"), nullable=True
    )
    short_name: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    integration_credential: Mapped[Optional["IntegrationCredential"]] = relationship(
        "IntegrationCredential", back_populates="connections", lazy="noload"
    )
    auth_provider: Mapped[Optional["AuthProvider"]] = relationship(
        "AuthProvider",
        primaryjoin="and_(foreign(Connection.short_name)==remote(AuthProvider.short_name), "
        "Connection.integration_type=='AUTH_PROVIDER')",
        foreign_keys=[short_name],
        viewonly=True,
        lazy="noload",
    )

    source_connection: Mapped[Optional["SourceConnection"]] = relationship(
        "SourceConnection",
        foreign_keys="[SourceConnection.connection_id]",
        back_populates="connection",
        lazy="noload",
    )

    sync_connections: Mapped[List["SyncConnection"]] = relationship(
        "SyncConnection",
        back_populates="connection",
        lazy="noload",
    )

    # Source connections that use this connection as an auth provider
    # This enables cascade deletion when an auth provider connection is deleted
    source_connections_using_auth_provider: Mapped[List["SourceConnection"]] = relationship(
        "SourceConnection",
        foreign_keys="[SourceConnection.readable_auth_provider_id]",
        primaryjoin="and_(SourceConnection.readable_auth_provider_id==Connection.readable_id, "
        "Connection.integration_type=='AUTH_PROVIDER')",
        cascade="all, delete-orphan",
        viewonly=False,
        lazy="noload",
        passive_deletes=False,  # Force Python-side cascade
    )

    __table_args__ = (
        CheckConstraint(
            """
            (short_name IN ('qdrant_native', 'neo4j_native', 'vespa_native', 'local_text2vec'))
            OR
            (organization_id IS NOT NULL
             AND created_by_email IS NOT NULL
             AND modified_by_email IS NOT NULL)
            """,
            name="ck_connection_native_or_complete",
        ),
        Index("idx_connection_organization_id", "organization_id"),
        Index("idx_connection_integration_credential_id", "integration_credential_id"),
    )


# Event to delete integration credential when Connection is deleted
@event.listens_for(Connection, "after_delete")
def delete_integration_credential(mapper: Any, connection: Any, target: Any) -> None:
    """When a Connection is deleted, also delete its IntegrationCredential if present."""
    if target.integration_credential_id:
        connection.execute(
            text("DELETE FROM integration_credential WHERE id = :id"),
            {"id": str(target.integration_credential_id)},
        )
