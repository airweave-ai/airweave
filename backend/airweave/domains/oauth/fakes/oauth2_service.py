"""Fake OAuth2 service for testing."""

from typing import Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.platform.auth.schemas import OAuth2Settings, OAuth2TokenResponse


class FakeOAuth2Service:
    """In-memory fake for OAuth2ServiceProtocol.

    Covers all public methods of OAuth2Service. Seed responses per-integration
    and inspect recorded calls for assertions.
    """

    def __init__(self) -> None:
        self._refresh_responses: dict[str, OAuth2TokenResponse] = {}
        self._exchange_responses: dict[str, OAuth2TokenResponse] = {}
        self._auth_urls: dict[str, str] = {}
        self._auth_url_with_redirect_responses: dict[str, Tuple[str, Optional[str]]] = {}
        self._calls: list[tuple[Any, ...]] = []
        self._should_raise: Optional[Exception] = None

    # -- seeding helpers --

    def seed_refresh(self, integration_short_name: str, access_token: str, **extra: str) -> None:
        self._refresh_responses[integration_short_name] = OAuth2TokenResponse(
            access_token=access_token, **extra
        )

    def seed_exchange(self, source_short_name: str, access_token: str, **extra: str) -> None:
        self._exchange_responses[source_short_name] = OAuth2TokenResponse(
            access_token=access_token, **extra
        )

    def seed_auth_url(self, integration_short_name: str, url: str) -> None:
        self._auth_urls[integration_short_name] = url

    def seed_auth_url_with_redirect(
        self,
        integration_short_name: str,
        url: str,
        code_verifier: Optional[str] = None,
    ) -> None:
        self._auth_url_with_redirect_responses[integration_short_name] = (url, code_verifier)

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    def clear_error(self) -> None:
        self._should_raise = None

    @property
    def calls(self) -> list[tuple[Any, ...]]:
        return list(self._calls)

    def calls_for(self, method: str) -> list[tuple[Any, ...]]:
        return [c for c in self._calls if c[0] == method]

    # -- public methods matching OAuth2ServiceProtocol + extras --

    async def generate_auth_url(
        self,
        oauth2_settings: OAuth2Settings,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict[str, str]] = None,
    ) -> str:
        self._calls.append(("generate_auth_url", oauth2_settings, client_id, state))
        if self._should_raise:
            raise self._should_raise
        url = self._auth_urls.get(oauth2_settings.integration_short_name)
        if url is None:
            raise ValueError(f"No seeded auth_url for {oauth2_settings.integration_short_name}")
        return url

    async def exchange_authorization_code_for_token(
        self,
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict[str, str]] = None,
    ) -> OAuth2TokenResponse:
        self._calls.append(
            (
                "exchange_authorization_code_for_token",
                ctx,
                source_short_name,
                code,
                client_id,
                client_secret,
                template_configs,
            )
        )
        if self._should_raise:
            raise self._should_raise
        resp = self._exchange_responses.get(source_short_name)
        if not resp:
            raise ValueError(f"No seeded exchange response for {source_short_name}")
        return resp

    async def generate_auth_url_with_redirect(
        self,
        oauth2_settings: OAuth2Settings,
        *,
        redirect_uri: str,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict[str, str]] = None,
    ) -> Tuple[str, Optional[str]]:
        self._calls.append(
            (
                "generate_auth_url_with_redirect",
                oauth2_settings,
                redirect_uri,
                client_id,
                state,
            )
        )
        if self._should_raise:
            raise self._should_raise
        result = self._auth_url_with_redirect_responses.get(oauth2_settings.integration_short_name)
        if result is None:
            raise ValueError(
                f"No seeded auth_url_with_redirect for {oauth2_settings.integration_short_name}"
            )
        return result

    async def exchange_authorization_code_for_token_with_redirect(
        self,
        ctx: ApiContext,
        *,
        source_short_name: str,
        code: str,
        redirect_uri: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict[str, str]] = None,
        code_verifier: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        self._calls.append(
            (
                "exchange_authorization_code_for_token_with_redirect",
                ctx,
                source_short_name,
                code,
                redirect_uri,
                client_id,
                client_secret,
                template_configs,
                code_verifier,
            )
        )
        if self._should_raise:
            raise self._should_raise
        resp = self._exchange_responses.get(source_short_name)
        if not resp:
            raise ValueError(f"No seeded exchange response for {source_short_name}")
        return resp

    async def refresh_access_token(
        self,
        db: AsyncSession,
        integration_short_name: str,
        ctx: ApiContext,
        connection_id: UUID,
        decrypted_credential: dict[str, Any],
        config_fields: Optional[dict[str, str]] = None,
    ) -> OAuth2TokenResponse:
        self._calls.append(
            (
                "refresh_access_token",
                db,
                integration_short_name,
                ctx,
                connection_id,
                decrypted_credential,
                config_fields,
            )
        )
        if self._should_raise:
            raise self._should_raise
        resp = self._refresh_responses.get(integration_short_name)
        if not resp:
            raise ValueError(f"No seeded refresh response for {integration_short_name}")
        return resp
