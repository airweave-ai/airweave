"""OAuth Client model for MCP OAuth 2.1 authorization server."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base

if TYPE_CHECKING:
    pass


class OAuthClient(Base):
    """OAuth client registration for MCP clients (Claude Desktop, Cursor, etc.)."""

    __tablename__ = "oauth_client"

    client_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    client_secret_hash: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Null for public clients
    name: Mapped[str] = mapped_column(String, nullable=False)
    redirect_uris: Mapped[list] = mapped_column(JSON, nullable=False)  # List of allowed URIs
    grant_types: Mapped[list] = mapped_column(
        JSON, nullable=False
    )  # ["authorization_code", "refresh_token"]
    client_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "public" or "confidential"
