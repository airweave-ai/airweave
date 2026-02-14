"""OAuth flow service -- cross-cutting OAuth initiation and completion.

Handles the protocol-level OAuth handshake: init sessions, proxy URLs,
auth URL generation, and token exchange. Does NOT handle domain-specific
connection/credential/sync creation -- that's the caller's responsibility.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from airweave.core.config import settings as core_settings
from airweave.core.protocols.oauth import OAuthFlowServiceProtocol
from airweave.crud import connection_init_session, redirect_session
from airweave.domains.oauth.exceptions import (
    OAuthNotConfiguredError,
    OAuthSessionAlreadyCompletedError,
    OAuthSessionNotFoundError,
    OAuthTokenExchangeError,
)
from airweave.domains.oauth.types import OAuthCompletionResult, OAuthInitResult
from airweave.models.connection_init_session import ConnectionInitStatus


class OAuthFlowService(OAuthFlowServiceProtocol):
    """OAuth flow management for browser-based OAuth1/OAuth2 flows."""

    def __init__(
        self,
        oauth2_service: Any,
        oauth1_service: Any,
        integration_settings: Any,
    ) -> None:
        """Initialize with OAuth service dependencies."""
        self._oauth2_service = oauth2_service
        self._oauth1_service = oauth1_service
        self._integration_settings = integration_settings

    async def initiate_oauth2(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_client_id: Optional[str],
        byoc_client_secret: Optional[str],
        template_configs: Optional[dict],
        db: Any,
        uow: Any,
        ctx: Any = None,
    ) -> OAuthInitResult:
        """Start OAuth2 browser flow."""
        oauth_settings = await self._integration_settings.get_by_short_name(short_name)
        if not oauth_settings:
            raise OAuthNotConfiguredError(short_name)

        state = secrets.token_urlsafe(24)
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        (
            provider_auth_url,
            code_verifier,
        ) = await self._oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=byoc_client_id,
            state=state,
            template_configs=template_configs,
        )

        # Build overrides
        overrides = self._build_overrides(
            byoc_client_id, byoc_client_secret, redirect_url, template_configs
        )
        if code_verifier:
            overrides["code_verifier"] = code_verifier

        proxy_url, proxy_expiry, redirect_session_id = await self._create_proxy_url(
            db, provider_auth_url, uow, ctx=ctx
        )

        init_session = await self._create_init_session(
            db=db,
            short_name=short_name,
            payload=payload,
            state=state,
            organization_id=organization_id,
            overrides=overrides,
            redirect_session_id=redirect_session_id,
            uow=uow,
            ctx=ctx,
        )

        return OAuthInitResult(
            auth_url=provider_auth_url,
            proxy_url=proxy_url,
            proxy_expiry=proxy_expiry,
            init_session_id=init_session.id,
            redirect_session_id=redirect_session_id,
        )

    async def initiate_oauth1(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_consumer_key: Optional[str],
        byoc_consumer_secret: Optional[str],
        db: Any,
        uow: Any,
        ctx: Any = None,
    ) -> OAuthInitResult:
        """Start OAuth1 browser flow."""
        from airweave.platform.auth.schemas import OAuth1Settings

        oauth_settings = await self._integration_settings.get_by_short_name(short_name)
        if not oauth_settings or not isinstance(oauth_settings, OAuth1Settings):
            raise OAuthNotConfiguredError(short_name)

        consumer_key = byoc_consumer_key or oauth_settings.consumer_key
        consumer_secret = byoc_consumer_secret or oauth_settings.consumer_secret
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        from airweave.core.logging import logger as app_logger

        request_token_response = await self._oauth1_service.get_request_token(
            request_token_url=oauth_settings.request_token_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            callback_url=api_callback,
            logger=app_logger,
        )

        provider_auth_url = (
            f"{oauth_settings.authorization_url}?oauth_token={request_token_response.oauth_token}"
        )

        overrides = self._build_overrides(
            byoc_consumer_key, byoc_consumer_secret, redirect_url, None
        )
        overrides["oauth_token"] = request_token_response.oauth_token
        overrides["oauth_token_secret"] = request_token_response.oauth_token_secret
        if byoc_consumer_key:
            overrides["consumer_key"] = byoc_consumer_key
        if byoc_consumer_secret:
            overrides["consumer_secret"] = byoc_consumer_secret

        proxy_url, proxy_expiry, redirect_session_id = await self._create_proxy_url(
            db, provider_auth_url, uow, ctx=ctx
        )

        init_session = await self._create_init_session(
            db=db,
            short_name=short_name,
            payload=payload,
            state=request_token_response.oauth_token,
            organization_id=organization_id,
            overrides=overrides,
            redirect_session_id=redirect_session_id,
            uow=uow,
            ctx=ctx,
        )

        return OAuthInitResult(
            auth_url=provider_auth_url,
            proxy_url=proxy_url,
            proxy_expiry=proxy_expiry,
            init_session_id=init_session.id,
            redirect_session_id=redirect_session_id,
        )

    async def complete_oauth2_callback(
        self,
        state: str,
        code: str,
        db: Any,
    ) -> OAuthCompletionResult:
        """Complete OAuth2 flow: look up session, exchange code, return tokens."""
        init_session = await connection_init_session.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise OAuthSessionNotFoundError()

        if init_session.status != ConnectionInitStatus.PENDING:
            raise OAuthSessionAlreadyCompletedError(str(init_session.status))

        overrides = init_session.overrides or {}
        redirect_uri = (
            overrides.get("oauth_redirect_uri")
            or f"{core_settings.api_url}/source-connections/callback"
        )

        try:
            token_response = (
                await self._oauth2_service.exchange_authorization_code_for_token_with_redirect(
                    ctx=None,
                    source_short_name=init_session.short_name,
                    code=code,
                    redirect_uri=redirect_uri,
                    client_id=overrides.get("client_id"),
                    client_secret=overrides.get("client_secret"),
                    template_configs=overrides.get("template_configs"),
                    code_verifier=overrides.get("code_verifier"),
                )
            )
        except Exception as e:
            raise OAuthTokenExchangeError(f"OAuth2 token exchange failed: {e}") from e

        return OAuthCompletionResult(
            token_response=token_response,
            init_session=init_session,
            original_payload=init_session.payload or {},
            overrides=overrides,
            short_name=init_session.short_name,
            organization_id=init_session.organization_id,
        )

    async def complete_oauth1_callback(
        self,
        oauth_token: str,
        oauth_verifier: str,
        db: Any,
    ) -> OAuthCompletionResult:
        """Complete OAuth1 flow: look up session, exchange verifier, return tokens."""
        from airweave.platform.auth.schemas import OAuth1Settings

        init_session = await connection_init_session.get_by_oauth_token_no_auth(
            db, oauth_token=oauth_token
        )
        if not init_session:
            raise OAuthSessionNotFoundError(
                "OAuth1 session not found or expired. Request token may have been used already."
            )

        if init_session.status != ConnectionInitStatus.PENDING:
            raise OAuthSessionAlreadyCompletedError(str(init_session.status))

        overrides = init_session.overrides or {}

        oauth_settings = await self._integration_settings.get_by_short_name(init_session.short_name)
        if not isinstance(oauth_settings, OAuth1Settings):
            raise OAuthNotConfiguredError(init_session.short_name)

        try:
            token_response = await self._oauth1_service.exchange_token(
                access_token_url=oauth_settings.access_token_url,
                consumer_key=oauth_settings.consumer_key,
                consumer_secret=oauth_settings.consumer_secret,
                oauth_token=overrides.get("oauth_token", ""),
                oauth_token_secret=overrides.get("oauth_token_secret", ""),
                oauth_verifier=oauth_verifier,
                logger=None,
            )
        except Exception as e:
            raise OAuthTokenExchangeError(f"OAuth1 token exchange failed: {e}") from e

        return OAuthCompletionResult(
            token_response=token_response,
            init_session=init_session,
            original_payload=init_session.payload or {},
            overrides=overrides,
            short_name=init_session.short_name,
            organization_id=init_session.organization_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_overrides(
        client_id: Optional[str],
        client_secret: Optional[str],
        redirect_url: Optional[str],
        template_configs: Optional[dict],
    ) -> Dict[str, Any]:
        """Build the overrides dict for the init session."""
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "oauth_client_mode": "byoc" if client_id else "platform_default",
            "redirect_url": redirect_url,
            "oauth_redirect_uri": f"{core_settings.api_url}/source-connections/callback",
            "template_configs": template_configs,
        }

    @staticmethod
    async def _create_proxy_url(db: Any, provider_auth_url: str, uow: Any, ctx: Any = None):
        """Create proxy URL for the OAuth auth URL."""
        proxy_ttl = 1440  # 24 hours
        proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
        code8 = await redirect_session.generate_unique_code(db, length=8)

        redirect_sess = await redirect_session.create(
            db,
            code=code8,
            final_url=provider_auth_url,
            expires_at=proxy_expires,
            ctx=ctx,
            uow=uow,
        )

        proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code8}"
        return proxy_url, proxy_expires, redirect_sess.id

    @staticmethod
    async def _create_init_session(
        db: Any,
        short_name: str,
        payload: dict,
        state: str,
        organization_id: Any,
        overrides: dict,
        redirect_session_id: UUID,
        uow: Any,
        ctx: Any = None,
    ) -> Any:
        """Create a ConnectionInitSession record."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return await connection_init_session.create(
            db,
            obj_in={
                "organization_id": organization_id,
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
