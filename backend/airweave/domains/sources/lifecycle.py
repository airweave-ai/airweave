"""Source lifecycle service — creates, configures, and validates source instances.

Replaces the scattered resource_locator.get_source() + manual .create()/.validate()/
set_*() calls that were duplicated across sync builders, search factories, and
credential services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from uuid import UUID

if TYPE_CHECKING:
    from airweave.domains.sources.token_providers.protocol import SourceAuthProvider

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger, LoggerConfigurator
from airweave.core.shared_models import FeatureFlag
from airweave.domains.auth_provider._base import BaseAuthProvider
from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
)
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialServiceProtocol
from airweave.domains.oauth.protocols import OAuth2ServiceProtocol
from airweave.domains.source_connections.protocols import (
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceCreationError,
    SourceNotFoundError,
    SourceValidationError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenExpiredError,
    TokenProviderAccountGoneError,
)
from airweave.domains.sources.protocols import (
    SourceLifecycleServiceProtocol,
    SourceRegistryProtocol,
)
from airweave.domains.sources.rate_limiting.service import SourceRateLimiter
from airweave.domains.sources.token_providers.auth_provider import AuthProviderTokenProvider
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.oauth import OAuthTokenProvider
from airweave.domains.sources.token_providers.static import StaticTokenProvider
from airweave.domains.sources.types import AuthConfig, SourceConnectionData, SourceRegistryEntry
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource

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
        credential_service: IntegrationCredentialServiceProtocol,
        oauth2_service: OAuth2ServiceProtocol,
    ) -> None:
        """Initialize with all required dependencies."""
        self._source_registry = source_registry
        self._auth_provider_registry = auth_provider_registry
        self._sc_repo = sc_repo
        self._conn_repo = conn_repo
        self._credential_service = credential_service
        self._oauth2_service = oauth2_service

        from airweave.core.redis_client import redis_client
        from airweave.domains.sources.rate_limiting.config_provider import (
            DatabaseRateLimitConfigProvider,
        )

        redis = redis_client.client
        self._rate_limiter = SourceRateLimiter(
            redis=redis,
            source_registry=source_registry,
            config_provider=DatabaseRateLimitConfigProvider(redis=redis),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: BaseContext,
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
            db, source_connection_id, ctx
        )

        # 2. Get auth configuration (credentials + proxy setup)
        auth_config = await self._get_auth_configuration(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
        )

        # 3. Resolve auth provider
        token_provider = await self._resolve_token_provider(
            source_connection_data=source_connection_data,
            source_credentials=auth_config.credentials,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
            auth_config=auth_config,
        )

        # 4. Build HTTP client with rate limiting
        http_client = self._build_http_client(
            source_short_name=source_connection_data.short_name,
            source_connection_id=source_connection_data.source_connection_id,
            ctx=ctx,
            logger=logger,
        )

        # 5. Parse config_fields into typed config
        entry = self._source_registry.get(source_connection_data.short_name)
        config = self._build_typed_config(entry, source_connection_data.config_fields)

        # 6. Create source instance with all deps injected
        source = await source_connection_data.source_class.create(
            auth=token_provider,
            logger=logger,
            http_client=http_client,
            config=config,
        )

        # 7. Validate credentials early so failures surface as NEEDS_REAUTH.
        #    Only catch auth-related exceptions — transient errors (server 5xx,
        #    rate limits, network timeouts) must propagate so they don't
        #    incorrectly pause schedules or set NEEDS_REAUTH status.
        try:
            await source.validate()
        except (
            SourceAuthError,
            AuthProviderAuthError,
            AuthProviderAccountNotFoundError,
            TokenCredentialsInvalidError,
            TokenExpiredError,
            TokenProviderAccountGoneError,
        ) as exc:
            raise SourceValidationError(
                short_name=source_connection_data.short_name,
                reason=f"credential validation failed: {exc}",
            ) from exc

        return source

    async def validate(
        self,
        short_name: str,
        credentials: Union[dict, BaseModel, str],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate credentials by creating a lightweight source and calling .validate().

        Wraps credentials in a StaticTokenProvider / DirectCredentialProvider
        and provides a plain httpx client (no rate limiting) so the source
        contract is satisfied.

        Raises:
            SourceNotFoundError: If source short_name is not in the registry.
            Exception: If source_class.create() or source.validate() fails.
        """
        from uuid import UUID as _UUID

        try:
            entry = self._source_registry.get(short_name)
        except KeyError:
            raise SourceNotFoundError(short_name)

        source_class = entry.source_class_ref
        normalized = self._normalize_credentials(credentials, entry)

        if isinstance(normalized, str):
            auth = StaticTokenProvider(normalized, source_short_name=short_name)
        else:
            auth = DirectCredentialProvider(normalized, source_short_name=short_name)

        validation_logger = LoggerConfigurator.configure_logger(
            f"validate:{short_name}", prefix=f"[validate:{short_name}]"
        )
        validation_client = AirweaveHttpClient(
            wrapped_client=httpx.AsyncClient(),
            org_id=_UUID(int=0),
            source_short_name=short_name,
            rate_limiter=None,
            source_connection_id=None,
            feature_flag_enabled=False,
            logger=validation_logger,
        )

        typed_config = self._build_typed_config(entry, config or {})

        try:
            source = await source_class.create(
                auth=auth,
                logger=validation_logger,
                http_client=validation_client,
                config=typed_config,
            )
            await source.validate()
        finally:
            await validation_client.aclose()

    # ------------------------------------------------------------------
    # Private: data loading
    # ------------------------------------------------------------------

    async def _load_source_connection_data(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
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
                auth_provider_instance=None,
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

        return AuthConfig(
            credentials=auth_result.credentials,
            auth_provider_instance=auth_provider_instance,
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

        decrypted = await self._credential_service.get(
            db, source_connection_data.integration_credential_id, ctx
        )

        if source_connection_data.auth_config_class:
            processed = await self._handle_auth_config_credentials(
                db=db,
                source_connection_data=source_connection_data,
                decrypted_credential=decrypted.raw,
                ctx=ctx,
                connection_id=source_connection_data.connection_id,
            )
            return AuthConfig(
                credentials=processed,
                auth_provider_instance=None,
                decrypted_credential=decrypted,
            )

        return AuthConfig(
            credentials=decrypted.raw,
            auth_provider_instance=None,
            decrypted_credential=decrypted,
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

        Uses auth_provider_registry to resolve the provider class.
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

        decrypted = await self._credential_service.get(
            db, auth_provider_connection.integration_credential_id, ctx
        )
        decrypted_credentials = decrypted.raw

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

    def _normalize_credentials(
        self,
        raw_credentials: Union[dict, BaseModel, str],
        entry: SourceRegistryEntry,
        logger: Optional[ContextualLogger] = None,
    ) -> SourceCredentials:
        """Normalize raw credentials into the format expected by source.create().

        Handles three cases:
        1. OAuth sources without auth_config_class: Extract just the access_token string
        2. Sources with auth_config_class and dict credentials: Convert to auth config object
        3. Other sources: Pass through as-is

        Used by both the full create() path and the lightweight validate() path.
        """
        if isinstance(raw_credentials, str):
            return raw_credentials

        creds_dict = self._to_creds_dict(raw_credentials, entry.short_name, logger)
        if creds_dict is None:
            return raw_credentials

        return self._process_creds_dict(creds_dict, raw_credentials, entry, logger)

    @staticmethod
    def _to_creds_dict(
        raw_credentials: Union[dict, BaseModel, str],
        short_name: str,
        logger: Optional[ContextualLogger],
    ) -> Optional[dict]:
        """Convert raw credentials to a dict, or None if the type is unexpected."""
        if isinstance(raw_credentials, BaseModel):
            return raw_credentials.model_dump()
        if isinstance(raw_credentials, dict):
            return raw_credentials
        if logger:
            logger.warning(
                f"Source {short_name} credentials in unexpected format: {type(raw_credentials)}"
            )
        return None

    @staticmethod
    def _process_creds_dict(
        creds_dict: dict,
        raw_credentials: Union[dict, BaseModel, str],
        entry: SourceRegistryEntry,
        logger: Optional[ContextualLogger],
    ) -> SourceCredentials:
        """Process a credentials dict according to the source registry entry."""
        auth_config_ref = entry.auth_config_ref
        short_name = entry.short_name

        if not auth_config_ref and entry.oauth_type:
            if "access_token" in creds_dict:
                if logger:
                    logger.debug(f"Extracting access_token for OAuth source {short_name}")
                return creds_dict["access_token"]
            if logger:
                logger.warning(f"OAuth source {short_name} credentials missing access_token")
            return raw_credentials

        if auth_config_ref:
            try:
                validated = auth_config_ref.model_validate(creds_dict)
                if logger:
                    logger.debug(
                        f"Converted credentials dict to {auth_config_ref.__name__} for {short_name}"
                    )
                return validated
            except Exception as e:
                if logger:
                    logger.error(f"Failed to convert credentials to auth config: {e}")
                raise

        return raw_credentials

    # ------------------------------------------------------------------
    # Private: source configuration helpers
    # ------------------------------------------------------------------

    async def _resolve_token_provider(
        self,
        source_connection_data: SourceConnectionData,
        source_credentials: SourceCredentials,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str],
        auth_config: AuthConfig,
    ) -> "SourceAuthProvider":
        """Resolve the appropriate auth provider for this source.

        Always returns a concrete SourceAuthProvider — never None.
        Non-OAuth sources get a StaticTokenProvider (string creds) or
        DirectCredentialProvider (structured creds).
        """
        from airweave.domains.sources.token_providers.credential import DirectCredentialProvider

        auth_provider_instance: Optional[BaseAuthProvider] = auth_config.auth_provider_instance
        short_name = source_connection_data.short_name

        if access_token is not None:
            return StaticTokenProvider(access_token, source_short_name=short_name)

        entry = self._source_registry.get(short_name)
        source_credentials = self._normalize_credentials(source_credentials, entry, logger)

        oauth_type = source_connection_data.oauth_type

        if not oauth_type:
            if isinstance(source_credentials, str):
                return StaticTokenProvider(source_credentials, source_short_name=short_name)
            return DirectCredentialProvider(source_credentials, source_short_name=short_name)

        try:
            if auth_provider_instance:
                return AuthProviderTokenProvider(
                    auth_provider_instance=auth_provider_instance,
                    source_short_name=short_name,
                    source_registry=self._source_registry,
                    logger=logger,
                )

            # Sources that support both OAuth and API key auth (e.g. calcom, coda)
            # may have structured credentials without access_token when using
            # API key mode — route those to DirectCredentialProvider.
            if isinstance(source_credentials, BaseModel):
                if _credentials_have_access_token(source_credentials):
                    return OAuthTokenProvider(
                        credentials=source_credentials,
                        oauth_type=oauth_type,
                        oauth2_service=self._oauth2_service,
                        source_short_name=short_name,
                        connection_id=source_connection_data.connection_id,
                        ctx=ctx,
                        logger=logger,
                        config_fields=source_connection_data.config_fields,
                    )
                return DirectCredentialProvider(source_credentials, source_short_name=short_name)

            # For OAuth sources without auth_config_class, normalization strips
            # the dict down to just the access_token string. Use the full
            # DecryptedCredential.raw so OAuthTokenProvider retains refresh_token.
            oauth_creds = (
                auth_config.decrypted_credential.raw
                if auth_config.decrypted_credential
                else source_credentials
            )
            return OAuthTokenProvider(
                credentials=oauth_creds,
                oauth_type=oauth_type,
                oauth2_service=self._oauth2_service,
                source_short_name=short_name,
                connection_id=source_connection_data.connection_id,
                ctx=ctx,
                logger=logger,
                config_fields=source_connection_data.config_fields,
            )

        except Exception as e:
            raise SourceCreationError(short_name, f"token provider setup failed: {e}") from e

    # ------------------------------------------------------------------
    # Private: rate limiting wrapper
    # ------------------------------------------------------------------

    def _build_http_client(
        self,
        source_short_name: str,
        source_connection_id: UUID,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> AirweaveHttpClient:
        """Build an AirweaveHttpClient with rate limiting for this source."""
        feature_enabled = ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING)

        client = AirweaveHttpClient(
            wrapped_client=httpx.AsyncClient(),
            org_id=ctx.organization.id,
            source_short_name=source_short_name,
            rate_limiter=self._rate_limiter,
            source_connection_id=source_connection_id,
            feature_flag_enabled=feature_enabled,
            logger=logger,
        )
        logger.debug(
            f"AirweaveHttpClient built for {source_short_name} "
            f"(feature_flag_enabled={feature_enabled})"
        )
        return client

    def _build_typed_config(
        self,
        entry: SourceRegistryEntry,
        config_fields: Dict[str, Any],
    ) -> BaseModel:
        """Parse raw config_fields dict into the source's typed config class."""
        from airweave.platform.configs.config import SourceConfig

        config_class = entry.config_ref or SourceConfig
        return config_class.model_validate(config_fields or {})

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


def _credentials_have_access_token(creds: object) -> bool:
    """Check whether credentials contain a usable access_token field.

    TODO: Remove this once we have proper named integration credentials.
    """
    if isinstance(creds, dict):
        return bool(creds.get("access_token"))
    if hasattr(creds, "access_token"):
        return bool(getattr(creds, "access_token", None))
    return False
