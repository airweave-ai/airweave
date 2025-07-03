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
from airweave.core.logging import LoggerConfigurator, logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.auth.token_provider import TokenProvider
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
        # Create a contextualized logger with sync job metadata first
        logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(auth_context.organization_id),
            },
        )

        # Fetch white label if set in sync
        white_label = None
        if source_connection.white_label_id:
            white_label = await crud.white_label.get(
                db, id=source_connection.white_label_id, auth_context=auth_context
            )

        source = await cls._create_source_instance(
            db=db,
            sync=sync,
            auth_context=auth_context,
            white_label=white_label,
            access_token=access_token,
            logger=logger,  # Pass the contextual logger
        )
        embedding_model = cls._get_embedding_model(sync=sync)
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
        """Create and configure the source instance with token provider for OAuth sources."""
        # Get source connection and config
        source_connection, config_fields, source_model = await cls._get_source_config(
            db, sync, auth_context
        )
        source_class = resource_locator.get_source(source_model)

        # Handle direct access token case
        if access_token:
            return await cls._create_source_with_token(
                source_class, access_token, config_fields, logger
            )

        # Handle stored credentials case
        return await cls._create_source_with_credentials(
            db,
            source_connection,
            source_model,
            source_class,
            config_fields,
            auth_context,
            white_label,
            logger,
        )

    @classmethod
    async def _get_source_config(
        cls, db: AsyncSession, sync: schemas.Sync, auth_context: AuthContext
    ) -> tuple[schemas.Connection, dict, schemas.Source]:
        """Get source connection configuration and model."""
        # Retrieve source connection and model
        source_connection = await crud.connection.get(db, sync.source_connection_id, auth_context)
        if not source_connection:
            raise NotFoundException("Source connection not found")

        # Get the source_connection record to access config_fields using sync_id
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, auth_context=auth_context
        )
        if not source_connection_obj:
            raise NotFoundException("Source connection record not found")

        config_fields = source_connection_obj.config_fields or {}
        source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection.short_name}")

        return source_connection, config_fields, source_model

    @classmethod
    async def _create_source_with_token(
        cls, source_class, access_token: str, config_fields: dict, logger
    ) -> BaseSource:
        """Create source instance with direct access token."""
        logger.info("Creating source instance with a direct access token.")
        source = await source_class.create(access_token, config=config_fields)
        if logger and hasattr(source, "set_logger"):
            source.set_logger(logger)
        return source

    @classmethod
    async def _create_source_with_credentials(
        cls,
        db: AsyncSession,
        source_connection: schemas.Connection,
        source_model: schemas.Source,
        source_class,
        config_fields: dict,
        auth_context: AuthContext,
        white_label: Optional[schemas.WhiteLabel],
        logger,
    ) -> BaseSource:
        """Create source instance with stored credentials and optional token provider."""
        if not source_connection.integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await cls._get_integration_credential(db, source_connection, auth_context)
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        # Create token provider if needed
        token_provider = await cls._create_token_provider_if_needed(
            source_model, auth_context, source_connection, decrypted_credential, white_label, logger
        )

        # Get source credentials
        source_credentials = await cls._get_source_credentials(
            token_provider, source_model, decrypted_credential
        )

        # Create and configure source instance
        source = await source_class.create(source_credentials, config=config_fields)
        logger.info(f"Created {source_model.short_name} source instance.")

        # Inject token provider and logger
        if token_provider and hasattr(source, "set_token_provider"):
            source.set_token_provider(token_provider)
            logger.info(f"Injected TokenProvider into {source_model.short_name} source.")

        if logger and hasattr(source, "set_logger"):
            source.set_logger(logger)

        return source

    @classmethod
    async def _create_token_provider_if_needed(
        cls,
        source_model: schemas.Source,
        auth_context: AuthContext,
        source_connection: schemas.Connection,
        decrypted_credential: dict,
        white_label: Optional[schemas.WhiteLabel],
        logger,
    ) -> Optional[TokenProvider]:
        """Create token provider if the source requires OAuth refresh."""
        if source_model.auth_type not in (
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ):
            return None

        logger.info(f"Creating TokenProvider for {source_model.short_name}.")
        return TokenProvider(
            integration_short_name=source_model.short_name,
            auth_context=auth_context,
            connection_id=source_connection.id,
            decrypted_credential=decrypted_credential,
            white_label=white_label,
        )

    @classmethod
    async def _get_source_credentials(
        cls,
        token_provider: Optional[TokenProvider],
        source_model: schemas.Source,
        decrypted_credential: dict,
    ):
        """Get appropriate credentials for source creation."""
        if token_provider:
            # Let the provider get the initial valid token
            return await token_provider.get_valid_token()
        elif source_model.auth_config_class:
            # For non-provider auth, use existing logic
            auth_config = resource_locator.get_auth_config(source_model.auth_config_class)
            return auth_config.model_validate(decrypted_credential)
        else:
            return decrypted_credential

    @classmethod
    async def _get_integration_credential(
        cls,
        db: AsyncSession,
        source_connection: schemas.Connection,
        auth_context: AuthContext,
    ) -> schemas.IntegrationCredential:
        """Get integration credential."""
        credential = await crud.integration_credential.get(
            db, source_connection.integration_credential_id, auth_context
        )
        if not credential:
            raise NotFoundException("Source integration credential not found")
        return credential

    @classmethod
    def _get_embedding_model(cls, sync: schemas.Sync) -> BaseEmbeddingModel:
        """Get embedding model instance.

        If OpenAI API key is available, it will use OpenAI embeddings instead of local.

        Args:
            sync (schemas.Sync): The sync configuration

        Returns:
            BaseEmbeddingModel: The embedding model to use
        """
        # Use OpenAI if API key is available
        from airweave.core.logging import logger

        if settings.OPENAI_API_KEY:
            logger.info(f"Using OpenAI embedding model (text-embedding-3-small) for sync {sync.id}")
            return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)

        # Otherwise use the local model
        logger.info(f"Using local embedding model (MiniLM-L6-v2) for sync {sync.id}")
        return LocalText2Vec()

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
