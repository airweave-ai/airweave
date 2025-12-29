"""Source builder - creates and configures source instances.

This is an internal implementation detail of the factory module.
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.utils.source_factory_utils import (
    get_auth_configuration,
    process_credentials_for_source,
)


class SourceBuilder:
    """Builder for creating and configuring source instances.

    Handles:
    - Loading source connection data
    - Authentication (credentials, OAuth, auth providers)
    - Token manager setup for OAuth refresh
    - File downloader setup for file-based sources
    - HTTP client wrapping for rate limiting
    """

    def __init__(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        logger: ContextualLogger,
    ):
        """Initialize the source builder."""
        self.db = db
        self.ctx = ctx
        self.logger = logger

    async def build(
        self,
        sync: schemas.Sync,
        access_token: Optional[str] = None,
        sync_job: Optional[schemas.SyncJob] = None,
    ) -> tuple[BaseSource, dict]:
        """Build a fully configured source instance.

        Returns:
            Tuple of (source instance, source connection data dict)
        """
        # 1. Load source connection data
        connection_data = await self._get_connection_data(sync)

        # 2. Get auth configuration
        auth_config = await get_auth_configuration(
            db=self.db,
            source_connection_data=connection_data,
            ctx=self.ctx,
            logger=self.logger,
            access_token=access_token,
        )

        # 3. Process credentials for source
        source_credentials = await process_credentials_for_source(
            raw_credentials=auth_config["credentials"],
            source_connection_data=connection_data,
            logger=self.logger,
        )

        # 4. Create source instance
        source = await connection_data["source_class"].create(
            source_credentials, config=connection_data["config_fields"]
        )

        # 5. Configure source
        await self._configure_source(
            source=source,
            connection_data=connection_data,
            auth_config=auth_config,
            access_token=access_token,
            sync_job=sync_job,
        )

        return source, connection_data

    async def _get_connection_data(self, sync: schemas.Sync) -> dict:
        """Load source connection and related data."""
        # 1. Get SourceConnection first
        source_connection = await crud.source_connection.get_by_sync_id(
            self.db, sync_id=sync.id, ctx=self.ctx
        )
        if not source_connection:
            raise NotFoundException(
                f"Source connection record not found for sync {sync.id}. "
                f"This typically occurs when a source connection is deleted while a "
                f"scheduled workflow is queued."
            )

        # 2. Get Connection for integration_credential_id
        connection = await crud.connection.get(self.db, source_connection.connection_id, self.ctx)
        if not connection:
            raise NotFoundException("Connection not found")

        # 3. Get Source model
        source_model = await crud.source.get_by_short_name(self.db, source_connection.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection.short_name}")

        # 4. Pre-fetch to avoid lazy loading
        config_fields = source_connection.config_fields or {}
        auth_config_class = source_model.auth_config_class
        source_connection_id = UUID(str(source_connection.id))
        short_name = str(source_connection.short_name)
        connection_id = UUID(str(connection.id))

        readable_auth_provider_id = getattr(source_connection, "readable_auth_provider_id", None)

        if not readable_auth_provider_id and not connection.integration_credential_id:
            raise NotFoundException(f"Connection {connection_id} has no integration credential")

        integration_credential_id = (
            UUID(str(connection.integration_credential_id))
            if connection.integration_credential_id
            else None
        )

        source_class = resource_locator.get_source(source_model)
        oauth_type = str(source_model.oauth_type) if source_model.oauth_type else None

        return {
            "source_connection_obj": source_connection,
            "connection": connection,
            "source_model": source_model,
            "source_class": source_class,
            "config_fields": config_fields,
            "short_name": short_name,
            "source_connection_id": source_connection_id,
            "auth_config_class": auth_config_class,
            "connection_id": connection_id,
            "integration_credential_id": integration_credential_id,
            "oauth_type": oauth_type,
            "readable_auth_provider_id": readable_auth_provider_id,
            "auth_provider_config": getattr(source_connection, "auth_provider_config", None),
        }

    async def _configure_source(
        self,
        source: BaseSource,
        connection_data: dict,
        auth_config: dict,
        access_token: Optional[str],
        sync_job: Optional[schemas.SyncJob],
    ) -> None:
        """Configure source with logger, clients, token manager, and file downloader."""
        short_name = connection_data["short_name"]

        if hasattr(source, "set_logger"):
            source.set_logger(self.logger)

        if auth_config.get("http_client_factory"):
            source.set_http_client_factory(auth_config["http_client_factory"])

        # Set sync identifiers
        try:
            source_connection_id = connection_data.get("source_connection_id")
            if hasattr(source, "set_sync_identifiers") and source_connection_id:
                source.set_sync_identifiers(
                    organization_id=str(self.ctx.organization.id),
                    source_connection_id=str(source_connection_id),
                )
        except Exception:
            pass

        # Setup token manager
        await self._setup_token_manager(
            source=source,
            connection_data=connection_data,
            credentials=auth_config["credentials"],
            auth_config=auth_config,
            access_token=access_token,
        )

        # Setup file downloader
        self._setup_file_downloader(source, sync_job)

        # Wrap HTTP client
        from airweave.platform.utils.source_factory_utils import wrap_source_with_airweave_client

        wrap_source_with_airweave_client(
            source=source,
            source_short_name=short_name,
            source_connection_id=connection_data["source_connection_id"],
            ctx=self.ctx,
            logger=self.logger,
        )

    async def _setup_token_manager(
        self,
        source: BaseSource,
        connection_data: dict,
        credentials: Any,
        auth_config: dict,
        access_token: Optional[str],
    ) -> None:
        """Set up token manager for OAuth sources."""
        from airweave.platform.auth_providers.auth_result import AuthProviderMode
        from airweave.schemas.source_connection import OAuthType

        short_name = connection_data["short_name"]
        oauth_type = connection_data.get("oauth_type")
        auth_mode = auth_config.get("auth_mode")
        auth_provider_instance = auth_config.get("auth_provider_instance")

        if access_token is not None:
            self.logger.debug(f"⏭️ Skipping token manager for {short_name} - direct token injection")
            return

        if auth_mode == AuthProviderMode.PROXY:
            self.logger.info(
                f"⏭️ Skipping token manager for {short_name} - "
                f"proxy mode (PipedreamProxyClient manages tokens internally)"
            )
            return

        if oauth_type not in (OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH):
            self.logger.debug(
                f"⏭️ Skipping token manager for {short_name} - "
                f"oauth_type={oauth_type} does not support refresh"
            )
            return

        try:
            minimal_connection = type(
                "SourceConnection",
                (),
                {
                    "id": connection_data["connection_id"],
                    "integration_credential_id": connection_data["integration_credential_id"],
                    "config_fields": connection_data.get("config_fields"),
                },
            )()

            token_manager = TokenManager(
                db=self.db,
                source_short_name=short_name,
                source_connection=minimal_connection,
                ctx=self.ctx,
                initial_credentials=credentials,
                is_direct_injection=False,
                logger_instance=self.logger,
                auth_provider_instance=auth_provider_instance,
            )
            source.set_token_manager(token_manager)

            self.logger.info(
                f"Token manager initialized for OAuth source {short_name} "
                f"(auth_provider: {'Yes' if auth_provider_instance else 'None'})"
            )
        except Exception as e:
            self.logger.error(f"Failed to setup token manager for {short_name}: {e}")

    def _setup_file_downloader(
        self,
        source: BaseSource,
        sync_job: Optional[schemas.SyncJob],
    ) -> None:
        """Setup file downloader for file-based sources."""
        from airweave.platform.downloader import FileDownloadService

        if not sync_job or not hasattr(sync_job, "id"):
            raise ValueError(
                "sync_job is required for file downloader initialization. "
                "This method should only be called from create_orchestrator()."
            )

        file_downloader = FileDownloadService(sync_job_id=str(sync_job.id))
        source.set_file_downloader(file_downloader)
        self.logger.debug(
            f"File downloader configured for {source.__class__.__name__} "
            f"(sync_job_id: {sync_job.id})"
        )
