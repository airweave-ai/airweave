"""Module for sync factory that creates context and orchestrator instances."""

import importlib
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger, LoggerConfigurator, logger
from airweave.platform.auth.services import oauth2_service
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.entities._base import BaseEntity
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pubsub import SyncProgress
from airweave.platform.sync.router import SyncDAGRouter
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.sync.worker_pool import AsyncWorkerPool
from airweave.schemas.auth import AuthContext


class SyncFactory:
    """Factory for sync orchestrator."""

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        auth_context: AuthContext,
        access_token: Optional[str] = None,
        max_workers: int = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run.

        This method creates all necessary components for a sync run, including the
        context and a dedicated orchestrator instance for concurrent execution.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            dag: The DAG for the sync
            collection: The collection to sync to
            source_connection: The source connection
            auth_context: The authentication context
            access_token: Optional token to use instead of stored credentials
            max_workers: Maximum number of concurrent workers (default: from settings)

        Returns:
            A dedicated SyncOrchestrator instance
        """
        # Use configured value if max_workers not specified
        if max_workers is None:
            max_workers = settings.SYNC_MAX_WORKERS
            logger.info(f"Using configured max_workers: {max_workers}")

        # Track initialization timing
        init_start = time.time()

        # Create sync context
        logger.info("Creating sync context...")
        context_start = time.time()
        sync_context = await cls._create_sync_context(
            db=db,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            auth_context=auth_context,
            access_token=access_token,
        )
        logger.info(f"Sync context created in {time.time() - context_start:.2f}s")

        # CRITICAL FIX: Initialize transformer cache to eliminate 1.5s database lookups
        cache_start = time.time()
        await sync_context.router.initialize_transformer_cache(db)
        logger.info(f"Transformer cache initialized in {time.time() - cache_start:.2f}s")

        # Create entity processor
        entity_processor = EntityProcessor()

        # Create worker pool
        pool_start = time.time()
        worker_pool = AsyncWorkerPool(max_workers=max_workers)
        logger.info(f"Worker pool created in {time.time() - pool_start:.2f}s")

        # Create dedicated orchestrator instance
        orchestrator = SyncOrchestrator(
            entity_processor=entity_processor,
            worker_pool=worker_pool,
            sync_context=sync_context,
        )

        # Initialize entity tracking
        entity_processor.initialize_tracking(sync_context)

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")

        return orchestrator

    @classmethod
    async def _create_sync_context(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        auth_context: AuthContext,
        access_token: Optional[str] = None,
    ) -> SyncContext:
        """Create a sync context.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            dag: The DAG for the sync
            collection: The collection to sync to
            source_connection: The source connection
            auth_context: The authentication context
            access_token: Optional token to use instead of stored credentials

        Returns:
            SyncContext object with all required components
        """
        # Get source connection data first to access white_label_id safely
        source_connection_data = await cls._get_source_connection_data(db, sync, auth_context)

        # Create a contextualized logger with all job metadata
        logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(auth_context.organization_id),
                "source_connection_id": str(source_connection_data["connection_id"]),
            },
        )

        # Fetch white label if set in sync using pre-fetched white_label_id
        white_label = None
        if source_connection_data["white_label_id"]:
            white_label = await crud.white_label.get(
                db, id=source_connection_data["white_label_id"], auth_context=auth_context
            )

        source = await cls._create_source_instance_with_data(
            db=db,
            source_connection_data=source_connection_data,
            auth_context=auth_context,
            white_label=white_label,
            access_token=access_token,
            logger=logger,  # Pass the contextual logger
        )
        embedding_model = cls._get_embedding_model(logger=logger)
        destinations = await cls._create_destination_instances(
            db=db,
            sync=sync,
            collection=collection,
            auth_context=auth_context,
        )
        transformers = await cls._get_transformer_callables(db=db, sync=sync)
        entity_map = await cls._get_entity_definition_map(db=db)

        progress = SyncProgress(sync_job.id)
        router = SyncDAGRouter(dag, entity_map)

        return SyncContext(
            source=source,
            destinations=destinations,
            embedding_model=embedding_model,
            transformers=transformers,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            progress=progress,
            router=router,
            entity_map=entity_map,
            auth_context=auth_context,
            logger=logger,
            white_label=white_label,
        )

    @classmethod
    async def _create_source_instance(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel] = None,
        access_token: Optional[str] = None,
        logger=None,
    ) -> BaseSource:
        """Create and configure the source instance based on authentication type."""
        # Get source connection and model
        source_connection_data = await cls._get_source_connection_data(db, sync, auth_context)

        return await cls._create_source_instance_with_data(
            db, source_connection_data, auth_context, white_label, access_token, logger
        )

    @classmethod
    async def _create_source_instance_with_data(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel] = None,
        access_token: Optional[str] = None,
        logger=None,
    ) -> BaseSource:
        """Create and configure the source instance using pre-fetched connection data."""
        # Handle credentials (either direct token or from database)
        final_access_token, source_credentials = await cls._handle_source_credentials(
            db, source_connection_data, auth_context, white_label, access_token
        )

        # Create the source instance
        source = await source_connection_data["source_class"].create(
            source_credentials, config=source_connection_data["config_fields"]
        )

        # Configure source with logger and token manager
        await cls._configure_source_instance(
            db,
            source,
            source_connection_data,
            auth_context,
            white_label,
            final_access_token,
            logger,
        )

        return source

    @classmethod
    async def _get_source_connection_data(
        cls, db: AsyncSession, sync: schemas.Sync, auth_context: AuthContext
    ) -> dict:
        """Get source connection and model data."""
        # 1. Get SourceConnection first (has most of our data)
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, auth_context=auth_context
        )
        if not source_connection_obj:
            raise NotFoundException("Source connection record not found")

        # 2. Get Connection only to access integration_credential_id
        connection = await crud.connection.get(
            db, source_connection_obj.connection_id, auth_context
        )
        if not connection:
            raise NotFoundException("Connection not found")

        # 3. Get Source model using short_name from SourceConnection
        source_model = await crud.source.get_by_short_name(db, source_connection_obj.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection_obj.short_name}")

        # Get all fields from the RIGHT places:
        config_fields = source_connection_obj.config_fields or {}  # From SourceConnection

        # Pre-fetch to avoid lazy loading - convert to pure Python types
        auth_type = source_model.auth_type
        auth_config_class = source_model.auth_config_class
        # Convert SQLAlchemy values to clean Python types to avoid lazy loading
        short_name = str(source_connection_obj.short_name)  # From SourceConnection
        white_label_id = (
            UUID(str(source_connection_obj.white_label_id))
            if source_connection_obj.white_label_id
            else None
        )
        connection_id = UUID(str(connection.id))
        # integration_credential_id must be set for sync to work
        if not connection.integration_credential_id:
            raise NotFoundException(f"Connection {connection_id} has no integration credential")
        integration_credential_id = UUID(str(connection.integration_credential_id))

        source_class = resource_locator.get_source(source_model)

        return {
            "source_connection_obj": source_connection_obj,  # The main entity
            "connection": connection,  # Just for credential access
            "source_model": source_model,
            "source_class": source_class,
            "config_fields": config_fields,  # From SourceConnection
            "white_label_id": white_label_id,  # From SourceConnection
            "short_name": short_name,  # From SourceConnection
            "auth_type": auth_type,
            "auth_config_class": auth_config_class,
            "connection_id": connection_id,
            "integration_credential_id": integration_credential_id,  # From Connection
        }

    @classmethod
    async def _handle_source_credentials(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel],
        access_token: Optional[str],
    ) -> tuple[Optional[str], any]:
        """Handle source credentials, either from direct token or database."""
        # If access token is provided, use it directly
        if access_token:
            return access_token, access_token

        # Otherwise get credentials from database
        integration_credential_id = source_connection_data["integration_credential_id"]
        if not integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await cls._get_integration_credential(
            db, integration_credential_id, auth_context
        )
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        # Handle auth configuration if required
        # Use pre-fetched auth_config_class to avoid SQLAlchemy lazy loading issues
        auth_config_class = source_connection_data["auth_config_class"]
        if auth_config_class:
            return await cls._handle_auth_config_credentials(
                db,
                source_connection_data,
                decrypted_credential,
                auth_context,
                source_connection_data["connection_id"],
                white_label,
            )

        # Handle direct credentials
        final_access_token = None
        if isinstance(decrypted_credential, dict) and "access_token" in decrypted_credential:
            final_access_token = decrypted_credential["access_token"]

        return final_access_token, decrypted_credential

    @classmethod
    async def _handle_auth_config_credentials(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        decrypted_credential: dict,
        auth_context: AuthContext,
        connection_id: UUID,
        white_label: Optional[schemas.WhiteLabel],
    ) -> tuple[Optional[str], any]:
        """Handle credentials that require auth configuration."""
        # Use pre-fetched auth_config_class to avoid SQLAlchemy lazy loading issues
        auth_config_class = source_connection_data["auth_config_class"]
        short_name = source_connection_data["short_name"]

        auth_config = resource_locator.get_auth_config(auth_config_class)
        source_credentials = auth_config.model_validate(decrypted_credential)

        # If the source_credential has a refresh token, exchange it for an access token
        if hasattr(source_credentials, "refresh_token") and source_credentials.refresh_token:
            oauth2_response = await oauth2_service.refresh_access_token(
                db,
                short_name,
                auth_context,
                connection_id,
                decrypted_credential,
                white_label,
            )
            # Just use the access token
            return oauth2_response.access_token, oauth2_response.access_token

        return None, source_credentials

    @classmethod
    async def _configure_source_instance(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel],
        final_access_token: Optional[str],
        logger: ContextualLogger,
    ) -> None:
        """Configure source instance with logger and token manager."""
        # Set contextual logger
        source.set_logger(logger)

        # Create and set token manager for OAuth sources
        if hasattr(source, "set_token_manager") and final_access_token:
            await cls._setup_token_manager(
                db,
                source,
                source_connection_data,
                auth_context,
                white_label,
                final_access_token,
                logger,
            )

    @classmethod
    async def _setup_token_manager(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel],
        final_access_token: str,
        logger,
    ) -> None:
        """Set up token manager for OAuth sources."""
        auth_type = source_connection_data["auth_type"]
        short_name = source_connection_data["short_name"]

        # Only create token manager for OAuth sources
        from airweave.platform.auth.schemas import AuthType

        oauth_types = {
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        }

        if auth_type in oauth_types:
            # Create a minimal connection object with only the fields needed by TokenManager
            # Use pre-fetched IDs to avoid SQLAlchemy lazy loading issues
            minimal_source_connection = type(
                "SourceConnection",
                (),
                {
                    "id": source_connection_data["connection_id"],
                    "integration_credential_id": source_connection_data[
                        "integration_credential_id"
                    ],
                },
            )()

            token_manager = TokenManager(
                db=db,
                source_short_name=short_name,
                source_connection=minimal_source_connection,
                auth_context=auth_context,
                auth_type=auth_type,
                initial_token=final_access_token,
                white_label=white_label,
                is_direct_injection=final_access_token is not None,
                logger_instance=logger,
            )
            source.set_token_manager(token_manager)

            if logger:
                logger.info(
                    f"Token manager initialized for {short_name} "
                    f"(auth_type: {auth_type}, "
                    f"is_direct_injection: {final_access_token is not None})"
                )

    @classmethod
    async def _get_integration_credential(
        cls,
        db: AsyncSession,
        integration_credential_id: UUID,
        auth_context: AuthContext,
    ) -> schemas.IntegrationCredential:
        """Get integration credential."""
        credential = await crud.integration_credential.get(
            db, integration_credential_id, auth_context
        )
        if not credential:
            raise NotFoundException("Source integration credential not found")
        return credential

    @classmethod
    def _get_embedding_model(cls, logger: ContextualLogger) -> BaseEmbeddingModel:
        """Get embedding model instance.

        If OpenAI API key is available, it will use OpenAI embeddings instead of local.

        Args:
            logger (ContextualLogger): The logger to use

        Returns:
            BaseEmbeddingModel: The embedding model to use
        """
        if settings.OPENAI_API_KEY:
            return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)

        return LocalText2Vec(logger=logger)

    @classmethod
    async def _create_destination_instances(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        auth_context: AuthContext,
    ) -> list[BaseDestination]:
        """Create destination instances.

        Args:
        -----
            db (AsyncSession): The database session
            sync (schemas.Sync): The sync object
            collection (schemas.Collection): The collection object
            auth_context (AuthContext): The authentication context

        Returns:
        --------
            list[BaseDestination]: A list of destination instances
        """
        destination_connection_id = sync.destination_connection_ids[0]

        destination_connection = await crud.connection.get(
            db, destination_connection_id, auth_context
        )
        if not destination_connection:
            raise NotFoundException(
                (
                    f"Destination connection not found for organization "
                    f"{auth_context.organization_id}"
                    f" and connection id {destination_connection_id}"
                )
            )
        destination_model = await crud.destination.get_by_short_name(
            db, destination_connection.short_name
        )
        destination_schema = schemas.Destination.model_validate(destination_model)
        if not destination_model:
            raise NotFoundException(
                f"Destination not found for connection {destination_connection.short_name}"
            )

        destination_class = resource_locator.get_destination(destination_schema)
        destination = await destination_class.create(collection_id=collection.id)

        return [destination]

    @classmethod
    async def _get_transformer_callables(
        cls, db: AsyncSession, sync: schemas.Sync
    ) -> dict[str, callable]:
        """Get transformers instance."""
        transformers = {}

        transformer_functions = await crud.transformer.get_all(db)
        for transformer in transformer_functions:
            transformers[transformer.method_name] = resource_locator.get_transformer(transformer)
        return transformers

    @classmethod
    async def _get_entity_definition_map(cls, db: AsyncSession) -> dict[type[BaseEntity], UUID]:
        """Get entity definition map.

        Map entity class to entity definition id.

        Example key-value pair:
            <class 'airweave.platform.entities.trello.TrelloBoard'>: entity_definition_id
        """
        entity_definitions = await crud.entity_definition.get_all(db)

        entity_definition_map = {}
        for entity_definition in entity_definitions:
            full_module_name = f"airweave.platform.entities.{entity_definition.module_name}"
            module = importlib.import_module(full_module_name)
            entity_class = getattr(module, entity_definition.class_name)
            entity_definition_map[entity_class] = entity_definition.id

        return entity_definition_map
