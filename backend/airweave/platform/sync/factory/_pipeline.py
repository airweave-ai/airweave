"""Pipeline builder - creates EntityPipeline with handlers.

This is an internal implementation detail of the factory module.
"""

from airweave.platform.destinations._base import BaseDestination, ProcessingRequirement
from airweave.platform.sync.actions import ActionDispatcher, ActionResolver
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.handlers import (
    PostgresMetadataHandler,
    RawDataHandler,
    VectorDBHandler,
)
from airweave.platform.sync.handlers.base import ActionHandler
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker


class PipelineBuilder:
    """Builder for creating EntityPipeline with appropriate handlers.

    Handlers are created based on destination processing requirements:
    - VectorDBHandler: For destinations needing chunking/embedding
    - RawDataHandler: For ARF storage (skipped in replay mode)
    - PostgresMetadataHandler: For entity metadata (always runs last)
    """

    @staticmethod
    def build(
        sync_context: SyncContext,
        include_raw_data_handler: bool = True,
    ) -> EntityPipeline:
        """Build an EntityPipeline for a sync context."""
        action_resolver = ActionResolver(entity_map=sync_context.entity_map)

        handlers = PipelineBuilder._create_handlers(
            destinations=sync_context.destinations,
            logger=sync_context.logger,
            include_raw_data_handler=include_raw_data_handler,
        )

        action_dispatcher = ActionDispatcher(handlers=handlers)

        return EntityPipeline(
            entity_tracker=sync_context.entity_tracker,
            action_resolver=action_resolver,
            action_dispatcher=action_dispatcher,
        )

    @staticmethod
    def build_for_replay(
        entity_tracker: EntityTracker,
        entity_map: dict,
        destinations: list[BaseDestination],
    ) -> EntityPipeline:
        """Build a pipeline for replay operations.

        Replay pipelines skip RawDataHandler (we're reading from ARF, not writing).
        """
        action_resolver = ActionResolver(entity_map=entity_map)

        handlers = PipelineBuilder._create_handlers(
            destinations=destinations,
            logger=None,
            include_raw_data_handler=False,
        )

        action_dispatcher = ActionDispatcher(handlers=handlers)

        return EntityPipeline(
            entity_tracker=entity_tracker,
            action_resolver=action_resolver,
            action_dispatcher=action_dispatcher,
        )

    @staticmethod
    def _create_handlers(
        destinations: list[BaseDestination],
        logger,
        include_raw_data_handler: bool = True,
    ) -> list[ActionHandler]:
        """Create handlers based on destination requirements."""
        handlers: list[ActionHandler] = []

        vector_db_destinations: list[BaseDestination] = []
        self_processing_destinations: list[BaseDestination] = []

        for dest in destinations:
            requirement = dest.processing_requirement
            if requirement == ProcessingRequirement.CHUNKS_AND_EMBEDDINGS:
                vector_db_destinations.append(dest)
            elif requirement == ProcessingRequirement.RAW_ENTITIES:
                self_processing_destinations.append(dest)
            else:
                if logger:
                    logger.warning(
                        f"Unknown processing requirement {requirement} for "
                        f"{dest.__class__.__name__}, defaulting to CHUNKS_AND_EMBEDDINGS"
                    )
                vector_db_destinations.append(dest)

        if vector_db_destinations:
            vector_handler = VectorDBHandler(destinations=vector_db_destinations)
            handlers.append(vector_handler)
            if logger:
                logger.info(
                    f"Created VectorDBHandler for {len(vector_db_destinations)} destination(s): "
                    f"{[d.__class__.__name__ for d in vector_db_destinations]}"
                )

        if include_raw_data_handler:
            handlers.append(RawDataHandler())

        handlers.append(PostgresMetadataHandler())

        if not handlers and logger:
            logger.warning("No destination handlers created - sync has no valid destinations")

        return handlers
