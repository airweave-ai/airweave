"""The services for handling OAuth2 authentication and token exchange for integrations."""

import base64
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException, TokenRefreshError
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import (
    AuthType,
    BaseAuthSettings,
    OAuth2Settings,
    OAuth2TokenResponse,
)
from airweave.platform.auth.settings import integration_settings

oauth2_service_logger = logger.with_prefix("OAuth2 Service: ").with_context(
    component="oauth2_service"
)


class OAuth2Service:
    """Service class for handling OAuth2 authentication and token exchange."""

    @staticmethod
    def generate_auth_url(
        oauth2_settings: OAuth2Settings, auth_fields: Optional[dict] = None
    ) -> str:
        """Generate the OAuth2 authorization URL with the required query parameters.

        Args:
        ----
            oauth2_settings: The OAuth2 settings for the integration.
            auth_fields: Optional dict containing configuration parameters like client_id

        Returns:
        -------
            str: The authorization URL.

        """
        redirect_uri = OAuth2Service._get_redirect_url(oauth2_settings.integration_short_name)

        client_id, _ = OAuth2Service._get_client_credentials(oauth2_settings, auth_fields)

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            **(oauth2_settings.additional_frontend_params or {}),
        }

        if oauth2_settings.scope:
            params["scope"] = oauth2_settings.scope

        auth_url = f"{oauth2_settings.url}?{urlencode(params)}"

        return auth_url

    @staticmethod
    def generate_auth_url_for_trello() -> str:
        """Generate the authorization URL for Trello.

        This method could potentially be generalized to work with similar authorization flows.

        Returns:
        -------
            str: The authorization URL.

        """
        integration_short_name = "trello"
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        redirect_uri = OAuth2Service._get_redirect_url(integration_short_name)

        params = {
            "response_type": "token",
            "scope": "read,write",
            "name": integration_config.name,
            "expiration": "never",
            "return_url": redirect_uri,
            "key": integration_config.key,
        }

        auth_url = f"{integration_config.url}?{urlencode(params)}"

        return auth_url

    @staticmethod
    async def exchange_autorization_code_for_token(
        integration_short_name: str, code: str, auth_fields: Optional[dict] = None
    ) -> OAuth2TokenResponse:
        """Exchanges an authorization code for an access token.

        Args:
        ----
            integration_short_name (str): The short name of the integration.
            code (str): The authorization code received from the OAuth provider.
            auth_fields: Optional additional authentication fields for the connection

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other token details.

        Raises:
        ------
            NotFoundException: If the integration is not found
        """
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        if not integration_config:
            raise NotFoundException(f"Integration {integration_short_name} not found.")

        redirect_uri = OAuth2Service._get_redirect_url(integration_short_name)

        client_id, client_secret = OAuth2Service._get_client_credentials(
            integration_config, auth_fields
        )

        return await OAuth2Service._exchange_code(
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            integration_config=integration_config,
        )

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        integration_short_name: str,
        user: schemas.User,
        connection_id: UUID,
        decrypted_credential: dict,
    ) -> OAuth2TokenResponse:
        """Refresh an access token using a refresh token.

        Rotates the refresh token if the integration is configured to do so.

        Args:
        ----
            db (AsyncSession): The database session.
            integration_short_name (str): The short name of the integration.
            user (schemas.User): The user for whom to refresh the token.
            connection_id (UUID): The ID of the connection to refresh the token for.
            decrypted_credential (dict): The token and optional config fields

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
            refresh_token = await OAuth2Service._get_refresh_token(decrypted_credential)

            # Get and validate integration config
            integration_config = OAuth2Service._get_integration_config(integration_short_name)

            # Get client credentials
            client_id, client_secret = OAuth2Service._get_client_credentials(
                integration_config, None, decrypted_credential
            )

            # Prepare request parameters
            headers, payload = OAuth2Service._prepare_token_request(
                integration_config, refresh_token, client_id, client_secret
            )

            # Make request and handle response
            response = await OAuth2Service._make_token_request(
                integration_config.backend_url, headers, payload
            )

            # Handle rotating refresh tokens if needed
            oauth2_token_response = await OAuth2Service._handle_token_response(
                db, response, integration_config, user, connection_id
            )

            return oauth2_token_response

        except Exception as e:
            oauth2_service_logger.error(
                f"Token refresh failed for user {user.email} and "
                f"integration {integration_short_name}: {str(e)}"
            )
            raise

    @staticmethod
    async def _get_refresh_token(decrypted_credential: dict) -> str:
        """Get refresh token from decrypted credentials.

        Args:
        ----
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
            oauth2_service_logger.error(error_message)
            raise TokenRefreshError(error_message)
        return refresh_token

    @staticmethod
    def _get_integration_config(
        integration_short_name: str,
    ) -> schemas.Source | schemas.Destination | schemas.EmbeddingModel:
        """Get and validate integration configuration exists.

        Args:
        ----
            integration_short_name (str): The short name of the integration.

        Returns:
        -------
            schemas.Source | schemas.Destination | schemas.EmbeddingModel: The integration
                configuration.

        Raises:
        ------
            NotFoundException: If integration configuration is not found

        """
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        if not integration_config:
            error_message = f"Configuration for {integration_short_name} not found"
            oauth2_service_logger.error(error_message)
            raise NotFoundException(error_message)
        return integration_config

    @staticmethod
    def _get_client_credentials(
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        auth_fields: Optional[dict] = None,
        decrypted_credential: Optional[dict] = None,
    ) -> tuple[str, str]:
        """Get client credentials based on priority ordering.

        Args:
        ----
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
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> tuple[dict, dict]:
        """Prepare headers and payload for token refresh request.

        Args:
        ----
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

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        # Fixed logging statement that doesn't use short_name
        oauth2_service_logger.info(
            "Preparing token request: "
            f"URL: {integration_config.backend_url}, "
            f"Headers: {headers}, "
            f"Payload keys: {list(payload.keys())}"  # Log keys only for security
        )

        return headers, payload

    @staticmethod
    async def _make_token_request(url: str, headers: dict, payload: dict) -> httpx.Response:
        """Make the token refresh request."""
        oauth2_service_logger.info(f"Making token request to: {url}")

        try:
            async with httpx.AsyncClient() as client:
                oauth2_service_logger.info(f"Sending POST request with data: {payload}")
                response = await client.post(url, headers=headers, data=payload)

                oauth2_service_logger.info(
                    f"Received response: Status {response.status_code}, "
                    f"Headers: {dict(response.headers)}"
                )

                # Log response body for debugging
                try:
                    response_json = response.json()
                    oauth2_service_logger.info(f"Response body: {response_json}")
                except Exception:
                    oauth2_service_logger.info(f"Response body (not JSON): {response.text}")

                response.raise_for_status()
                return response

        except httpx.HTTPStatusError as e:
            oauth2_service_logger.error(
                f"HTTP error during token request: {e.response.status_code} "
                f"{e.response.reason_phrase}"
            )

            # Try to log the error response
            try:
                error_content = e.response.json()
                oauth2_service_logger.error(f"Error response body: {error_content}")
            except Exception:
                oauth2_service_logger.error(f"Error response text: {e.response.text}")

            raise
        except Exception as e:
            oauth2_service_logger.error(f"Unexpected error during token request: {str(e)}")
            raise

    @staticmethod
    async def _handle_token_response(
        db: AsyncSession,
        response: httpx.Response,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
        user: schemas.User,
        connection_id: UUID,
    ) -> OAuth2TokenResponse:
        """Handle the token response and update refresh token if needed.

        Args:
        ----
            db (AsyncSession): The database session.
            response (httpx.Response): The response from the token refresh request.
            integration_config (schemas.Source | schemas.Destination | schemas.EmbeddingModel):
                The integration configuration.
            user (schemas.User): The user to update the refresh token for.
            connection_id (UUID): The ID of the connection to update.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the new access token and other details.
        """
        oauth2_token_response = OAuth2TokenResponse(**response.json())

        if integration_config.auth_type == "oauth2_with_refresh_rotating":
            # Get connection and its credential
            connection = await crud.connection.get(db=db, id=connection_id, current_user=user)
            integration_credential = await crud.integration_credential.get(
                db=db, id=connection.integration_credential_id, current_user=user
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
                current_user=user,
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
        return f"{app_url}/auth/callback/{integration_short_name}"

    @staticmethod
    async def generate_auth_url_for_whitelabel(
        db: AsyncSession, white_label: schemas.WhiteLabel
    ) -> str:
        """Generate the OAuth2 authorization URL for a white label integration."""
        source = await crud.source.get_by_short_name(
            db=db, short_name=white_label.source_short_name
        )

        if not source:
            raise NotFoundException("Source not found")

        integration_config = integration_settings.get_by_short_name(source.short_name)

        if not integration_config:
            raise NotFoundException("Integration not found")

        # Use white_label's redirect_url instead of the default one
        params = {
            "response_type": "code",
            "client_id": white_label.client_id,
            "redirect_uri": white_label.redirect_url,
            **(integration_config.additional_frontend_params or {}),
        }

        if integration_config.scope:
            params["scope"] = integration_config.scope

        auth_url = f"{integration_config.url}?{urlencode(params)}"
        return auth_url

    @staticmethod
    async def exchange_code_for_whitelabel(
        code: str,
        white_label: schemas.WhiteLabel,
    ) -> OAuth2TokenResponse:
        """Exchange OAuth2 authorization code for tokens using white label credentials.

        Args:
        ----
            code: The authorization code to exchange
            white_label: The white label configuration to use

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other token details.

        Raises:
        ------
            NotFoundException: If the integration is not found
        """
        integration_config = integration_settings.get_by_short_name(white_label.source_short_name)
        if not integration_config:
            raise NotFoundException(f"Integration {white_label.source_short_name} not found.")

        return await OAuth2Service._exchange_code(
            code=code,
            redirect_uri=white_label.redirect_url,
            client_id=white_label.client_id,
            client_secret=white_label.client_secret,
            integration_config=integration_config,
        )

    @staticmethod
    async def _exchange_code(
        *,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        integration_config: schemas.Source | schemas.Destination | schemas.EmbeddingModel,
    ) -> OAuth2TokenResponse:
        """Core method to exchange an authorization code for tokens.

        Args:
        ----
            code: The authorization code to exchange
            redirect_uri: The redirect URI used in the authorization request
            client_id: The OAuth2 client ID
            client_secret: The OAuth2 client secret
            integration_config: The integration configuration

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other token details.

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

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    integration_config.backend_url, headers=headers, data=payload
                )
                response.raise_for_status()
        except Exception as e:
            oauth2_service_logger.error(f"Failed to exchange authorization code: {str(e)}")
            raise HTTPException(
                status_code=400, detail="Failed to exchange authorization code"
            ) from e

        return OAuth2TokenResponse(**response.json())

    @staticmethod
    async def create_oauth2_connection(
        db: AsyncSession,
        short_name: str,
        code: str,
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a new OAuth2 connection for a source.

        Does the following:
        1. Get the OAuth2 settings for the source
        2. Exchange the authorization code for a token
        3. Create an integration credential with the token
        4. Create a connection with the integration credential

        Args:
        ----
            db: Database session
            short_name: The short name of the source
            code: The authorization code to exchange
            user: The user creating the connection

        Returns:
        -------
            schemas.Connection: The created connection
        """
        settings = integration_settings.get_by_short_name(short_name)
        if not settings:
            raise NotFoundException("Integration not found")

        source = await crud.source.get_by_short_name(db, short_name)
        if not source:
            raise NotFoundException("Source not found")

        if not OAuth2Service._supports_oauth2(source.auth_type):
            raise HTTPException(status_code=400, detail="Source does not support OAuth2")

        # Exchange code for token using default credentials
        oauth2_response = await OAuth2Service.exchange_autorization_code_for_token(short_name, code)

        return await OAuth2Service._create_connection(
            db=db,
            source=source,
            settings=settings,
            oauth2_response=oauth2_response,
            user=user,
        )

    @staticmethod
    async def create_oauth2_connection_for_whitelabel(
        db: AsyncSession,
        white_label: schemas.WhiteLabel,
        code: str,
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a new OAuth2 connection using white label credentials.

        Args:
        ----
            db: Database session
            white_label: The white label configuration to use
            code: The authorization code to exchange
            user: The user creating the connection

        Returns:
        -------
            schemas.Connection: The created connection
        """
        source = await crud.source.get_by_short_name(db, white_label.source_short_name)
        if not source:
            raise NotFoundException("Source not found")

        settings = integration_settings.get_by_short_name(source.short_name)
        if not settings:
            raise NotFoundException("Integration not found")

        if not OAuth2Service._supports_oauth2(source.auth_type):
            raise HTTPException(status_code=400, detail="Source does not support OAuth2")

        # Exchange code for token using white label credentials
        oauth2_response = await OAuth2Service.exchange_code_for_whitelabel(
            code=code, white_label=white_label
        )

        return await OAuth2Service._create_connection(
            db=db,
            source=source,
            settings=settings,
            oauth2_response=oauth2_response,
            user=user,
        )

    @staticmethod
    def _supports_oauth2(auth_type: AuthType) -> bool:
        """Check if the auth type supports OAuth2."""
        return auth_type in (
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        )

    @staticmethod
    async def _create_connection(
        db: AsyncSession,
        source: schemas.Source,
        settings: BaseAuthSettings,
        oauth2_response: OAuth2TokenResponse,
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a new connection with OAuth2 credentials."""
        # Prepare credentials based on auth type
        decrypted_credentials = (
            {"access_token": oauth2_response.access_token}
            if settings.auth_type == AuthType.oauth2
            else {"refresh_token": oauth2_response.refresh_token}
        )

        encrypted_credentials = credentials.encrypt(decrypted_credentials)

        async with UnitOfWork(db) as uow:
            # Create integration credential
            integration_credential_in = schemas.IntegrationCredentialCreate(
                name=f"{source.name} - {user.email}",
                description=f"OAuth2 credentials for {source.name} - {user.email}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=source.auth_type,
                encrypted_credentials=encrypted_credentials,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_credential_in, current_user=user, uow=uow
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
                uow.session, obj_in=connection_in, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)

        return connection


oauth2_service = OAuth2Service()
