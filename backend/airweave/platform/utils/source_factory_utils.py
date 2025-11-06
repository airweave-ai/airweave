"""Shared utilities for creating and configuring source instances.

Used by both sync and search factories to ensure consistent source
instantiation with auth providers, proxy support, and token managers.
"""

from typing import Any, Callable, Dict, Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.platform.auth.schemas import BaseAuthSettings, ClientCredentialsSettings
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.auth_providers.auth_result import AuthProviderMode
from airweave.platform.auth_providers.pipedream import PipedreamAuthProvider
from airweave.platform.configs.auth import ClientCredentialsAuthConfig
from airweave.platform.http_client import PipedreamProxyClient
from airweave.platform.locator import resource_locator


async def create_auth_provider_instance(
    db: AsyncSession,
    readable_auth_provider_id: str,
    auth_provider_config: Dict[str, Any],
    ctx: ApiContext,
    logger: ContextualLogger,
) -> BaseAuthProvider:
    """Create an auth provider instance from readable_id.

    Args:
        db: Database session
        readable_auth_provider_id: The readable ID of the auth provider connection
        auth_provider_config: Configuration for the auth provider
        ctx: The API context
        logger: Logger to set on the auth provider

    Returns:
        An instance of the auth provider

    Raises:
        NotFoundException: If auth provider connection not found
    """
    # 1. Get the auth provider connection by readable_id
    auth_provider_connection = await crud.connection.get_by_readable_id(
        db, readable_id=readable_auth_provider_id, ctx=ctx
    )
    if not auth_provider_connection:
        raise NotFoundException(
            f"Auth provider connection with readable_id '{readable_auth_provider_id}' not found"
        )

    # 2. Get the integration credential
    if not auth_provider_connection.integration_credential_id:
        raise NotFoundException(
            f"Auth provider connection '{readable_auth_provider_id}' has no integration credential"
        )

    credential = await crud.integration_credential.get(
        db, auth_provider_connection.integration_credential_id, ctx
    )
    if not credential:
        raise NotFoundException("Auth provider integration credential not found")

    # 3. Decrypt the credentials
    decrypted_credentials = credentials.decrypt(credential.encrypted_credentials)

    # 4. Get the auth provider model
    auth_provider_model = await crud.auth_provider.get_by_short_name(
        db, short_name=auth_provider_connection.short_name
    )
    if not auth_provider_model:
        raise NotFoundException(
            f"Auth provider model not found for '{auth_provider_connection.short_name}'"
        )

    # 5. Create the auth provider instance
    auth_provider_class = resource_locator.get_auth_provider(auth_provider_model)
    auth_provider_instance = await auth_provider_class.create(
        credentials=decrypted_credentials,
        config=auth_provider_config,
    )

    # 6. Set logger if provided
    if hasattr(auth_provider_instance, "set_logger"):
        auth_provider_instance.set_logger(logger)

        logger.info(
            f"Created auth provider instance: {auth_provider_instance.__class__.__name__} "
            f"for readable_id: {readable_auth_provider_id}"
        )

    return auth_provider_instance


async def create_pipedream_proxy_factory(
    auth_provider_instance: PipedreamAuthProvider,
    source_connection_data: dict,
    ctx: ApiContext,
    logger: ContextualLogger,
) -> Optional[Callable]:
    """Create a factory function for Pipedream proxy clients.

    Args:
        auth_provider_instance: Pipedream auth provider instance
        source_connection_data: Source connection data dict
        ctx: API context
        logger: Logger for diagnostics

    Returns:
        Factory function that creates PipedreamProxyClient instances, or None if failed
    """
    try:
        # Get app info from Pipedream API
        async with httpx.AsyncClient() as client:
            access_token = await auth_provider_instance._ensure_valid_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "x-pd-environment": auth_provider_instance.environment,
            }

            # Map source name to Pipedream app slug if needed
            pipedream_app_slug = auth_provider_instance._get_pipedream_app_slug(
                source_connection_data["short_name"]
            )

            # Get app info
            response = await client.get(
                f"https://api.pipedream.com/v1/apps/{pipedream_app_slug}", headers=headers
            )

            if response.status_code == 404:
                logger.warning(f"App {pipedream_app_slug} not found in Pipedream")
                return None

            response.raise_for_status()
            app_info = response.json()

    except Exception as e:
        logger.error(f"Failed to get app info from Pipedream: {e}")
        return None

    # Return factory function
    def create_proxy_client(**httpx_kwargs) -> PipedreamProxyClient:
        """Creates a Pipedream proxy client with httpx-compatible interface.

        The client will call _ensure_valid_token() on each request, which:
        - Returns cached token if still valid (with 5-minute buffer)
        - Only refreshes when approaching expiry (not on every request)
        - Handles the 3600-second token lifetime automatically
        """
        return PipedreamProxyClient(
            project_id=auth_provider_instance.project_id,
            account_id=auth_provider_instance.account_id,
            external_user_id=auth_provider_instance.external_user_id,
            environment=auth_provider_instance.environment,
            pipedream_token=None,  # No static token
            token_provider=auth_provider_instance._ensure_valid_token,  # Smart refresh method
            app_info=app_info,
            **httpx_kwargs,
        )

    logger.info(f"Configured Pipedream proxy for {source_connection_data['short_name']}")
    return create_proxy_client


