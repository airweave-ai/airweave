"""Protocols for OAuth domain dependencies."""

from typing import Optional, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.logging import ContextualLogger
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.models.connection import Connection
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.source import Source
from airweave.platform.auth.schemas import OAuth2Settings, OAuth2TokenResponse
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class OAuth1ServiceProtocol(Protocol):
    """OAuth1 authentication flow capability."""

    async def get_request_token(
        self,
        *,
        request_token_url: str,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str,
        logger: ContextualLogger,
    ) -> OAuth1TokenResponse:
        """Obtain temporary credentials (request token)."""
        ...

    async def exchange_token(
        self,
        *,
        access_token_url: str,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        oauth_verifier: str,
        logger: ContextualLogger,
    ) -> OAuth1TokenResponse:
        """Exchange temporary credentials for access token credentials."""
        ...

    def build_authorization_url(
        self,
        *,
        authorization_url: str,
        oauth_token: str,
        app_name: Optional[str] = None,
        scope: Optional[str] = None,
        expiration: Optional[str] = None,
    ) -> str:
        """Build the authorization URL for user consent."""
        ...


class OAuth2ServiceProtocol(Protocol):
    """OAuth2 authentication and token management capability."""

    async def generate_auth_url(
        self,
        oauth2_settings: OAuth2Settings,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> str:
        """Generate the OAuth2 authorization URL for an integration."""
        ...

    async def exchange_authorization_code_for_token(
        self,
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an authorization code for an OAuth2 token."""
        ...

    async def generate_auth_url_with_redirect(
        self,
        oauth2_settings: OAuth2Settings,
        *,
        redirect_uri: str,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> Tuple[str, Optional[str]]:
        """Generate an OAuth2 authorization URL with PKCE support if required.

        Returns (authorization_url, code_verifier).
        """
        ...

    async def exchange_authorization_code_for_token_with_redirect(
        self,
        ctx: ApiContext,
        *,
        source_short_name: str,
        code: str,
        redirect_uri: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict] = None,
        code_verifier: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an OAuth2 code using an explicit redirect_uri."""
        ...

    async def refresh_access_token(
        self,
        db: AsyncSession,
        integration_short_name: str,
        ctx: ApiContext,
        connection_id: UUID,
        decrypted_credential: dict,
        config_fields: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Refresh an OAuth2 access token."""
        ...


class OAuthConnectionRepositoryProtocol(Protocol):
    """Connection data access needed by OAuth flows."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Connection:
        """Get a connection by ID."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        """Create a connection within a unit of work."""
        ...


class OAuthCredentialRepositoryProtocol(Protocol):
    """Integration credential data access needed by OAuth flows."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> IntegrationCredential:
        """Get an integration credential by ID."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: IntegrationCredentialUpdate,
        ctx: ApiContext,
    ) -> IntegrationCredential:
        """Update an integration credential."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> IntegrationCredential:
        """Create an integration credential within a unit of work."""
        ...


class OAuthSourceRepositoryProtocol(Protocol):
    """Source lookup needed for template URL rendering during token refresh."""

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[Source]:
        """Get a source by short_name. Returns None if not found."""
        ...
