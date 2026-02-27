"""Protocols for OAuth domain dependencies."""

from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.logging import ContextualLogger
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.oauth.types import OAuth1TokenResponse, OAuthBrowserInitiationResult
from airweave.models.connection import Connection
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.source import Source
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2Settings, OAuth2TokenResponse
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)
from airweave.schemas.source_connection import SourceConnection as SourceConnectionSchema


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


# ---------------------------------------------------------------------------
# Init session + redirect session repositories
# ---------------------------------------------------------------------------


class OAuthInitSessionRepositoryProtocol(Protocol):
    """Data access for ConnectionInitSession records."""

    async def get_by_state_no_auth(
        self, db: AsyncSession, *, state: str
    ) -> Optional[ConnectionInitSession]:
        """Look up a pending init session by OAuth2 state token (no auth check)."""
        ...

    async def get_by_oauth_token_no_auth(
        self, db: AsyncSession, *, oauth_token: str
    ) -> Optional[ConnectionInitSession]:
        """Look up a pending init session by OAuth1 request token (no auth check)."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> ConnectionInitSession:
        """Persist a new init session."""
        ...

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        final_connection_id: Optional[UUID],
        ctx: ApiContext,
    ) -> None:
        """Transition session to COMPLETED and record final connection."""
        ...


class OAuthRedirectSessionRepositoryProtocol(Protocol):
    """Data access for short-lived redirect (proxy URL) sessions."""

    async def generate_unique_code(self, db: AsyncSession, *, length: int) -> str:
        """Generate a unique short code for a redirect session."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Any:
        """Persist a new redirect session and return it."""
        ...

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Any]:
        """Get a redirect session by its unique code."""
        ...


# ---------------------------------------------------------------------------
# Higher-level OAuth service protocols
# ---------------------------------------------------------------------------


class OAuthFlowServiceProtocol(Protocol):
    """Manages the OAuth handshake lifecycle (URL generation, token exchange, session state)."""

    async def initiate_oauth2(
        self,
        short_name: str,
        state: str,
        *,
        client_id: Optional[str] = None,
        template_configs: Optional[dict] = None,
        ctx: ApiContext,
    ) -> Tuple[str, Optional[str]]:
        """Generate OAuth2 authorization URL. Returns (provider_auth_url, code_verifier)."""
        ...

    async def initiate_oauth1(
        self,
        short_name: str,
        *,
        consumer_key: str,
        consumer_secret: str,
        ctx: ApiContext,
    ) -> Tuple[str, Dict[str, str]]:
        """Start OAuth1 flow. Returns (provider_auth_url, oauth1_overrides)."""
        ...

    async def initiate_browser_flow(
        self,
        *,
        short_name: str,
        oauth_type: Optional[str],
        state: str,
        nested_client_id: Optional[str],
        nested_client_secret: Optional[str],
        nested_consumer_key: Optional[str],
        nested_consumer_secret: Optional[str],
        template_configs: Optional[dict],
        ctx: ApiContext,
    ) -> OAuthBrowserInitiationResult:
        """Start browser OAuth flow and return normalized init-session data."""
        ...

    async def complete_oauth2_callback(
        self,
        short_name: str,
        code: str,
        overrides: Dict[str, Any],
        ctx: ApiContext,
    ) -> OAuth2TokenResponse:
        """Exchange OAuth2 authorization code for tokens."""
        ...

    async def complete_oauth1_callback(
        self,
        short_name: str,
        verifier: str,
        overrides: Dict[str, Any],
        oauth_settings: OAuth1Settings,
        ctx: ApiContext,
    ) -> OAuth1TokenResponse:
        """Exchange OAuth1 verifier for access token."""
        ...

    async def create_init_session(
        self,
        db: AsyncSession,
        *,
        short_name: str,
        state: str,
        payload: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
        redirect_session_id: Optional[UUID] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        oauth_client_mode: Optional[str] = None,
        redirect_url: Optional[str] = None,
        template_configs: Optional[dict] = None,
        additional_overrides: Optional[Dict[str, Any]] = None,
    ) -> ConnectionInitSession:
        """Persist an init session for a new OAuth flow."""
        ...

    async def create_proxy_url(
        self,
        db: AsyncSession,
        provider_auth_url: str,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Tuple[str, datetime, UUID]:
        """Create proxy redirect URL. Returns (proxy_url, proxy_expires, redirect_session_id)."""
        ...


class OAuthCallbackServiceProtocol(Protocol):
    """Completes browser-based OAuth callback flows end-to-end."""

    async def complete_oauth_callback(
        self,
        db: AsyncSession,
        *,
        state: Optional[str] = None,
        code: Optional[str] = None,
        oauth_token: Optional[str] = None,
        oauth_verifier: Optional[str] = None,
    ) -> SourceConnectionSchema:
        """Complete OAuth callback by auto-detecting OAuth1 vs OAuth2 parameter set."""
        ...

    async def complete_oauth2_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> SourceConnectionSchema:
        """Complete OAuth2 callback: exchange code, wire credential + connection, trigger sync."""
        ...

    async def complete_oauth1_callback(
        self,
        db: AsyncSession,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SourceConnectionSchema:
        """Complete OAuth1 callback.

        Exchange verifier, wire credential + connection, trigger sync.
        """
        ...
