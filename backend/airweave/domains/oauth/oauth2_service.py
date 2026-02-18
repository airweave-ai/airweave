"""OAuth2 service for handling authentication and token exchange for integrations."""

import asyncio
import base64
import hashlib
import random
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config.settings import Settings
from airweave.core.exceptions import NotFoundException, TokenRefreshError
from airweave.core.logging import ContextualLogger
from airweave.core.protocols.encryption import CredentialEncryptor
from airweave.core.shared_models import ConnectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.oauth.protocols import (
    OAuth2ServiceProtocol,
    OAuthConnectionRepositoryProtocol,
    OAuthCredentialRepositoryProtocol,
    OAuthSourceRepositoryProtocol,
)
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import (
    BaseAuthSettings,
    OAuth2Settings,
    OAuth2TokenResponse,
)
from airweave.platform.auth.settings import integration_settings


class OAuth2Service(OAuth2ServiceProtocol):
    """Service for handling OAuth2 authentication and token exchange."""

    def __init__(
        self,
        settings: Settings,
        conn_repo: OAuthConnectionRepositoryProtocol,
        cred_repo: OAuthCredentialRepositoryProtocol,
        encryptor: CredentialEncryptor,
        source_repo: OAuthSourceRepositoryProtocol,
    ):
        """Initialize with injected dependencies."""
        self.settings = settings
        self.conn_repo = conn_repo
        self.cred_repo = cred_repo
        self.encryptor = encryptor
        self.source_repo = source_repo

    async def generate_auth_url(
        self,
        oauth2_settings: OAuth2Settings,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> str:
        """Generate the OAuth2 authorization URL for an integration.

        Args:
            oauth2_settings: The OAuth2 settings for the integration
            client_id: Optional client ID to override the default one
            state: Optional state token to round-trip through the OAuth flow
            template_configs: Optional config fields for URL templates (e.g., instance_url)

        Returns:
            The authorization URL for the OAuth2 flow

        Raises:
            HTTPException: If there's an error generating the authorization URL
            ValueError: If template URL requires template_configs but it's missing
        """
        redirect_uri = self._get_redirect_url(oauth2_settings.integration_short_name)

        if not client_id:
            client_id = oauth2_settings.client_id

        if oauth2_settings.url_template:
            if not template_configs:
                raise ValueError(
                    f"template_configs needed for templated OAuth URLs "
                    f"({oauth2_settings.integration_short_name})"
                )
            try:
                auth_url_base = oauth2_settings.render_url(**template_configs)
            except KeyError as e:
                raise ValueError(
                    f"Missing template variable {e} for {oauth2_settings.integration_short_name}. "
                    f"Available in template_configs: {list(template_configs.keys())}"
                ) from e
        else:
            auth_url_base = oauth2_settings.url

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            **(oauth2_settings.additional_frontend_params or {}),
        }

        if oauth2_settings.scope:
            params["scope"] = oauth2_settings.scope

        if oauth2_settings.user_scope:
            params["user_scope"] = oauth2_settings.user_scope

        if state is not None:
            params["state"] = state

        auth_url = f"{auth_url_base}?{urlencode(params)}"

        return auth_url

    async def exchange_authorization_code_for_token(
        self,
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an authorization code for an OAuth2 token.

        Args:
            ctx: The API context.
            source_short_name: The short name of the integration source.
            code: The authorization code to exchange.
            client_id: Optional client ID to override the default.
            client_secret: Optional client secret to override the default.
            template_configs: Optional config fields for URL templates.

        Returns:
            OAuth2TokenResponse: The response containing the access token and other details.

        Raises:
            HTTPException: If settings are not found for the source or token exchange fails.
        """
        oauth2_settings = await self._get_oauth2_settings(source_short_name)

        redirect_uri = self._get_redirect_url(source_short_name)

        backend_url = self._resolve_backend_url(
            oauth2_settings, source_short_name, template_configs
        )

        if not client_id and not client_secret:
            client_id = oauth2_settings.client_id
            client_secret = oauth2_settings.client_secret

        return await self._exchange_code(
            logger=ctx.logger,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            backend_url=backend_url,
            integration_config=oauth2_settings,
        )

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

        For providers that require PKCE (e.g., Airtable), this method generates
        a code_verifier and includes the corresponding code_challenge in the
        authorization URL. The code_verifier must be stored and sent during
        token exchange.

        Args:
            oauth2_settings: The OAuth2 settings for the integration
            redirect_uri: The redirect URI for the OAuth callback
            client_id: Optional client ID to override the default
            state: Optional state token for CSRF protection
            template_configs: Optional config fields for URL templates (e.g., instance_url)

        Returns:
            Tuple[str, Optional[str]]: (authorization_url, code_verifier)
                - authorization_url: The complete URL to redirect the user to
                - code_verifier: The PKCE code verifier if PKCE is required, None otherwise

        Raises:
            ValueError: If template URL requires template_configs but it's missing
        """
        if not client_id:
            client_id = oauth2_settings.client_id

        if oauth2_settings.url_template:
            if not template_configs:
                raise ValueError(
                    f"template_configs needed for templated OAuth URLs "
                    f"({oauth2_settings.integration_short_name})"
                )
            try:
                auth_url_base = oauth2_settings.render_url(**template_configs)
            except KeyError as e:
                raise ValueError(
                    f"Missing template variable {e} for {oauth2_settings.integration_short_name}"
                ) from e
        else:
            auth_url_base = oauth2_settings.url

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            **(oauth2_settings.additional_frontend_params or {}),
        }
        if state:
            params["state"] = state
        if oauth2_settings.scope:
            params["scope"] = oauth2_settings.scope
        if oauth2_settings.user_scope:
            params["user_scope"] = oauth2_settings.user_scope

        code_verifier = None
        if oauth2_settings.requires_pkce:
            code_verifier, code_challenge = self._generate_pkce_challenge_pair()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        auth_url = f"{auth_url_base}?{urlencode(params)}"
        return auth_url, code_verifier

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
        """Exchange an OAuth2 code using an explicit redirect_uri.

        Args:
            ctx: The API context
            source_short_name: The short name of the integration
            code: The authorization code from the OAuth provider
            redirect_uri: Must match the one used in authorization request
            client_id: Optional client ID override
            client_secret: Optional client secret override
            template_configs: Optional config fields for URL templates
            code_verifier: PKCE code verifier (required if provider uses PKCE)

        Returns:
            OAuth2TokenResponse: The response containing the access token and other details

        Raises:
            HTTPException: If settings not found or token exchange fails
            ValueError: If template URL requires template_configs but it's missing
        """
        oauth2_settings = await self._get_oauth2_settings(source_short_name)

        backend_url = self._resolve_backend_url(
            oauth2_settings, source_short_name, template_configs
        )

        if not client_id:
            client_id = oauth2_settings.client_id
        if not client_secret:
            client_secret = oauth2_settings.client_secret

        return await self._exchange_code(
            logger=ctx.logger,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            backend_url=backend_url,
            integration_config=oauth2_settings,
            code_verifier=code_verifier,
        )

    async def refresh_access_token(
        self,
        db: AsyncSession,
        integration_short_name: str,
        ctx: ApiContext,
        connection_id: UUID,
        decrypted_credential: dict,
        config_fields: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Refresh an access token using a refresh token.

        Rotates the refresh token if the integration is configured to do so.

        Args:
            db: The database session.
            integration_short_name: The short name of the integration.
            ctx: The API context.
            connection_id: The ID of the connection to refresh the token for.
            decrypted_credential: The token and optional config fields.
            config_fields: Config fields for template rendering.

        Returns:
            OAuth2TokenResponse: The response containing the new access token and other details.

        Raises:
            TokenRefreshError: If token refresh fails.
            NotFoundException: If the integration is not found.
        """
        try:
            refresh_token = await self._get_refresh_token(ctx.logger, decrypted_credential)

            integration_config = await self._get_integration_config(
                ctx.logger, integration_short_name
            )

            backend_url = integration_config.backend_url
            if integration_config.backend_url_template:
                if not config_fields:
                    raise ValueError(
                        f"config_fields required for token refresh of {integration_short_name}"
                    )

                try:
                    source = await self.source_repo.get_by_short_name(db, integration_short_name)
                    if source and source.config_class:
                        from airweave.platform.locator import resource_locator

                        config_class = resource_locator.get_config(source.config_class)
                        template_config_values = config_class.extract_template_configs(
                            config_fields
                        )
                    else:
                        template_config_values = config_fields
                except Exception:
                    template_config_values = config_fields

                try:
                    backend_url = integration_config.backend_url.format(**template_config_values)
                    ctx.logger.debug(f"Rendered backend URL for token refresh: {backend_url}")
                except KeyError as e:
                    raise ValueError(
                        f"Missing template variable {e} in config_fields for token refresh"
                    ) from e

            client_id, client_secret = await self._get_client_credentials(
                integration_config, None, decrypted_credential
            )

            headers, payload = self._prepare_token_request(
                ctx.logger, integration_config, refresh_token, client_id, client_secret
            )

            response = await self._make_token_request(ctx.logger, backend_url, headers, payload)

            oauth2_token_response = await self._handle_token_response(
                db, response, integration_config, ctx, connection_id
            )

            return oauth2_token_response

        except Exception as e:
            ctx.logger.error(
                f"Token refresh failed for organization {ctx.organization.id} and "
                f"integration {integration_short_name}: {str(e)}"
            )
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_oauth2_settings(self, source_short_name: str) -> OAuth2Settings:
        """Look up integration settings and narrow to OAuth2Settings.

        Raises:
            HTTPException 404: if settings not found or not an OAuth2 integration.
        """
        try:
            settings = await integration_settings.get_by_short_name(source_short_name)
        except KeyError as e:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source_short_name}"
            ) from e

        if not isinstance(settings, OAuth2Settings):
            raise HTTPException(
                status_code=404,
                detail=f"{source_short_name} is not an OAuth2 integration",
            )
        return settings

    def _resolve_backend_url(
        self,
        oauth2_settings: OAuth2Settings,
        source_short_name: str,
        template_configs: Optional[dict],
    ) -> str:
        """Resolve the backend token URL, rendering templates if needed."""
        if oauth2_settings.backend_url_template:
            if not template_configs:
                raise ValueError(f"template_configs needed for {source_short_name}")
            try:
                return oauth2_settings.render_backend_url(**template_configs)
            except KeyError as e:
                raise ValueError(
                    f"Missing template variable {e} in template_configs for token exchange"
                ) from e
        return oauth2_settings.backend_url

    async def _get_refresh_token(self, logger: ContextualLogger, decrypted_credential: dict) -> str:
        """Get refresh token from decrypted credentials.

        Raises:
            TokenRefreshError: If no refresh token is found.
        """
        refresh_token = decrypted_credential.get("refresh_token", None)
        if not refresh_token:
            error_message = "No refresh token found"
            logger.error(error_message)
            raise TokenRefreshError(error_message)
        return refresh_token

    async def _get_integration_config(
        self,
        logger: ContextualLogger,
        integration_short_name: str,
    ) -> OAuth2Settings:
        """Get and validate OAuth2 integration configuration.

        Raises:
            NotFoundException: If integration configuration is not found.
            NotFoundException: If integration is not an OAuth2 integration.
        """
        try:
            config = await integration_settings.get_by_short_name(integration_short_name)
        except KeyError:
            error_message = f"Configuration for {integration_short_name} not found"
            logger.error(error_message)
            raise NotFoundException(error_message)

        if not isinstance(config, OAuth2Settings):
            error_message = f"{integration_short_name} is not an OAuth2 integration"
            logger.error(error_message)
            raise NotFoundException(error_message)

        return config

    async def _get_client_credentials(
        self,
        integration_config: OAuth2Settings,
        auth_fields: Optional[dict] = None,
        decrypted_credential: Optional[dict] = None,
    ) -> tuple[str, str]:
        """Get client credentials based on priority ordering.

        Priority order:
        1. From decrypted_credential (if available)
        2. From auth_fields (if available)
        3. From integration_config (as fallback)
        """
        client_id = integration_config.client_id
        client_secret = integration_config.client_secret

        if decrypted_credential:
            client_id = decrypted_credential.get("client_id", client_id)
            client_secret = decrypted_credential.get("client_secret", client_secret)

        if auth_fields:
            client_id = auth_fields.get("client_id", client_id)
            client_secret = auth_fields.get("client_secret", client_secret)

        return client_id, client_secret

    def _prepare_token_request(
        self,
        logger: ContextualLogger,
        integration_config: OAuth2Settings,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> tuple[dict, dict]:
        """Prepare headers and payload for token refresh request."""
        headers = {
            "Content-Type": integration_config.content_type,
        }

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        # IMPORTANT: For WITH_ROTATING_REFRESH OAuth (Jira, Confluence, Microsoft),
        # do NOT include scope parameter - Atlassian/Microsoft reject it with 403
        # For WITH_REFRESH OAuth (Google, Slack), scope should be included
        # EXCEPTION: Salesforce is with_refresh but does NOT support scope parameter during refresh
        # See: https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/#refresh-a-token
        oauth_type = integration_config.oauth_type
        short_name = integration_config.integration_short_name

        if oauth_type == "with_rotating_refresh" or short_name == "salesforce":
            logger.debug(
                f"Skipping scope in token refresh "
                f"(oauth_type={oauth_type}, integration={short_name})"
            )
        elif oauth_type == "with_refresh" and integration_config.scope:
            payload["scope"] = integration_config.scope
            logger.debug(
                f"Including scope in token refresh (oauth_type=with_refresh): "
                f"{integration_config.scope}"
            )

        if integration_config.client_credential_location == "header":
            encoded_credentials = self._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        logger.info(
            f"OAuth2 code exchange request - "
            f"URL: {integration_config.backend_url}, "
            f"Redirect URI: {integration_config.backend_url}, "
            f"Client ID: {client_id}, "
            f"Code length: {len(refresh_token)}, "
            f"Grant type: {payload['grant_type']}, "
            f"Credential location: {integration_config.client_credential_location}"
        )

        return headers, payload

    def _is_oauth_rate_limit_error(self, response: httpx.Response) -> bool:
        """Check if response is an OAuth rate limit error.

        Some providers (like Zoho) return 400 instead of 429 for rate limits:
        {"error_description": "You have made too many requests...", "error": "Access Denied"}
        """
        if response.status_code == 429:
            return True
        if response.status_code == 400:
            try:
                data = response.json()
                error_desc = data.get("error_description", "").lower()
                error_type = data.get("error", "").lower()
                if "too many requests" in error_desc and error_type == "access denied":
                    return True
            except Exception:
                pass
        return False

    async def _make_token_request(
        self, logger: ContextualLogger, url: str, headers: dict, payload: dict
    ) -> httpx.Response:
        """Make the token refresh request with retry on rate limit."""
        logger.info(f"Making token request to: {url}")

        max_retries = 5
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    logger.info(f"Sending request to {url}")
                    response = await client.post(url, headers=headers, data=payload)

                    logger.info(f"Received response: Status {response.status_code}, ")

                    if self._is_oauth_rate_limit_error(response):
                        delay = base_delay * (2**attempt) + random.uniform(0, 2)
                        logger.warning(
                            f"OAuth rate limit hit, waiting {delay:.1f}s before retry "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    return response

            except httpx.HTTPStatusError as e:
                if self._is_oauth_rate_limit_error(e.response):
                    delay = base_delay * (2**attempt) + random.uniform(0, 2)
                    logger.warning(
                        f"OAuth rate limit hit (exception), waiting {delay:.1f}s before retry "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    f"HTTP error during token request: {e.response.status_code} "
                    f"{e.response.reason_phrase}"
                )

                try:
                    error_content = e.response.json()
                    logger.error(f"Error response body: {error_content}")
                except Exception:
                    logger.error(f"Error response text: {e.response.text}")

                raise
            except Exception as e:
                logger.error(f"Unexpected error during token request: {str(e)}")
                raise

        raise httpx.HTTPStatusError(
            f"OAuth token request failed after {max_retries} retries (rate limited)",
            request=httpx.Request("POST", url),
            response=httpx.Response(429),
        )

    async def _handle_token_response(
        self,
        db: AsyncSession,
        response: httpx.Response,
        integration_config: OAuth2Settings,
        ctx: ApiContext,
        connection_id: UUID,
    ) -> OAuth2TokenResponse:
        """Handle the token response and update refresh token if needed."""
        oauth2_token_response = OAuth2TokenResponse(**response.json())

        if integration_config.oauth_type == "with_rotating_refresh":
            connection = await self.conn_repo.get(db=db, id=connection_id, ctx=ctx)
            integration_credential = await self.cred_repo.get(
                db=db, id=connection.integration_credential_id, ctx=ctx
            )

            current_credentials = self.encryptor.decrypt(
                integration_credential.encrypted_credentials
            )
            current_credentials["refresh_token"] = oauth2_token_response.refresh_token

            encrypted_credentials = self.encryptor.encrypt(current_credentials)
            await self.cred_repo.update(
                db=db,
                db_obj=integration_credential,
                obj_in={"encrypted_credentials": encrypted_credentials},
                ctx=ctx,
            )

        return oauth2_token_response

    def _encode_client_credentials(self, client_id: str, client_secret: str) -> str:
        """Encodes the client ID and client secret in Base64."""
        creds = f"{client_id}:{client_secret}"
        creds_bytes = creds.encode("ascii")
        base64_bytes = base64.b64encode(creds_bytes)
        base64_credentials = base64_bytes.decode("ascii")
        return base64_credentials

    def _generate_pkce_challenge_pair(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and code challenge.

        Returns:
            Tuple[str, str]: (code_verifier, code_challenge)
                - code_verifier: Random string to be sent during token exchange
                - code_challenge: SHA256 hash to be sent during authorization

        References:
            RFC 7636: https://tools.ietf.org/html/rfc7636
        """
        code_verifier = secrets.token_urlsafe(64)

        verifier_bytes = code_verifier.encode("ascii")
        sha256_hash = hashlib.sha256(verifier_bytes).digest()

        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode("ascii").rstrip("=")

        return code_verifier, code_challenge

    def _normalize_token_response(
        self, response_data: dict, integration_short_name: str, logger: ContextualLogger
    ) -> dict:
        """Normalize non-standard OAuth2 token responses to standard format.

        Some OAuth providers return tokens in non-standard nested structures.
        This method detects and normalizes them to the standard OAuth2 format.
        """
        if "authed_user" in response_data and isinstance(response_data.get("authed_user"), dict):
            authed_user = response_data["authed_user"]
            if "access_token" in authed_user and "access_token" not in response_data:
                logger.debug(
                    f"Normalized nested authed_user token format for {integration_short_name}"
                )
                return {
                    "access_token": authed_user.get("access_token"),
                    "token_type": authed_user.get("token_type", "Bearer"),
                    "scope": authed_user.get("scope", response_data.get("scope")),
                    "refresh_token": authed_user.get("refresh_token"),
                }

        return response_data

    def _get_redirect_url(self, integration_short_name: str) -> str:
        """Generate the appropriate redirect URI based on environment."""
        return f"{self.settings.app_url}/auth/callback"

    async def _exchange_code(
        self,
        *,
        logger: ContextualLogger,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        backend_url: str,
        integration_config: OAuth2Settings,
        code_verifier: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        """Core method to exchange an authorization code for tokens.

        Supports both standard OAuth 2.0 and PKCE (Proof Key for Code Exchange).
        """
        headers = {
            "Content-Type": integration_config.content_type,
        }

        payload = {
            "grant_type": integration_config.grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        if code_verifier:
            payload["code_verifier"] = code_verifier
            logger.debug("Including PKCE code_verifier in token exchange request")

        if integration_config.client_credential_location == "header":
            encoded_credentials = self._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        logger.info(
            f"OAuth2 code exchange request - "
            f"URL: {backend_url}, "
            f"Redirect URI: {redirect_uri}, "
            f"Client ID: {client_id}, "
            f"Code length: {len(code)}, "
            f"Grant type: {integration_config.grant_type}, "
            f"Credential location: {integration_config.client_credential_location}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(backend_url, headers=headers, data=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"OAuth2 token exchange failed - Status: {e.response.status_code}, "
                f"Response text: {e.response.text}"
            )
            raise HTTPException(status_code=400, detail=e.response.text) from e
        except Exception as e:
            logger.error(f"Failed to exchange authorization code: {str(e)}")
            raise HTTPException(
                status_code=400, detail="Failed to exchange authorization code"
            ) from e

        response_data = response.json()

        normalized_data = self._normalize_token_response(
            response_data, integration_config.integration_short_name, logger
        )

        return OAuth2TokenResponse(**normalized_data)

    def _supports_oauth2(self, oauth_type: Optional[str]) -> bool:
        """Check if the integration supports OAuth2 based on oauth_type."""
        return oauth_type is not None

    async def _create_connection(
        self,
        db: AsyncSession,
        source: schemas.Source,
        auth_settings: BaseAuthSettings,
        oauth2_response: OAuth2TokenResponse,
        ctx: ApiContext,
    ) -> schemas.Connection:
        """Create a new connection with OAuth2 credentials."""
        decrypted_credentials = (
            {"access_token": oauth2_response.access_token}
            if auth_settings.oauth_type == "access_only"
            else {
                "refresh_token": oauth2_response.refresh_token,
                "access_token": oauth2_response.access_token,
            }
        )

        encrypted_credentials = self.encryptor.encrypt(decrypted_credentials)

        async with UnitOfWork(db) as uow:
            integration_credential_in = schemas.IntegrationCredentialCreate(
                name=f"{source.name} - {ctx.organization.id}",
                description=(f"OAuth2 credentials for {source.name} - {ctx.organization.id}"),
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                encrypted_credentials=encrypted_credentials,
            )

            integration_credential = await self.cred_repo.create(
                uow.session, obj_in=integration_credential_in, ctx=ctx, uow=uow
            )

            await uow.session.flush()

            connection_in = schemas.ConnectionCreate(
                name=f"Connection to {source.name}",
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_credential.id,
                short_name=source.short_name,
            )

            connection = await self.conn_repo.create(
                uow.session, obj_in=connection_in, ctx=ctx, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)

        return connection
