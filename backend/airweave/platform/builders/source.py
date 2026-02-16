"""Source context builder for sync operations.

Handles all source creation complexity:
- Source connection data loading
- Credentials and OAuth configuration
- Token manager setup
- File downloader setup
- HTTP client wrapping (rate limiting)
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.contexts.infra import InfraContext
from airweave.platform.contexts.source import SourceContext
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.config import SyncConfig
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.utils.source_factory_utils import (
    get_auth_configuration,
    process_credentials_for_source,
)


class SourceContextBuilder:
    """Builds source context with all required configuration."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        infra: InfraContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SourceContext:
        """Build complete source context.

        Args:
            db: Database session
            sync: Sync configuration
            sync_job: The sync job (needed for file downloader)
            infra: Infrastructure context (provides ctx and logger)
            access_token: Optional direct token (skips credential loading)
            force_full_sync: If True, skip cursor loading
            execution_config: Optional execution config

        Returns:
            SourceContext with configured source and cursor.
        """
        ctx = infra.ctx
        logger = infra.logger

        # Check for ARF replay mode - override source with ArfReplaySource
        if execution_config and execution_config.behavior.replay_from_arf:
            return await cls._build_arf_replay_context(
                db=db,
                sync=sync,
                infra=infra,
                execution_config=execution_config,
            )

        # 1. Load source connection data
        source_connection_data = await cls._get_source_connection_data(db, sync, ctx)

        # 2. Create source instance
        source = await cls._create_source_instance(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
            sync_job=sync_job,
        )

        # 3. Create cursor
        cursor = await cls._create_cursor(
            db=db,
            sync=sync,
            source_class=source_connection_data["source_class"],
            ctx=ctx,
            logger=logger,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        # 4. Set cursor on source
        source.set_cursor(cursor)

        return SourceContext(source=source, cursor=cursor)

    @classmethod
    async def _build_arf_replay_context(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        infra: InfraContext,
        execution_config: SyncConfig,
    ) -> SourceContext:
        """Build source context for ARF replay mode.

        Creates an ArfReplaySource instead of the normal source,
        reading entities from ARF storage.

        Args:
            db: Database session
            sync: Sync configuration
            infra: Infrastructure context
            execution_config: Execution config (must have replay_from_arf=True)

        Returns:
            SourceContext with ArfReplaySource
        """
        from airweave.platform.storage.replay_source import ArfReplaySource

        ctx = infra.ctx
        logger = infra.logger

        # Get original source short_name from DB
        source_connection = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        original_short_name = source_connection.short_name if source_connection else None

        logger.info(
            f"🔄 ARF Replay mode: Creating ArfReplaySource for sync {sync.id} "
            f"(masquerading as '{original_short_name}')"
        )

        # Create the ARF replay source with original source identity
        source = await ArfReplaySource.create(
            sync_id=sync.id,
            logger=logger,
            restore_files=True,
            original_short_name=original_short_name,
        )

        # Set logger on source
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        # Validate ARF data exists
        if not await source.validate():
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException(
                f"ARF data not found for sync {sync.id}. "
                f"Cannot replay - ensure ARF capture was enabled for previous syncs."
            )

        # No cursor for ARF replay (we're replaying all entities)
        cursor = SyncCursor(
            sync_id=sync.id,
            cursor_schema=None,
            cursor_data=None,
        )

        return SourceContext(source=source, cursor=cursor)

    @classmethod
    async def get_source_connection_id(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: ApiContext,
    ) -> UUID:
        """Get user-facing source connection ID for logging and scoping.

        Args:
            db: Database session
            sync: Sync configuration
            ctx: API context

        Returns:
            User-facing SourceConnection UUID (not internal Connection ID).
        """
        source_connection_data = await cls._get_source_connection_data(db, sync, ctx)
        return source_connection_data["source_connection_id"]

    # -------------------------------------------------------------------------
    # Private: Source Connection Data
    # -------------------------------------------------------------------------

    @classmethod
    async def _get_source_connection_data(
        cls, db: AsyncSession, sync: schemas.Sync, ctx: ApiContext
    ) -> dict:
        """Get source connection and model data."""
        # 1. Get SourceConnection first (has most of our data)
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        if not source_connection_obj:
            raise NotFoundException(
                f"Source connection record not found for sync {sync.id}. "
                f"This typically occurs when a source connection is deleted while a "
                f"scheduled workflow is queued. The workflow should self-destruct and "
                f"clean up orphaned schedules."
            )

        # 2. Guard: snapshot sources that completed have their short_name updated
        # to the original source (e.g., "github"). Detect this by checking if the
        # stored config validates as a SnapshotConfig.
        if source_connection_obj.short_name != "snapshot":
            from pydantic import ValidationError

            from airweave.platform.configs.config import SnapshotConfig

            try:
                SnapshotConfig(**(source_connection_obj.config_fields or {}))
                # Config is a valid SnapshotConfig but short_name is not "snapshot"
                # → this is a completed snapshot, can't re-sync
                from airweave.platform.sync.exceptions import SyncFailureError

                raise SyncFailureError(
                    f"Cannot re-sync a completed snapshot source connection "
                    f"('{source_connection_obj.name}'). Snapshot data is immutable — "
                    f"create a new snapshot source connection instead."
                )
            except ValidationError:
                pass  # Not a snapshot config, proceed normally

        # 3. Get Connection only to access integration_credential_id
        connection = await crud.connection.get(db, source_connection_obj.connection_id, ctx)
        if not connection:
            raise NotFoundException("Connection not found")

        # 4. Get Source model using short_name from SourceConnection
        source_model = await crud.source.get_by_short_name(db, source_connection_obj.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection_obj.short_name}")

        # Get all fields from the RIGHT places:
        config_fields = source_connection_obj.config_fields or {}  # From SourceConnection

        # Pre-fetch to avoid lazy loading - convert to pure Python types
        auth_config_class = source_model.auth_config_class
        # Convert SQLAlchemy values to clean Python types to avoid lazy loading
        source_connection_id = UUID(str(source_connection_obj.id))  # From SourceConnection
        short_name = str(source_connection_obj.short_name)  # From SourceConnection
        connection_id = UUID(str(connection.id))

        # Check if this connection uses an auth provider
        readable_auth_provider_id = getattr(
            source_connection_obj, "readable_auth_provider_id", None
        )

        # For auth provider connections, integration_credential_id will be None
        # For regular connections, integration_credential_id must be set
        if not readable_auth_provider_id and not connection.integration_credential_id:
            raise NotFoundException(f"Connection {connection_id} has no integration credential")

        integration_credential_id = (
            UUID(str(connection.integration_credential_id))
            if connection.integration_credential_id
            else None
        )

        source_class = resource_locator.get_source(source_model)

        # Pre-fetch oauth_type to avoid lazy loading issues
        oauth_type = str(source_model.oauth_type) if source_model.oauth_type else None

        return {
            "source_connection_obj": source_connection_obj,  # The main entity
            "connection": connection,  # Just for credential access
            "source_model": source_model,
            "source_class": source_class,
            "config_fields": config_fields,  # From SourceConnection
            "short_name": short_name,  # From SourceConnection
            "source_connection_id": source_connection_id,  # Pre-fetched to avoid lazy loading
            "auth_config_class": auth_config_class,
            "connection_id": connection_id,
            "integration_credential_id": integration_credential_id,  # From Connection
            "oauth_type": oauth_type,  # Pre-fetched to avoid lazy loading
            "readable_auth_provider_id": getattr(
                source_connection_obj, "readable_auth_provider_id", None
            ),
            "auth_provider_config": getattr(source_connection_obj, "auth_provider_config", None),
        }

    # -------------------------------------------------------------------------
    # Private: Source Instance Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_source_instance(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str] = None,
        sync_job: Optional[Any] = None,
    ) -> BaseSource:
        """Create and configure the source instance."""
        # Get auth configuration (credentials + proxy setup if needed)
        auth_config = await get_auth_configuration(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
        )

        # Process credentials for source consumption
        source_credentials = await process_credentials_for_source(
            raw_credentials=auth_config["credentials"],
            source_connection_data=source_connection_data,
            logger=logger,
        )

        # Create the source instance with processed credentials
        source = await source_connection_data["source_class"].create(
            source_credentials, config=source_connection_data["config_fields"]
        )

        # Configure source with logger
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        # Set HTTP client factory if proxy is needed
        if auth_config.get("http_client_factory"):
            source.set_http_client_factory(auth_config["http_client_factory"])

        # Pass sync identifiers to the source for scoped helpers
        try:
            organization_id = ctx.organization.id
            source_connection_id = source_connection_data.get("source_connection_id")
            if hasattr(source, "set_sync_identifiers") and source_connection_id:
                source.set_sync_identifiers(
                    organization_id=str(organization_id),
                    source_connection_id=str(source_connection_id),
                )
        except Exception:
            # Non-fatal: older sources may ignore this
            pass

        # Setup token manager for OAuth sources (if applicable)
        await cls._setup_token_manager(
            db=db,
            source=source,
            source_connection_data=source_connection_data,
            source_credentials=auth_config["credentials"],
            ctx=ctx,
            logger=logger,
            access_token=access_token,
            auth_config=auth_config,
        )

        # Setup file downloader for file-based sources
        cls._setup_file_downloader(source, sync_job, logger)

        # Wrap HTTP client with AirweaveHttpClient for rate limiting
        from airweave.platform.utils.source_factory_utils import wrap_source_with_airweave_client

        wrap_source_with_airweave_client(
            source=source,
            source_short_name=source_connection_data["short_name"],
            source_connection_id=source_connection_data["source_connection_id"],
            ctx=ctx,
            logger=logger,
        )

        return source

    @classmethod
    async def _setup_token_manager(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        source_credentials: Any,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str],
        auth_config: dict,
    ) -> None:
        """Set up token manager for OAuth sources."""
        from airweave.platform.auth_providers.auth_result import AuthProviderMode

        auth_mode = auth_config.get("auth_mode")
        auth_provider_instance: Optional[BaseAuthProvider] = auth_config.get(
            "auth_provider_instance"
        )

        # Check if we should skip TokenManager
        is_direct_token_injection = access_token is not None
        is_proxy_mode = auth_mode == AuthProviderMode.PROXY

        if is_direct_token_injection:
            logger.debug(
                f"⏭️ Skipping token manager for {source_connection_data['short_name']} - "
                f"direct token injection"
            )
            return

        if is_proxy_mode:
            logger.info(
                f"⏭️ Skipping token manager for {source_connection_data['short_name']} - "
                f"proxy mode (PipedreamProxyClient manages tokens internally)"
            )
            return

        short_name = source_connection_data["short_name"]
        oauth_type = source_connection_data.get("oauth_type")

        # Determine if we should create a token manager based on oauth_type
        should_create_token_manager = False

        if oauth_type:
            from airweave.schemas.source_connection import OAuthType

            if oauth_type in (OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH):
                should_create_token_manager = True
                logger.debug(
                    f"✅ OAuth source {short_name} with oauth_type={oauth_type} "
                    f"will use token manager for refresh"
                )
            else:
                logger.debug(
                    f"⏭️ Skipping token manager for {short_name} - "
                    f"oauth_type={oauth_type} does not support token refresh"
                )

        if should_create_token_manager:
            try:
                # Create a minimal connection object with only the fields needed by TokenManager
                minimal_source_connection = type(
                    "SourceConnection",
                    (),
                    {
                        "id": source_connection_data["connection_id"],
                        "integration_credential_id": source_connection_data[
                            "integration_credential_id"
                        ],
                        "config_fields": source_connection_data.get("config_fields"),
                    },
                )()

                token_manager = TokenManager(
                    db=db,
                    source_short_name=short_name,
                    source_connection=minimal_source_connection,
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
                logger.error(f"Failed to setup token manager for source '{short_name}': {e}")
                # Don't fail source creation if token manager setup fails

    @classmethod
    def _setup_file_downloader(
        cls, source: BaseSource, sync_job: Optional[Any], logger: ContextualLogger
    ) -> None:
        """Setup file downloader for file-based sources."""
        from airweave.platform.storage import FileService

        # Require sync_job - we're always in sync context when this is called
        if not sync_job or not hasattr(sync_job, "id"):
            raise ValueError(
                "sync_job is required for file downloader initialization. "
                "This method should only be called from create_orchestrator() "
                "where sync_job exists."
            )

        file_downloader = FileService(sync_job_id=sync_job.id)
        source.set_file_downloader(file_downloader)
        logger.debug(
            f"File downloader configured for {source.__class__.__name__} "
            f"(sync_job_id: {sync_job.id})"
        )

    # -------------------------------------------------------------------------
    # Private: Cursor Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_cursor(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        source_class: type,
        ctx: ApiContext,
        logger: ContextualLogger,
        force_full_sync: bool,
        execution_config: Optional[SyncConfig],
    ) -> SyncCursor:
        """Create sync cursor with optional data loading."""
        # Get cursor schema from source class (direct reference, no string lookup!)
        cursor_schema = None
        if hasattr(source_class, "cursor_class") and source_class.cursor_class:
            cursor_schema = source_class.cursor_class
            logger.debug(f"Source has typed cursor: {cursor_schema.__name__}")

        # Determine whether to load cursor data
        if force_full_sync:
            logger.info(
                "🔄 FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched "
                "for accurate orphaned entity cleanup. Will still track cursor for next sync."
            )
            cursor_data = None
        elif execution_config and execution_config.cursor.skip_load:
            logger.info(
                "🔄 SKIP CURSOR LOAD: Fetching all entities "
                "(execution_config.cursor.skip_load=True)"
            )
            cursor_data = None
        else:
            # Normal incremental sync - load cursor data
            cursor_data = await sync_cursor_service.get_cursor_data(db=db, sync_id=sync.id, ctx=ctx)
            if cursor_data:
                logger.info(f"📊 Incremental sync: Using cursor data with {len(cursor_data)} keys")

        return SyncCursor(
            sync_id=sync.id,
            cursor_schema=cursor_schema,
            cursor_data=cursor_data,
        )
