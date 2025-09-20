"""Models for sources."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.connection import Connection


class Source(Base):
    """A source that can produce entities."""

    __tablename__ = "source"

    name = Column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[str] = mapped_column(String, nullable=True)
    config_class: Mapped[str] = mapped_column(String, nullable=True)
    # New fields for auth refactor
    auth_methods = Column(JSON, nullable=True)  # List of AuthenticationMethod values
    oauth_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # OAuthType value
    requires_byoc: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    description = Column(String)
    organization_id = Column(ForeignKey("organization.id"), nullable=True)
    # List of entity IDs this source can output
    output_entity_definition_ids = Column(JSON, nullable=False)
    config_schema = Column(JSON, nullable=True)  # JSON Schema for configuration
    labels: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)

    __table_args__ = (UniqueConstraint("name", "organization_id", name="uq_source_name_org"),)

    # Back-reference to connections
    connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        primaryjoin="and_(foreign(Connection.short_name) == Source.short_name, "
        "Connection.integration_type == 'SOURCE')",
        back_populates="source",
        lazy="noload",
        viewonly=True,
    )
