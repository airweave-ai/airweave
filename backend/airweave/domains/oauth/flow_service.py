"""OAuth flow service — manages the OAuth handshake lifecycle.

Owns URL generation, token exchange, and session state persistence.
Does NOT know about source connections, credentials, or syncs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.config import Settings
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.oauth.protocols import (
    OAuth1ServiceProtocol,
    OAuth2ServiceProtocol,
    OAuthInitSessionRepositoryProtocol,
    OAuthRedirectSessionRepositoryProtocol,
)
from airweave.domains.oauth.types import OAuth1TokenResponse, OAuthBrowserInitiationResult
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2TokenResponse
from airweave.platform.auth.settings import IntegrationSettings


class OAuthFlowService:
    """Manages the OAuth handshake lifecycle.

    Responsibilities:
    - Generate provider authorization URLs (OAuth1 request token + URL, OAuth2 URL + PKCE)
    - Exchange authorization codes/verifiers for access tokens
    - Persist init sessions (OAuth flow state) and proxy redirect URLs

    Does NOT know about source connections, credentials, or syncs.
    """

    def __init__(
        self,
        *,
        oauth2_service: OAuth2ServiceProtocol,
        oauth1_service: OAuth1ServiceProtocol,
        integration_settings: IntegrationSettings,
        init_session_repo: OAuthInitSessionRepositoryProtocol,
        redirect_session_repo: OAuthRedirectSessionRepositoryProtocol,
        settings: Settings,
    ) -> None:
        """Store dependencies for OAuth initiation/callback/session orchestration."""
        self._oauth2_service = oauth2_service
        self._oauth1_service = oauth1_service
        self._integration_settings = integration_settings
        self._init_session_repo = init_session_repo
        self._redirect_session_repo = redirect_session_repo
        self._settings = settings

    # ------------------------------------------------------------------
    # Initiation
    # ------------------------------------------------------------------

    async def initiate_oauth2(
        self,
        short_name: str,
        state: str,
        *,
        client_id: Optional[str] = None,
        template_configs: Optional[dict] = None,
        ctx: ApiContext,
    ) -> Tuple[str, Optional[str]]:
        """Generate OAuth2 authorization URL with optional PKCE.

        Returns:
            (provider_auth_url, code_verifier) — code_verifier is None when PKCE is not used.
        """
        oauth_settings = await self._integration_settings.get_by_short_name(short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not configured for source: {short_name}",
            )

        api_callback = f"{self._settings.api_url}/source-connections/callback"

        try:
            (
                provider_auth_url,
                code_verifier,
            ) = await self._oauth2_service.generate_auth_url_with_redirect(
                oauth_settings,
                redirect_uri=api_callback,
                client_id=client_id,
                state=state,
                template_configs=template_configs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if code_verifier:
            ctx.logger.debug(f"Generated PKCE challenge for {short_name} (code_verifier stored)")

        return provider_auth_url, code_verifier

    async def initiate_oauth1(
        self,
        short_name: str,
        *,
        consumer_key: str,
        consumer_secret: str,
        ctx: ApiContext,
    ) -> Tuple[str, Dict[str, str]]:
        """Start OAuth1 flow: get request token and build authorization URL.

        Returns:
            (provider_auth_url, oauth1_overrides) where overrides contain
            oauth_token, oauth_token_secret, consumer_key, consumer_secret.
        """
        oauth_settings = await self._integration_settings.get_by_short_name(short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not configured for source: {short_name}",
            )

        if not isinstance(oauth_settings, OAuth1Settings):
            raise HTTPException(
                status_code=400,
                detail=f"Source {short_name} is not configured for OAuth1",
            )

        api_callback = f"{self._settings.api_url}/source-connections/callback"
        effective_consumer_key = consumer_key or oauth_settings.consumer_key
        effective_consumer_secret = consumer_secret or oauth_settings.consumer_secret

        request_token_response = await self._oauth1_service.get_request_token(
            request_token_url=oauth_settings.request_token_url,
            consumer_key=effective_consumer_key,
            consumer_secret=effective_consumer_secret,
            callback_url=api_callback,
            logger=ctx.logger,
        )

        oauth1_overrides: Dict[str, str] = {
            "oauth_token": request_token_response.oauth_token,
            "oauth_token_secret": request_token_response.oauth_token_secret,
            "consumer_key": effective_consumer_key,
            "consumer_secret": effective_consumer_secret,
        }

        provider_auth_url = self._oauth1_service.build_authorization_url(
            authorization_url=oauth_settings.authorization_url,
            oauth_token=request_token_response.oauth_token,
            scope=oauth_settings.scope,
            expiration=oauth_settings.expiration,
        )

        ctx.logger.debug(f"OAuth1 request token obtained for {short_name}")

        return provider_auth_url, oauth1_overrides

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
        client_id = nested_client_id or nested_consumer_key
        client_secret = nested_client_secret or nested_consumer_secret
        if (client_id and not client_secret) or (client_secret and not client_id):
            raise HTTPException(
                status_code=422,
                detail="Custom OAuth requires both client_id and client_secret or neither",
            )

        oauth_client_mode = "byoc_nested" if (client_id and client_secret) else "platform_default"
        additional_overrides: Dict[str, Any] = {}

        if oauth_type == "oauth1":
            provider_auth_url, oauth1_overrides = await self.initiate_oauth1(
                short_name,
                consumer_key=nested_consumer_key or "",
                consumer_secret=nested_consumer_secret or "",
                ctx=ctx,
            )
            additional_overrides.update(oauth1_overrides)
        else:
            provider_auth_url, code_verifier = await self.initiate_oauth2(
                short_name,
                state,
                client_id=nested_client_id or None,
                template_configs=template_configs,
                ctx=ctx,
            )
            if code_verifier:
                additional_overrides["code_verifier"] = code_verifier

        return OAuthBrowserInitiationResult(
            provider_auth_url=provider_auth_url,
            client_id=client_id,
            client_secret=client_secret,
            oauth_client_mode=oauth_client_mode,
            additional_overrides=additional_overrides,
        )

    # ------------------------------------------------------------------
    # Token exchange (callback phase)
    # ------------------------------------------------------------------

    async def complete_oauth2_callback(
        self,
        short_name: str,
        code: str,
        overrides: Dict[str, Any],
        ctx: ApiContext,
    ) -> OAuth2TokenResponse:
        """Exchange OAuth2 authorization code for tokens."""
        redirect_uri = (
            overrides.get("oauth_redirect_uri")
            or f"{self._settings.api_url}/source-connections/callback"
        )

        template_configs = overrides.get("template_configs")
        code_verifier = overrides.get("code_verifier")

        return await self._oauth2_service.exchange_authorization_code_for_token_with_redirect(
            ctx=ctx,
            source_short_name=short_name,
            code=code,
            redirect_uri=redirect_uri,
            client_id=overrides.get("client_id"),
            client_secret=overrides.get("client_secret"),
            template_configs=template_configs,
            code_verifier=code_verifier,
        )

    async def complete_oauth1_callback(
        self,
        short_name: str,
        verifier: str,
        overrides: Dict[str, Any],
        oauth_settings: OAuth1Settings,
        ctx: ApiContext,
    ) -> OAuth1TokenResponse:
        """Exchange OAuth1 verifier for access token."""
        ctx.logger.info(f"Exchanging OAuth1 verifier for access token: {short_name}")

        return await self._oauth1_service.exchange_token(
            access_token_url=oauth_settings.access_token_url,
            consumer_key=oauth_settings.consumer_key,
            consumer_secret=oauth_settings.consumer_secret,
            oauth_token=overrides.get("oauth_token", ""),
            oauth_token_secret=overrides.get("oauth_token_secret", ""),
            oauth_verifier=verifier,
            logger=ctx.logger,
        )

    # ------------------------------------------------------------------
    # Flow state persistence
    # ------------------------------------------------------------------

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
        """Persist an init session for a new OAuth flow.

        Caller pre-extracts BYOC creds; this method never sees SourceConnectionCreate.
        """
        effective_client_mode = oauth_client_mode
        if not effective_client_mode:
            effective_client_mode = "byoc" if (client_id and client_secret) else "platform_default"

        overrides: Dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "oauth_client_mode": effective_client_mode,
            "redirect_url": redirect_url,
            "oauth_redirect_uri": f"{self._settings.api_url}/source-connections/callback",
            "template_configs": template_configs,
        }

        if additional_overrides:
            overrides.update(additional_overrides)

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return await self._init_session_repo.create(
            db,
            obj_in={
                "organization_id": ctx.organization.id,
                "short_name": short_name,
                "payload": payload,
                "overrides": overrides,
                "state": state,
                "status": ConnectionInitStatus.PENDING,
                "expires_at": expires_at,
                "redirect_session_id": redirect_session_id,
            },
            ctx=ctx,
            uow=uow,
        )

    async def create_proxy_url(
        self,
        db: AsyncSession,
        provider_auth_url: str,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Tuple[str, datetime, UUID]:
        """Create proxy redirect URL for OAuth flow.

        Returns:
            (proxy_url, proxy_expires, redirect_session_id)
        """
        proxy_ttl = 1440  # 24 hours
        proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
        code8 = await self._redirect_session_repo.generate_unique_code(db, length=8)

        redirect_sess = await self._redirect_session_repo.create(
            db,
            code=code8,
            final_url=provider_auth_url,
            expires_at=proxy_expires,
            ctx=ctx,
            uow=uow,
        )

        proxy_url = f"{self._settings.api_url}/source-connections/authorize/{code8}"
        return proxy_url, proxy_expires, redirect_sess.id