async def handle_auth_config_credentials(
    db: AsyncSession,
    source_connection_data: dict,
    decrypted_credential: dict,
    ctx: ApiContext,
    connection_id: UUID,
) -> Any:
    """Handle credentials that require auth configuration.

    Converts dict credentials to auth config objects and handles OAuth refresh.

    Args:
        db: Database session
        source_connection_data: Source connection data dict
        decrypted_credential: Decrypted credential dictionary
        ctx: API context
        connection_id: Connection ID for OAuth refresh

    Returns:
        Processed credentials (auth config object or updated dict)
    """
    # Use pre-fetched auth_config_class to avoid SQLAlchemy lazy loading issues
    auth_config_class = source_connection_data["auth_config_class"]
    short_name = source_connection_data["short_name"]

    auth_config = resource_locator.get_auth_config(auth_config_class)
    source_credentials = auth_config.model_validate(decrypted_credential)

    # Original OAuth refresh logic for non-auth-provider sources
    # If the source_credential has a refresh token, exchange it for an access token
    if hasattr(source_credentials, "refresh_token") and source_credentials.refresh_token:
        from airweave.platform.auth.oauth2_service import oauth2_service

        oauth2_response = await oauth2_service.refresh_access_token(
            db,
            short_name,
            ctx,
            connection_id,
            decrypted_credential,
            source_connection_data["config_fields"],
        )
        # Update the access_token in the credentials while preserving other fields
        # This is critical for sources like Salesforce that need instance_url
        updated_credentials = decrypted_credential.copy()
        updated_credentials["access_token"] = oauth2_response.access_token

        # Return the updated credentials dict (NOT just the access token)
        # This preserves fields like instance_url, client_id, etc.
        return updated_credentials

    if issubclass(auth_config, ClientCredentialsAuthConfig):
        from airweave.platform.auth.oauth2_service import oauth2_service

        oauth2_response = await oauth2_service.exchange_client_credentials_for_token(
            ctx,
            short_name,
            source_credentials.client_id,
            source_credentials.client_secret,
            source_connection_data["config_fields"],
        )
        decrypted_credential["access_token"] = oauth2_response.access_token
        return decrypted_credential
    return source_credentials


async def process_credentials_for_source(
    raw_credentials: Any,
    source_connection_data: dict,
    logger: ContextualLogger,
    auth_settings: Optional[BaseAuthSettings] = None,
) -> Any:
    """Process raw credentials into the format expected by the source.

    This method handles three cases:
    1. OAuth sources without auth_config_class: Extract just the access_token string
    2. Sources with auth_config_class and dict credentials: Convert to auth config object
    3. Other sources: Pass through as-is

    Args:
        raw_credentials: Raw credentials from auth provider or database
        source_connection_data: Source connection data dict
        logger: Logger for diagnostics
        auth_settings: Optional typed auth schema (OAuth2Settings or ClientCredentialsSettings)
            to avoid re-loading from integration_settings

    Returns:
        Processed credentials in format expected by source
    """
    from airweave.platform.auth.schemas import (
        OAuth2Settings,
    )

    auth_config_class_name = source_connection_data.get("auth_config_class")
    source_model = source_connection_data.get("source_model")
    short_name = source_connection_data["short_name"]

    if isinstance(auth_settings, (OAuth2Settings, ClientCredentialsSettings)):
        return raw_credentials["access_token"]

    # Case 1: OAuth sources without auth_config_class need just the access_token string
    # Use typed auth settings to check explicitly (no more hasattr!)
    if not auth_config_class_name and source_model and source_model.oauth_type:
        if not auth_settings:
            from airweave.platform.auth.settings import integration_settings

            auth_settings = await integration_settings.get_by_short_name(short_name)

        if isinstance(raw_credentials, dict) and "access_token" in raw_credentials:
            return raw_credentials["access_token"]
        elif isinstance(raw_credentials, str):
            logger.debug(f"OAuth source {short_name} credentials already a string token")
            return raw_credentials
        else:
            logger.warning(
                f"OAuth source {short_name} credentials not in expected format: "
                f"{type(raw_credentials)}"
            )
            return raw_credentials

    # Case 2: Sources with auth_config_class and dict credentials
    # Convert dict to auth config object (e.g., Stripe expects StripeAuthConfig)
    if auth_config_class_name and isinstance(raw_credentials, dict):
        try:
            auth_config_class = resource_locator.get_auth_config(auth_config_class_name)
            processed_credentials = auth_config_class.model_validate(raw_credentials)
            logger.debug(f"Converted credentials dict to {auth_config_class_name} for {short_name}")
            return processed_credentials
        except Exception as e:
            logger.error(f"Failed to convert credentials to auth config object: {e}")
            raise

    # Case 3: Pass through as-is (already in correct format)
    return raw_credentials


