"""Integration credential model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import IntegrationType
from airweave.models._base import OrganizationBase, UserMixin
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.models.connection import Connection


class IntegrationCredential(OrganizationBase, UserMixin):
    """Integration credential model."""

    __tablename__ = "integration_credential"

    name: Mapped[str] = mapped_column(String, nullable=False)
    integration_short_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    integration_type: Mapped[IntegrationType] = mapped_column(String, nullable=False)
    # Replace auth_type with authentication_method and oauth_type
    authentication_method: Mapped[AuthenticationMethod] = mapped_column(
        String, nullable=False
    )  # AuthenticationMethod value
    oauth_type: Mapped[Optional[OAuthType]] = mapped_column(
        String, nullable=True
    )  # OAuthType value for OAuth methods
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    auth_config_class: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    connections: Mapped[list["Connection"]] = relationship(
        "Connection", back_populates="integration_credential"
    )
