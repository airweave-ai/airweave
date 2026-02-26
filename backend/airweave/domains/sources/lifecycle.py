"""Source lifecycle service — creates, configures, and validates source instances.

Replaces the scattered resource_locator.get_source() + manual .create()/.validate()/
set_*() calls that were duplicated across sync builders, search factories, and
credential services.
"""

from typing import Any, Callable, Dict, Optional, Union
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import FeatureFlag
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import (
    IntegrationCredentialRepositoryProtocol,
)
from airweave.domains.oauth.protocols import OAuth2ServiceProtocol
from airweave.domains.source_connections.protocols import (
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.sources.exceptions import (
    SourceCreationError,
    SourceNotFoundError,
    SourceValidationError,
)
from airweave.domains.sources.protocols import (
    SourceLifecycleServiceProtocol,
    SourceRegistryProtocol,
)
from airweave.domains.sources.types import AuthConfig, SourceConnectionData
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.auth_providers.auth_result import AuthProviderMode
from airweave.platform.auth_providers.pipedream import PipedreamAuthProvider
from airweave.platform.http_client import PipedreamProxyClient
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.token_manager import TokenManager
from airweave.schemas.source_connection import OAuthType

SourceCredentials = Union[str, dict, BaseModel]


class SourceLifecycleService(SourceLifecycleServiceProtocol):
    """Manages source instance creation, configuration, and validation.

    All external dependencies are injected via constructor — no module-level
    singletons, no resource_locator, no crud imports.
    """

    def __init__(
        self,
        source_registry: SourceRegistryProtocol,
        auth_provider_registry: AuthProviderRegistryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        conn_repo: ConnectionRepositoryProtocol,
        cred_repo: IntegrationCredentialRepositoryProtocol,
        oauth2_service: OAuth2ServiceProtocol,
    ) -> None:
        """Initialize with all required dependencies.

        Args:
            source_registry: In-memory registry of source metadata (built at startup).
            auth_provider_registry: In-memory registry of auth provider metadata.
            sc_repo: Source connection repository (wraps crud.source_connection).
            conn_repo: Connection repository (wraps crud.connection).
            cred_repo: Integration credential repository (wraps crud.integration_credential).
            oauth2_service: OAuth2 token refresh service.
        """
        self._source_registry = source_registry
        self._auth_provider_registry = auth_provider_registry
        self._sc_repo = sc_repo
        self._conn_repo = conn_repo
        self._cred_repo = cred_repo
        self._oauth2_service = oauth2_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        *,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        """Create a fully configured source instance for sync or search.

        Orchestrates:
        1. Load source connection + connection from DB
        2. Resolve source class from registry (no resource_locator)
        3. Get auth configuration (credentials, proxy, auth provider)
        4. Process credentials for source consumption
        5. Create source instance
        6. Configure logger, token manager, HTTP client,
           rate limiting, sync identifiers
        """
        logger = ctx.logger

        # 1. Load source connection data
        source_connection_data = await self._load_source_connection_data(
            db, source_connection_id, ctx, logger
        )

        # 2. Get auth configuration (credentials + proxy setup)
        auth_config = await self._get_auth_configuration(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
        )

        # 3. Process credentials for source consumption
        source_credentials = self._process_credentials_for_source(
            raw_credentials=auth_config.credentials,
            source_connection_data=source_connection_data,
            logger=logger,
        )

        # 4. Create source instance
        source = await source_connection_data.source_class.create(
            source_credentials, config=source_connection_data.config_fields
        )

        # 5. Configure source
        self._configure_logger(source, logger)
        self._configure_http_client_factory(source, auth_config)
        self._configure_sync_identifiers(source, source_connection_data, ctx)

        await self._configure_token_manager(
            db=db,
            source=source,
            source_connection_data=source_connection_data,
            source_credentials=auth_config.credentials,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
            auth_config=auth_config,
        )

        self._wrap_source_with_airweave_client(
            source=source,
            source_short_name=source_connection_data.short_name,
            source_connection_id=source_connection_data.source_connection_id,
            ctx=ctx,
            logger=logger,
        )

        return source

    async def validate(
        self,
        short_name: str,
        credentials: Union[dict, BaseModel, str],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate credentials by creating a lightweight source and calling .validate().

        No token manager, no HTTP wrapping, no rate limiting — just create + validate.

        Raises:
            SourceNotFoundError: If source short_name is not in the registry.
            SourceCreationError: If source_class.create() fails.
            SourceValidationError: If source.validate() returns False or raises.
        """
        try:
            entry = self._source_registry.get(short_name)
        except KeyError:
            raise SourceNotFoundError(short_name)

        source_class = entry.source_class_ref

        try:
            source = await source_class.create(credentials, config=config)
        except Exception as exc:
            raise SourceCreationError(short_name, str(exc)) from exc

        try:
            is_valid = await source.validate()
        except Exception as exc:
            raise SourceValidationError(short_name, f"validation raised: {exc}") from exc

        if not is_valid:
            raise SourceValidationError(short_name, "validate() returned False")

    # ------------------------------------------------------------------
    # Private: data loading
    # ------------------------------------------------------------------

    async def _load_source_connection_data(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> SourceConnectionData:
        """Load source connection, connection, and resolve source class from registry."""
        source_connection = await self._sc_repo.get(db, source_connection_id, ctx)
        if not source_connection:
            raise NotFoundException(f"Source connection {source_connection_id} not found")

        short_name = str(source_connection.short_name)

        # Resolve source class from registry
        try:
            entry = self._source_registry.get(short_name)
        except KeyError:
            raise SourceNotFoundError(short_name)

        # Load connection for credential access
        connection = await self._conn_repo.get(db, source_connection.connection_id, ctx)
        if not connection:
            raise NotFoundException("Connection not found")

        connection_id = UUID(str(connection.id))

        readable_auth_provider_id = getattr(source_connection, "readable_auth_provider_id", None)

        if not readable_auth_provider_id and not connection.integration_credential_id:
            raise NotFoundException(f"Connection {connection_id} has no integration credential")

        integration_credential_id = (
            UUID(str(connection.integration_credential_id))
            if connection.integration_credential_id
            else None
        )

        return SourceConnectionData(
            source_connection_obj=source_connection,
            connection=connection,
            source_class=entry.source_class_ref,
            config_fields=source_connection.config_fields or {},
            short_name=short_name,
            source_connection_id=UUID(str(source_connection.id)),
            auth_config_class=(entry.auth_config_ref.__name__ if entry.auth_config_ref else None),
            connection_id=connection_id,
            integration_credential_id=integration_credential_id,
            oauth_type=entry.oauth_type,
            readable_auth_provider_id=readable_auth_provider_id,
            auth_provider_config=getattr(source_connection, "auth_provider_config", None),
        )

    # ------------------------------------------------------------------
    # Private: auth configuration
    # ------------------------------------------------------------------

    async def _get_auth_configuration(
        self,
        db: AsyncSession,
        source_connection_data: SourceConnectionData,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str] = None,
    ) -> AuthConfig:
        """Get complete auth configuration including credentials and proxy setup.

        Handles three auth methods:
        - Direct token injection (sync only, via access_token parameter)
        - Auth provider connections (Pipedream direct/proxy, Composio direct)
        - Database-stored credentials with OAuth refresh
        """
        # Case 1: Direct token injection (highest priority — sync only)
        if access_token:
            logger.debug("Using directly injected access token")
            return AuthConfig(
                credentials=access_token,
                http_client_factory=None,
                auth_provider_instance=None,
                auth_mode=AuthProviderMode.DIRECT,
            )

        # Case 2: Auth provider connection
        if (
            source_connection_data.readable_auth_provider_id
            and source_connection_data.auth_provider_config
        ):
            return await self._get_auth_provider_configuration(
                db=db,
                source_connection_data=source_connection_data,
                readable_auth_provider_id=source_connection_data.readable_auth_provider_id,
                auth_provider_config=source_connection_data.auth_provider_config,
                ctx=ctx,
                logger=logger,
            )

        # Case 3: Database credentials (regular flow)
        return await self._get_database_credentials(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
        )

    async def _get_auth_provider_configuration(
        self,
        db: AsyncSession,
        source_connection_data: SourceConnectionData,
        readable_auth_provider_id: str,
        auth_provider_config: Dict[str, Any],
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> AuthConfig:
        """Resolve credentials via an auth provider (Pipedream, Composio, etc.)."""
        logger.info("Using auth provider for authentication")

        auth_provider_instance = await self._create_auth_provider_instance(
            db=db,
            readable_auth_provider_id=readable_auth_provider_id,
            auth_provider_config=auth_provider_config,
            ctx=ctx,
            logger=logger,
        )

        # Get runtime auth fields from the source registry (precomputed at startup)
        short_name = source_connection_data.short_name
        entry = self._source_registry.get(short_name)
        auth_fields_all = entry.runtime_auth_all_fields
        auth_fields_optional = entry.runtime_auth_optional_fields

        source_config_field_mappings = self._build_source_config_field_mappings(
            source_connection_data
        )

        auth_result = await auth_provider_instance.get_auth_result(
            source_short_name=short_name,
            source_auth_config_fields=auth_fields_all,
            optional_fields=auth_fields_optional,
            source_config_field_mappings=source_config_field_mappings or None,
        )

        if auth_result.source_config:
            self._merge_source_config(source_connection_data, auth_result.source_config)

        if auth_result.requires_proxy:
            logger.info(f"Auth provider requires proxy mode: {auth_result.proxy_config}")

            http_client_factory = None
            if isinstance(auth_provider_instance, PipedreamAuthProvider):
                http_client_factory = await self._create_pipedream_proxy_factory(
                    auth_provider_instance=auth_provider_instance,
                    source_connection_data=source_connection_data,
                    ctx=ctx,
                    logger=logger,
                )

            return AuthConfig(
                credentials="PROXY_MODE",
                http_client_factory=http_client_factory,
                auth_provider_instance=auth_provider_instance,
                auth_mode=AuthProviderMode.PROXY,
            )

        return AuthConfig(
            credentials=auth_result.credentials,
            http_client_factory=None,
            auth_provider_instance=auth_provider_instance,
            auth_mode=AuthProviderMode.DIRECT,
        )

    async def _get_database_credentials(
        self,
        db: AsyncSession,
        source_connection_data: SourceConnectionData,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> AuthConfig:
        """Load and decrypt credentials from the database."""
        if not source_connection_data.integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await self._cred_repo.get(
            db, source_connection_data.integration_credential_id, ctx
        )
        if not credential:
            raise NotFoundException("Source integration credential not found")

        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        if source_connection_data.auth_config_class:
            processed = await self._handle_auth_config_credentials(
                db=db,
                source_connection_data=source_connection_data,
                decrypted_credential=decrypted_credential,
                ctx=ctx,
                connection_id=source_connection_data.connection_id,
            )
            return AuthConfig(
                credentials=processed,
                http_client_factory=None,
                auth_provider_instance=None,
                auth_mode=AuthProviderMode.DIRECT,
            )

        return AuthConfig(
            credentials=decrypted_credential,
            http_client_factory=None,
            auth_provider_instance=None,
            auth_mode=AuthProviderMode.DIRECT,
        )

    # ------------------------------------------------------------------
    # Private: auth helpers
    # ------------------------------------------------------------------

    async def _create_auth_provider_instance(
        self,
        db: AsyncSession,
        readable_auth_provider_id: str,
        auth_provider_config: Dict[str, Any],
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> BaseAuthProvider:
        """Create an auth provider instance from readable_id.

        Uses auth_provider_registry to resolve the provider class (replaces
        crud.auth_provider.get_by_short_name + resource_locator.get_auth_provider).
        """
        auth_provider_connection = await self._conn_repo.get_by_readable_id(
            db, readable_id=readable_auth_provider_id, ctx=ctx
        )
        if not auth_provider_connection:
            raise NotFoundException(
                f"Auth provider connection with readable_id '{readable_auth_provider_id}' not found"
            )

        if not auth_provider_connection.integration_credential_id:
            raise NotFoundException(
                f"Auth provider connection '{readable_auth_provider_id}' "
                f"has no integration credential"
            )

        credential = await self._cred_repo.get(
            db, auth_provider_connection.integration_credential_id, ctx
        )
        if not credential:
            raise NotFoundException("Auth provider integration credential not found")

        decrypted_credentials = credentials.decrypt(credential.encrypted_credentials)

        # Resolve auth provider class from registry (replaces resource_locator)
        provider_short_name = auth_provider_connection.short_name
        try:
            registry_entry = self._auth_provider_registry.get(provider_short_name)
        except KeyError:
            raise NotFoundException(f"Auth provider '{provider_short_name}' not found in registry")

        auth_provider_class = registry_entry.provider_class_ref
        auth_provider_instance = await auth_provider_class.create(
            credentials=decrypted_credentials,
            config=auth_provider_config,
        )

        if hasattr(auth_provider_instance, "set_logger"):
            auth_provider_instance.set_logger(logger)
            logger.info(
                f"Created auth provider instance: {auth_provider_instance.__class__.__name__} "
                f"for readable_id: {readable_auth_provider_id}"
            )

        return auth_provider_instance

    @staticmethod
    async def _create_pipedream_proxy_factory(
        auth_provider_instance: PipedreamAuthProvider,
        source_connection_data: SourceConnectionData,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> Optional[Callable]:
        """Create a factory function for Pipedream proxy clients."""
        try:
            async with httpx.AsyncClient() as client:
                access_token = await auth_provider_instance._ensure_valid_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "x-pd-environment": auth_provider_instance.environment,
                }

                pipedream_app_slug = auth_provider_instance._get_pipedream_app_slug(
                    source_connection_data.short_name
                )

                response = await client.get(
                    f"https://api.pipedream.com/v1/apps/{pipedream_app_slug}",
                    headers=headers,
                )

                if response.status_code == 404:
                    logger.warning(f"App {pipedream_app_slug} not found in Pipedream")
                    return None

                response.raise_for_status()
                app_info = response.json()

        except Exception as e:
            logger.error(f"Failed to get app info from Pipedream: {e}")
            return None

        def create_proxy_client(**httpx_kwargs) -> PipedreamProxyClient:
            return PipedreamProxyClient(
                project_id=auth_provider_instance.project_id,
                account_id=auth_provider_instance.account_id,
                external_user_id=auth_provider_instance.external_user_id,
                environment=auth_provider_instance.environment,
                pipedream_token=None,
                token_provider=auth_provider_instance._ensure_valid_token,
                app_info=app_info,
                **httpx_kwargs,
            )

        logger.info(f"Configured Pipedream proxy for {source_connection_data.short_name}")
        return create_proxy_client

    async def _handle_auth_config_credentials(
        self,
        db: AsyncSession,
        source_connection_data: SourceConnectionData,
        decrypted_credential: dict,
        ctx: ApiContext,
        connection_id: UUID,
    ) -> Union[dict, BaseModel]:
        """Handle credentials that require auth config (e.g. OAuth refresh).

        Uses source_registry.auth_config_ref instead of resource_locator.get_auth_config().
        Uses injected oauth2_service instead of module-level singleton.
        """
        short_name = source_connection_data.short_name
        entry = self._source_registry.get(short_name)
        auth_config_class = entry.auth_config_ref

        if not auth_config_class:
            return decrypted_credential

        source_credentials = auth_config_class.model_validate(decrypted_credential)

        if hasattr(source_credentials, "refresh_token") and source_credentials.refresh_token:
            oauth2_response = await self._oauth2_service.refresh_access_token(
                db,
                short_name,
                ctx,
                connection_id,
                decrypted_credential,
                source_connection_data.config_fields,
            )
            updated_credentials = decrypted_credential.copy()
            updated_credentials["access_token"] = oauth2_response.access_token
            return auth_config_class.model_validate(updated_credentials)

        return source_credentials

    # ------------------------------------------------------------------
    # Private: credential processing
    # ------------------------------------------------------------------

    def _process_credentials_for_source(
        self,
        raw_credentials: Union[dict, BaseModel],
        source_connection_data: SourceConnectionData,
        logger: ContextualLogger,
    ) -> SourceCredentials:
        """Process raw credentials into the format expected by the source.

        Handles three cases:
        1. OAuth sources without auth_config_class: Extract just the access_token string
        2. Sources with auth_config_class and dict credentials: Convert to auth config object
        3. Other sources: Pass through as-is
        """
        short_name = source_connection_data.short_name
        oauth_type = source_connection_data.oauth_type

        # Case 1: OAuth sources without auth_config_class need just the access_token string
        entry = self._source_registry.get(short_name)
        auth_config_ref = entry.auth_config_ref

        if not auth_config_ref and oauth_type:
            if isinstance(raw_credentials, dict) and "access_token" in raw_credentials:
                logger.debug(f"Extracting access_token for OAuth source {short_name}")
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
        if auth_config_ref and isinstance(raw_credentials, dict):
            try:
                processed_credentials = auth_config_ref.model_validate(raw_credentials)
                logger.debug(
                    f"Converted credentials dict to {auth_config_ref.__name__} for {short_name}"
                )
                return processed_credentials
            except Exception as e:
                logger.error(f"Failed to convert credentials to auth config object: {e}")
                raise

        # Case 3: Pass through as-is
        return raw_credentials

    # ------------------------------------------------------------------
    # Private: source configuration helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_logger(source: BaseSource, logger: ContextualLogger) -> None:
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

    @staticmethod
    def _configure_http_client_factory(source: BaseSource, auth_config: AuthConfig) -> None:
        if auth_config.http_client_factory:
            source.set_http_client_factory(auth_config.http_client_factory)

    @staticmethod
    def _configure_sync_identifiers(
        source: BaseSource, source_connection_data: SourceConnectionData, ctx: ApiContext
    ) -> None:
        try:
            organization_id = ctx.organization.id
            sc_id = source_connection_data.source_connection_id
            if hasattr(source, "set_sync_identifiers") and sc_id:
                source.set_sync_identifiers(
                    organization_id=str(organization_id),
                    source_connection_id=str(sc_id),
                )
        except Exception:
            pass  # Non-fatal for older sources

    @staticmethod
    async def _configure_token_manager(
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: SourceConnectionData,
        source_credentials: SourceCredentials,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str],
        auth_config: AuthConfig,
    ) -> None:
        """Set up token manager for OAuth sources that support refresh."""
        auth_mode = auth_config.auth_mode
        auth_provider_instance: Optional[BaseAuthProvider] = auth_config.auth_provider_instance

        if access_token is not None:
            logger.debug(
                f"Skipping token manager for {source_connection_data.short_name} "
                f"— direct token injection"
            )
            return

        if auth_mode == AuthProviderMode.PROXY:
            logger.info(
                f"Skipping token manager for {source_connection_data.short_name} — proxy mode"
            )
            return

        short_name = source_connection_data.short_name
        oauth_type = source_connection_data.oauth_type

        if not oauth_type:
            return

        if oauth_type not in (OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH):
            logger.debug(
                f"Skipping token manager for {short_name} — "
                f"oauth_type={oauth_type} does not support refresh"
            )
            return

        try:
            minimal_connection = type(
                "SourceConnection",
                (),
                {
                    "id": source_connection_data.connection_id,
                    "integration_credential_id": source_connection_data.integration_credential_id,
                    "config_fields": source_connection_data.config_fields,
                },
            )()

            token_manager = TokenManager(
                db=db,
                source_short_name=short_name,
                source_connection=minimal_connection,
                ctx=ctx,
                initial_credentials=source_credentials,
                is_direct_injection=False,
                logger_instance=logger,
                auth_provider_instance=auth_provider_instance,
            )
            source.set_token_manager(token_manager)

            logger.info(
                f"Token manager initialized for OAuth source {short_name} "
                f"(auth_provider: {'Yes' if auth_provider_instance else 'None'})"
            )
        except Exception as e:
            logger.error(f"Failed to setup token manager for '{short_name}': {e}")

    # ------------------------------------------------------------------
    # Private: rate limiting wrapper
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_source_with_airweave_client(
        source: BaseSource,
        source_short_name: str,
        source_connection_id: UUID,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> None:
        """Wrap source HTTP client with AirweaveHttpClient for rate limiting.

        ALL sources are wrapped. The client checks internally:
        1. Is SOURCE_RATE_LIMITING feature enabled? -> No = skip check
        2. Is rate_limit_level set? -> No = skip check
        3. Is limit configured in DB? -> No = skip check
        4. Otherwise -> enforce limit
        """
        feature_enabled = ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING)
        original_factory = source._http_client_factory

        def airweave_client_factory(**kwargs):
            if original_factory:
                base_client = original_factory(**kwargs)
            else:
                base_client = httpx.AsyncClient(**kwargs)

            return AirweaveHttpClient(
                wrapped_client=base_client,
                org_id=ctx.organization.id,
                source_short_name=source_short_name,
                source_connection_id=source_connection_id,
                feature_flag_enabled=feature_enabled,
                logger=logger,
            )

        source.set_http_client_factory(airweave_client_factory)
        logger.debug(
            f"AirweaveHttpClient configured for {source.__class__.__name__} "
            f"(feature_flag_enabled={feature_enabled})"
        )

    # ------------------------------------------------------------------
    # Private: config field helpers
    # ------------------------------------------------------------------

    def _build_source_config_field_mappings(
        self,
        source_connection_data: SourceConnectionData,
    ) -> Dict[str, str]:
        """Build a mapping of config fields that can be populated by auth providers.

        Introspects the source's config class (from registry) for fields with
        `auth_provider_field` in their json_schema_extra.
        """
        short_name = source_connection_data.short_name
        if not short_name:
            return {}

        try:
            entry = self._source_registry.get(short_name)
        except KeyError:
            return {}

        config_class = entry.config_ref
        if not config_class:
            return {}

        mappings = {}
        for field_name, field_info in config_class.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if "auth_provider_field" in extra:
                mappings[field_name] = extra["auth_provider_field"]

        return mappings

    @staticmethod
    def _merge_source_config(
        source_connection_data: SourceConnectionData,
        source_config: Dict[str, Any],
    ) -> None:
        """Merge auth-provider-sourced config into config_fields.

        User-provided values take precedence over auth-provider values.
        """
        existing_config = source_connection_data.config_fields or {}
        for key, value in source_config.items():
            if key not in existing_config or existing_config[key] is None:
                existing_config[key] = value
        source_connection_data.config_fields = existing_config