async def get_auth_configuration(
    db: AsyncSession,
    source_connection_data: dict,
    ctx: ApiContext,
    logger: ContextualLogger,
    access_token: Optional[str] = None,
) -> dict:
    """Get complete auth configuration including credentials and proxy setup.

    Handles all authentication methods:
    - Direct token injection (sync only, via access_token parameter)
    - Auth provider connections (Pipedream direct/proxy, Composio direct)
    - Database-stored credentials with OAuth refresh

    Args:
        db: Database session
        source_connection_data: Dict with source connection info including:
            - readable_auth_provider_id (optional)
            - auth_provider_config (optional)
            - integration_credential_id (optional)
            - short_name (required)
            - auth_config_class (optional)
            - connection_id (optional)
            - config_fields (optional)
        ctx: API context
        logger: Contextual logger
        access_token: Optional direct token injection (sync only)

    Returns:
        Dict with:
        - credentials: Actual credentials or "PROXY_MODE" placeholder
        - http_client_factory: Optional factory for creating proxy clients
        - auth_provider_instance: Optional auth provider instance
        - auth_mode: AuthProviderMode (DIRECT or PROXY)
    """
    # Case 1: Direct token injection (highest priority - sync only)
    if access_token:
        logger.debug("Using directly injected access token")
        return {
            "credentials": access_token,
            "http_client_factory": None,
            "auth_provider_instance": None,
            "auth_mode": AuthProviderMode.DIRECT,
        }

    # Case 2: Auth provider connection
    readable_auth_provider_id = source_connection_data.get("readable_auth_provider_id")
    auth_provider_config = source_connection_data.get("auth_provider_config")

    if readable_auth_provider_id and auth_provider_config:
        logger.info("Using auth provider for authentication")

        # Create auth provider instance
        auth_provider_instance = await create_auth_provider_instance(
            db=db,
            readable_auth_provider_id=readable_auth_provider_id,
            auth_provider_config=auth_provider_config,
            ctx=ctx,
            logger=logger,
        )

        # Get auth result with explicit mode
        from airweave.core.auth_provider_service import auth_provider_service
        from airweave.db.session import get_db_context

        async with get_db_context() as db:
            source_auth_config_fields = (
                await auth_provider_service.get_runtime_auth_fields_for_source(
                    db, source_connection_data["short_name"]
                )
            )

        auth_result = await auth_provider_instance.get_auth_result(
            source_short_name=source_connection_data["short_name"],
            source_auth_config_fields=source_auth_config_fields,
        )

        if auth_result.requires_proxy:
            logger.info(f"Auth provider requires proxy mode: {auth_result.proxy_config}")

            # Create proxy client factory if it's Pipedream
            http_client_factory = None
            if isinstance(auth_provider_instance, PipedreamAuthProvider):
                http_client_factory = await create_pipedream_proxy_factory(
                    auth_provider_instance=auth_provider_instance,
                    source_connection_data=source_connection_data,
                    ctx=ctx,
                    logger=logger,
                )

            return {
                "credentials": "PROXY_MODE",  # Placeholder
                "http_client_factory": http_client_factory,
                "auth_provider_instance": auth_provider_instance,
                "auth_mode": AuthProviderMode.PROXY,
            }
        else:
            # Direct mode with credentials
            return {
                "credentials": auth_result.credentials,
                "http_client_factory": None,
                "auth_provider_instance": auth_provider_instance,
                "auth_mode": AuthProviderMode.DIRECT,
            }

    # Case 3: Database credentials (regular flow)
    integration_credential_id = source_connection_data.get("integration_credential_id")
    if not integration_credential_id:
        raise NotFoundException("Source connection has no integration credential")

    credential = await crud.integration_credential.get(db, integration_credential_id, ctx)
    if not credential:
        raise NotFoundException("Source integration credential not found")

    decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

    # Check if we need to handle auth config (e.g., OAuth refresh)
    auth_config_class = source_connection_data.get("auth_config_class")
    if auth_config_class:
        processed = await handle_auth_config_credentials(
            db=db,
            source_connection_data=source_connection_data,
            decrypted_credential=decrypted_credential,
            ctx=ctx,
            connection_id=source_connection_data.get("connection_id"),
        )
        return {
            "credentials": processed,
            "http_client_factory": None,
            "auth_provider_instance": None,
            "auth_mode": AuthProviderMode.DIRECT,
        }

    return {
        "credentials": decrypted_credential,
        "http_client_factory": None,
        "auth_provider_instance": None,
        "auth_mode": AuthProviderMode.DIRECT,
    }
