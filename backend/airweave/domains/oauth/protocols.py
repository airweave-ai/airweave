"""Protocols for OAuth2 domain dependencies."""

from typing import Any, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.platform.auth.schemas import OAuth2TokenResponse


class OAuth2ServiceProtocol(Protocol):
    """OAuth2 token refresh capability."""

    async def refresh_access_token(
        self,
        db: AsyncSession,
        integration_short_name: str,
        ctx: ApiContext,
        connection_id: UUID,
        decrypted_credential: dict,
        config_fields: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Refresh an OAuth2 access token.

        Returns an OAuth2TokenResponse with an `access_token` attribute.
        """
        ...


class OAuthConnectionRepositoryProtocol(Protocol):
    """Connection data access needed by OAuth2 flows."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Any:
        """Get a connection by ID."""
        ...

    async def create(
        self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any
    ) -> Any:
        """Create a connection within a unit of work."""
        ...


class OAuthCredentialRepositoryProtocol(Protocol):
    """Integration credential data access needed by OAuth2 flows."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Any:
        """Get an integration credential by ID."""
        ...

    async def update(
        self, db: AsyncSession, *, db_obj: Any, obj_in: Any, ctx: ApiContext
    ) -> Any:
        """Update an integration credential."""
        ...

    async def create(
        self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any
    ) -> Any:
        """Create an integration credential within a unit of work."""
        ...


class CredentialEncryptorProtocol(Protocol):
    """Encrypt/decrypt credential dicts."""

    def encrypt(self, data: dict) -> str:
        """Encrypt a credential dict → encrypted string."""
        ...

    def decrypt(self, encrypted: str) -> dict:
        """Decrypt an encrypted string → credential dict."""
        ...


class OAuthSourceRepositoryProtocol(Protocol):
    """Source lookup needed for template URL rendering during token refresh."""

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Any:
        """Get a source by short_name. Returns None if not found."""
        ...
