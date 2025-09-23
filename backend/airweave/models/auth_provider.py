"""Auth provider model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.connection import Connection


class AuthProvider(Base):
    """Auth provider definition for 3rd party authentication services.

    Auth providers define the available authentication services (e.g., Google OAuth, GitHub)
    that can be used to authenticate and obtain credentials for accessing external data sources.
    This is a system-level definition, similar to Source and Destination models.
    """

    __tablename__ = "auth_provider"

    name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, unique=True)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    auth_config_class: Mapped[str] = mapped_column(String, nullable=False)
    config_class: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("organization.id"), nullable=True
    )  # Null for system providers

    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_auth_provider_name_org"),
    )

    # Back-reference to connections using this auth provider
    connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        primaryjoin="and_(foreign(Connection.short_name) == AuthProvider.short_name, "
        "Connection.integration_type == 'AUTH_PROVIDER')",
        back_populates="auth_provider",
        lazy="noload",
        viewonly=True,
    )
