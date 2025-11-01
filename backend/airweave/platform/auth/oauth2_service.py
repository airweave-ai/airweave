"""The services for handling OAuth2 authentication and token exchange for integrations."""

import base64
import hashlib
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException, TokenRefreshError
from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import ConnectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import (
    BaseAuthSettings,
    OAuth2Settings,
    OAuth2TokenResponse,
)
from airweave.platform.auth.settings import integration_settings

# Note: oauth1_service imported at bottom to avoid circular dependency


class OAuth2Service:
    """Service class for handling OAuth2 authentication and token exchange."""

    @staticmethod
    async def generate_auth_url(
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
        redirect_uri = OAuth2Service._get_redirect_url(oauth2_settings.integration_short_name)

        # if client_id is not provided, get it from the integration settings
        if not client_id:
            client_id = oauth2_settings.client_id

        # Render URL if it's a template
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

    @staticmethod
    async def exchange_authorization_code_for_token(
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an authorization code for an OAuth2 token.

        Args:
        ----
            ctx (ApiContext): The API context.
            source_short_name (str): The short name of the integration source.
            code (str): The authorization code to exchange.
            client_id (Optional[str]): Optional client ID to override the default.
            client_secret (Optional[str]): Optional client secret to override the default.
            template_configs (Optional[dict]): Optional config fields for URL templates.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other details.

        Raises:
        ------
            HTTPException: If settings are not found for the source or token exchange fails.
        """
        # Get the settings for this source to generate the URL
        oauth2_settings = await integration_settings.get_by_short_name(source_short_name)
        if not oauth2_settings:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source_short_name}"
            )

        redirect_uri = OAuth2Service._get_redirect_url(source_short_name)

        # Render backend URL if it's a template
        if getattr(oauth2_settings, "backend_url_template", False):
            if not template_configs:
                raise ValueError(f"template_configs needed for {source_short_name}")
            try:
                backend_url = oauth2_settings.render_backend_url(**template_configs)
            except KeyError as e:
                raise ValueError(
                    f"Missing template variable {e} in template_configs for token exchange"
                ) from e
        else:
            backend_url = oauth2_settings.backend_url

        if not client_id and not client_secret:
            client_id = oauth2_settings.client_id
            client_secret = oauth2_settings.client_secret

        return await OAuth2Service._exchange_code(
            logger=ctx.logger,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            backend_url=backend_url,
            integration_config=oauth2_settings,
        )

    @staticmethod
    async def generate_auth_url_with_redirect(
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
        ----
            oauth2_settings: The OAuth2 settings for the integration
            redirect_uri: The redirect URI for the OAuth callback
            client_id: Optional client ID to override the default
            state: Optional state token for CSRF protection
            template_configs: Optional config fields for URL templates (e.g., instance_url)

        Returns:
        -------
            Tuple[str, Optional[str]]: (authorization_url, code_verifier)
                - authorization_url: The complete URL to redirect the user to
                - code_verifier: The PKCE code verifier if PKCE is required, None otherwise

        Raises:
        ------
            ValueError: If template URL requires template_configs but it's missing
        """
        if not client_id:
            client_id = oauth2_settings.client_id

        # Render URL if it's a template
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

        # Generate PKCE parameters if required by the provider
        code_verifier = None
        if oauth2_settings.requires_pkce:
            code_verifier, code_challenge = OAuth2Service._generate_pkce_challenge_pair()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        auth_url = f"{auth_url_base}?{urlencode(params)}"
        return auth_url, code_verifier

    @staticmethod
    async def exchange_authorization_code_for_token_with_redirect(
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
        ----
            ctx: The API context
            source_short_name: The short name of the integration
            code: The authorization code from the OAuth provider
            redirect_uri: Must match the one used in authorization request
            client_id: Optional client ID override
            client_secret: Optional client secret override
            template_configs: Optional config fields for URL templates
            code_verifier: PKCE code verifier (required if provider uses PKCE)

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other details

        Raises:
        ------
            HTTPException: If settings not found or token exchange fails
            ValueError: If template URL requires template_configs but it's missing
        """
        try:
            oauth2_settings = await integration_settings.get_by_short_name(source_short_name)
        except KeyError as e:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source_short_name}"
            ) from e

        # Render backend URL if it's a template
        if getattr(oauth2_settings, "backend_url_template", False):
            if not template_configs:
                raise ValueError(f"template_configs needed for {source_short_name}")
            try:
                backend_url = oauth2_settings.render_backend_url(**template_configs)
            except KeyError as e:
                raise ValueError(
                    f"Missing template variable {e} in template_configs for token exchange"
                ) from e
        else:
            backend_url = oauth2_settings.backend_url

        if not client_id:
            client_id = oauth2_settings.client_id
        if not client_secret:
            client_secret = oauth2_settings.client_secret

        return await OAuth2Service._exchange_code(
            logger=ctx.logger,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            backend_url=backend_url,
            integration_config=oauth2_settings,
            code_verifier=code_verifier,
        )

    @staticmethod
    async def refresh_access_token(
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
        ----
            db (AsyncSession): The database session.
            integration_short_name (str): The short name of the integration.
            ctx (ApiContext): The API context.
            connection_id (UUID): The ID of the connection to refresh the token for.
            decrypted_credential (dict): The token and optional config fields
            config_fields (Optional[dict]): Config fields for template rendering

        Returns:
        -------
            OAuth2TokenResponse: The response containing the new access token and other details.

        Raises:
        ------
            TokenRefreshError: If token refresh fails
            NotFoundException: If the integration is not found

        """
        try:
            # Get and validate refresh token
            refresh_token = await OAuth2Service._get_refresh_token(ctx.logger, decrypted_credential)

            # Get and validate integration config
            integration_config = await OAuth2Service._get_integration_config(
                ctx.logger, integration_short_name
            )

            # Render backend URL if it's a template
            backend_url = integration_config.backend_url
            if getattr(integration_config, "backend_url_template", False):
                if not config_fields:
                    raise ValueError(
                        f"config_fields required for token refresh of {integration_short_name}"
                    )

                # Extract only auth-required fields if config class is available
                try:
                    from airweave import crud

                    source = await crud.source.get_by_short_name(db, integration_short_name)
                    if source and source.config_class:
                        from airweave.platform.locator import resource_locator

                        config_class = resource_locator.get_config(source.config_class)
                        template_config_values = config_class.extract_template_configs(
                            config_fields
                        )
                    else:
                        template_config_values = config_fields
                except Exception:
                    # Fallback to all config fields
                    template_config_values = config_fields

                try:
                    backend_url = integration_config.backend_url.format(**template_config_values)
                    ctx.logger.debug(f"Rendered backend URL for token refresh: {backend_url}")
                except KeyError as e:
                    raise ValueError(
                        f"Missing template variable {e} in config_fields for token refresh"
                    ) from e

            # Get client credentials
            # TODO: this is the only place we need to check the db for client credentials
            client_id, client_secret = await OAuth2Service._get_client_credentials(
                ctx.logger, integration_config, None, decrypted_credential
            )

            # Prepare request parameters
            headers, payload = OAuth2Service._prepare_token_request(
                ctx.logger, integration_config, refresh_token, client_id, client_secret
            )

            # Make request and handle response
            response = await OAuth2Service._make_token_request(
                ctx.logger, backend_url, headers, payload
            )

            # Handle rotating refresh tokens if needed
            oauth2_token_response = await OAuth2Service._handle_token_response(
                db, response, integration_config, ctx, connection_id
            )

            return oauth2_token_response

        except Exception as e:
            ctx.logger.error(
                f"Token refresh failed for organization {ctx.organization.id} and "
                f"integration {integration_short_name}: {str(e)}"
            )
            raise

    @staticmethod
    async def _get_refresh_token(logger: ContextualLogger, decrypted_credential: dict) -> str:
        """Get refresh token from decrypted credentials.

        Args:
        ----
            logger (ContextualLogger): The logger to use.
            decrypted_credential (dict): The decrypted credentials containing the refresh token.

        Returns:
        -------
            str: The refresh token.

        Raises:
        ------
            TokenRefreshError: If no refresh token is found
        """
        refresh_token = decrypted_credential.get("refresh_token", None)
        if not refresh_token:
            error_message = "No refresh token found"
            logger.error(error_message)
            raise TokenRefreshError(error_message)
        return refresh_token

    @staticmethod
    async def _get_integration_config(
        logger: ContextualLogger,
        integration_short_name: str,
    ) -> schemas.Source | schemas.Destination | schemas.EmbeddingModel:
        """Get and validate integration configuration exists.

        Args:
        ----
            logger (ContextualLogger): The logger to use.
            integration_short_name (str): The short name of the integration.

        Returns:
        -------
            schemas.Source | schemas.Destination | schemas.EmbeddingModel: The integration
                configuration.

        Raises:
        ------
            NotFoundException: If integration configuration is not found

        """
        integration_config = await integration_settings.get_by_short_name(integration_short_name)
        if not integration_config:
            error_message = f"Configuration for {integration_short_name} not found"
            logger.error(error_message)
            raise NotFoundException(error_message)
        return integration_config

    @staticmethod
    async def _get_client_credentials(
        logger: ContextualLogger,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        auth_fields: Optional[dict] = None,
        decrypted_credential: Optional[dict] = None,
    ) -> tuple[str, str]:
        """Get client credentials based on priority ordering.

        Args:
        ----
            logger (ContextualLogger): The logger to use.
            integration_config: The integration configuration.
            auth_fields: Optional additional authentication fields for the connection.
            decrypted_credential: Optional decrypted credentials that may contain client ID/secret.

        Returns:
        -------
            tuple[str, str]: The client ID and client secret.

        Priority order:
        1. From decrypted_credential (if available)
        2. From auth_fields (if available)
        3. From integration_config (as fallback)
        """
        client_id = integration_config.client_id
        client_secret = integration_config.client_secret

        # First check decrypted_credential
        if decrypted_credential:
            client_id = decrypted_credential.get("client_id", client_id)
            client_secret = decrypted_credential.get("client_secret", client_secret)

        # Then check auth_fields
        if auth_fields:
            client_id = auth_fields.get("client_id", client_id)
            client_secret = auth_fields.get("client_secret", client_secret)

        return client_id, client_secret

    @staticmethod
    def _prepare_token_request(
        logger: ContextualLogger,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> tuple[dict, dict]:
        """Prepare headers and payload for token refresh request.

        Args:
        ----
            logger (ContextualLogger): The logger to use.
            integration_config (schemas.Source | schemas.Destination | schemas.EmbeddingModel):
                The integration configuration.
            refresh_token (str): The refresh token.
            client_id (str): The client ID.
            client_secret (str): The client secret.

        Returns:
        -------
            tuple[dict, dict]: The headers and payload.

        """
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
        # See: https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/#refresh-a-token
        oauth_type = getattr(integration_config, "oauth_type", None)
        if (
            oauth_type == "with_refresh"
            and hasattr(integration_config, "scope")
            and integration_config.scope
        ):
            payload["scope"] = integration_config.scope
            logger.debug(
                f"Including scope in token refresh (oauth_type=with_refresh): {integration_config.scope}"
            )
        elif oauth_type == "with_rotating_refresh":
            logger.debug(f"Skipping scope in token refresh (oauth_type=with_rotating_refresh)")

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        # Log the request details for debugging
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

    @staticmethod
    async def _make_token_request(
        logger: ContextualLogger, url: str, headers: dict, payload: dict
    ) -> httpx.Response:
        """Make the token refresh request."""
        logger.info(f"Making token request to: {url}")

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending request to {url}")
                response = await client.post(url, headers=headers, data=payload)

                logger.info(f"Received response: Status {response.status_code}, ")

                response.raise_for_status()
                return response

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during token request: {e.response.status_code} "
                f"{e.response.reason_phrase}"
            )

            # Try to log the error response
            try:
                error_content = e.response.json()
                logger.error(f"Error response body: {error_content}")
            except Exception:
                logger.error(f"Error response text: {e.response.text}")

            raise
        except Exception as e:
            logger.error(f"Unexpected error during token request: {str(e)}")
            raise

    @staticmethod
    async def _handle_token_response(
        db: AsyncSession,
        response: httpx.Response,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        ctx: ApiContext,
        connection_id: UUID,
    ) -> OAuth2TokenResponse:
        """Handle the token response and update refresh token if needed.

        Args:
        ----
            db (AsyncSession): The database session.
            logger (ContextualLogger): The logger to use.
            response (httpx.Response): The response from the token refresh request.
            integration_config (schemas.Source | schemas.Destination | schemas.EmbeddingModel):
                The integration configuration.
            ctx (ApiContext): The API context.
            connection_id (UUID): The ID of the connection to update.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the new access token and other details.
        """
        oauth2_token_response = OAuth2TokenResponse(**response.json())

        # Check if this is a rotating refresh token OAuth
        if (
            hasattr(integration_config, "oauth_type")
            and integration_config.oauth_type == "with_rotating_refresh"
        ):
            # Get connection and its credential
            connection = await crud.connection.get(db=db, id=connection_id, ctx=ctx)
            integration_credential = await crud.integration_credential.get(
                db=db, id=connection.integration_credential_id, ctx=ctx
            )

            # Update the credentials with the new refresh token
            current_credentials = credentials.decrypt(integration_credential.encrypted_credentials)
            current_credentials["refresh_token"] = oauth2_token_response.refresh_token

            # Encrypt and update the credentials
            encrypted_credentials = credentials.encrypt(current_credentials)
            await crud.integration_credential.update(
                db=db,
                db_obj=integration_credential,
                obj_in={"encrypted_credentials": encrypted_credentials},
                ctx=ctx,
            )

        return oauth2_token_response

    @staticmethod
    def _encode_client_credentials(client_id: str, client_secret: str) -> str:
        """Encodes the client ID and client secret in Base64.

        Args:
        ----
            client_id (str): The client ID.
            client_secret (str): The client secret.

        Returns:
        -------
            str: The Base64-encoded client credentials.

        """
        credentials = f"{client_id}:{client_secret}"
        credentials_bytes = credentials.encode("ascii")
        base64_bytes = base64.b64encode(credentials_bytes)
        base64_credentials = base64_bytes.decode("ascii")
        return base64_credentials

    @staticmethod
    def _generate_pkce_challenge_pair() -> Tuple[str, str]:
        """Generate PKCE code verifier and code challenge.

        PKCE (Proof Key for Code Exchange) is an OAuth 2.0 security extension
        that prevents authorization code interception attacks.

        Process:
        1. Generate a cryptographically random code_verifier (43-128 characters)
        2. Compute code_challenge = BASE64URL(SHA256(code_verifier))
        3. Send code_challenge in authorization request
        4. Send code_verifier in token exchange request

        The OAuth provider verifies that SHA256(code_verifier) == code_challenge,
        ensuring the token exchange request comes from the same client that
        initiated the authorization.

        Returns:
        -------
            Tuple[str, str]: (code_verifier, code_challenge)
                - code_verifier: Random string to be sent during token exchange
                - code_challenge: SHA256 hash to be sent during authorization

        References:
        ----------
            RFC 7636: https://tools.ietf.org/html/rfc7636
            Airtable OAuth: https://airtable.com/developers/web/api/oauth-reference

        """
        # Generate cryptographically secure random verifier (43-128 characters)
        # Using 64 bytes gives us ~86 base64 characters (well within spec)
        code_verifier = secrets.token_urlsafe(64)

        # Compute SHA256 hash of the verifier
        verifier_bytes = code_verifier.encode("ascii")
        sha256_hash = hashlib.sha256(verifier_bytes).digest()

        # Base64 URL-encode the hash (without padding as per spec)
        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode("ascii").rstrip("=")

        return code_verifier, code_challenge

    @staticmethod
    def _normalize_token_response(
        response_data: dict, integration_short_name: str, logger: ContextualLogger
    ) -> dict:
        """Normalize non-standard OAuth2 token responses to standard format.

        Some OAuth providers return tokens in non-standard nested structures.
        This method detects and normalizes them to the standard OAuth2 format.

        Args:
            response_data: Raw OAuth2 token response from provider
            integration_short_name: Provider identifier for logging
            logger: Logger for debugging

        Returns:
            Normalized token response in standard OAuth2 format with access_token at top level

        Examples of non-standard formats:
            - Slack user tokens: {"authed_user": {"access_token": "..."}}
            - Standard format: {"access_token": "...", "token_type": "Bearer"}
        """
        # Handle nested authed_user format (e.g., Slack's user token flow)
        # Pattern: {"authed_user": {"access_token": "..."}} instead of {"access_token": "..."}
        if "authed_user" in response_data and isinstance(response_data.get("authed_user"), dict):
            authed_user = response_data["authed_user"]
            # Only normalize if access_token is nested rather than at top level
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

        # Add more non-standard patterns here as needed
        # Example: if "credentials" in response_data and isinstance(...)

        # Return as-is if already in standard format
        return response_data

    @staticmethod
    def _get_redirect_url(integration_short_name: str) -> str:
        """Private method to generate the appropriate redirect URI based on environment.

        Args:
        ----
            integration_short_name: The short name of the integration.

        Returns:
        -------
            str: The redirect URI.

        """
        app_url = settings.app_url

        # if the oauth app cannot redirect to localhost because of http
        # paste: https://redirectmeto.com/ before the redirect uri
        # and set change the redirect uri in the oauth app as well

        return f"{app_url}/auth/callback"

    @staticmethod
    async def _exchange_code(
        *,
        logger: ContextualLogger,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        backend_url: str,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        code_verifier: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        """Core method to exchange an authorization code for tokens.

        Supports both standard OAuth 2.0 and PKCE (Proof Key for Code Exchange).
        When code_verifier is provided, it will be included in the token request
        to complete the PKCE flow.

        Args:
        ----
            logger: The logger to use
            code: The authorization code to exchange
            redirect_uri: The redirect URI used in the authorization request
            client_id: The OAuth2 client ID
            client_secret: The OAuth2 client secret
            backend_url: The backend URL for token exchange (may be rendered from template)
            integration_config: The integration configuration
            code_verifier: PKCE code verifier (required for PKCE-enabled providers)

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other token details

        Raises:
        ------
            HTTPException: If the token exchange fails

        """
        headers = {
            "Content-Type": integration_config.content_type,
        }

        payload = {
            "grant_type": integration_config.grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        # Add PKCE code verifier if provided (completes PKCE flow)
        if code_verifier:
            payload["code_verifier"] = code_verifier
            logger.debug("Including PKCE code_verifier in token exchange request")

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        # Log the request details for debugging
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
            # Log the actual error response from the OAuth provider
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

        # Normalize non-standard OAuth responses to standard format
        normalized_data = OAuth2Service._normalize_token_response(
            response_data, integration_config.integration_short_name, logger
        )

        return OAuth2TokenResponse(**normalized_data)

    @staticmethod
    def _supports_oauth2(oauth_type: Optional[str]) -> bool:
        """Check if the integration supports OAuth2 based on oauth_type."""
        return oauth_type is not None

    @staticmethod
    async def _create_connection(
        db: AsyncSession,
        source: schemas.Source,
        settings: BaseAuthSettings,
        oauth2_response: OAuth2TokenResponse,
        ctx: ApiContext,
    ) -> schemas.Connection:
        """Create a new connection with OAuth2 credentials."""
        # Prepare credentials based on oauth type
        # If it's access_only OAuth, only store access token
        # Otherwise store both refresh and access tokens
        decrypted_credentials = (
            {"access_token": oauth2_response.access_token}
            if (hasattr(settings, "oauth_type") and settings.oauth_type == "access_only")
            else {
                "refresh_token": oauth2_response.refresh_token,
                "access_token": oauth2_response.access_token,
            }
        )

        encrypted_credentials = credentials.encrypt(decrypted_credentials)

        async with UnitOfWork(db) as uow:
            # Create integration credential
            integration_credential_in = schemas.IntegrationCredentialCreate(
                name=f"{source.name} - {ctx.organization.id}",
                description=(f"OAuth2 credentials for {source.name} - {ctx.organization.id}"),
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                encrypted_credentials=encrypted_credentials,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_credential_in, ctx=ctx, uow=uow
            )

            await uow.session.flush()

            # Create connection
            connection_in = schemas.ConnectionCreate(
                name=f"Connection to {source.name}",
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_credential.id,
                short_name=source.short_name,
            )

            connection = await crud.connection.create(
                uow.session, obj_in=connection_in, ctx=ctx, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)

        return connection


oauth2_service = OAuth2Service()

__all__ = ["oauth2_service", "OAuth2Service"]

# Import OAuth1 service at bottom to avoid circular dependency
from airweave.platform.auth.oauth1_service import oauth1_service  # noqa: E402, F401

__all__.append("oauth1_service")
