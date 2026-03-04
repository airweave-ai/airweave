"""Builder for action dispatcher with handlers."""

from typing import List, Optional

from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination, ProcessingRequirement
from airweave.platform.sync.actions import EntityActionDispatcher
from airweave.platform.sync.config import SyncConfig
from airweave.platform.sync.handlers import (
    ArfHandler,
    DestinationHandler,
    EntityPostgresHandler,
)
from airweave.platform.sync.handlers.protocol import EntityActionHandler


class DispatcherBuilder:
    """Builds action dispatcher with configured handlers."""

    @classmethod
    def build(
        cls,
        destinations: List[BaseDestination],
        execution_config: Optional[SyncConfig] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build dispatcher with handlers based on config.

        Args:
            destinations: List of destination instances
            execution_config: Optional config to enable/disable handlers
            logger: Optional logger for logging handler creation

        Returns:
            ActionDispatcher with configured handlers.
        """
        handlers = cls._build_handlers(destinations, execution_config, logger)
        return EntityActionDispatcher(handlers=handlers)

    @classmethod
    def _build_handlers(
        cls,
        destinations: List[BaseDestination],
        execution_config: Optional[SyncConfig],
        logger: Optional[ContextualLogger],
    ) -> List[EntityActionHandler]:
        """Build handler list based on config."""
        enable_vector = (
            execution_config.handlers.enable_vector_handlers if execution_config else True
        )
        enable_raw = execution_config.handlers.enable_raw_data_handler if execution_config else True
        enable_postgres = (
            execution_config.handlers.enable_postgres_handler if execution_config else True
        )

        handlers: List[EntityActionHandler] = []

        cls._add_vector_handler(handlers, destinations, enable_vector, logger)
        cls._add_raw_handler(handlers, enable_raw, logger)
        cls._add_postgres_handler(handlers, enable_postgres, logger)

        if not handlers and logger:
            logger.warning("No handlers created - sync will fetch entities but not persist them")

        return handlers

    @classmethod
    def _add_vector_handler(
        cls,
        handlers: List[EntityActionHandler],
        destinations: List[BaseDestination],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add vector DB handler if enabled and destinations exist."""
        if not destinations:
            return

        if enabled:
            # Group destinations by processing requirement
            vector_db_destinations: List[BaseDestination] = []

            for dest in destinations:
                requirement = dest.processing_requirement
                if requirement == ProcessingRequirement.CHUNKS_AND_EMBEDDINGS:
                    vector_db_destinations.append(dest)
                elif requirement == ProcessingRequirement.RAW:
                    # Self-processing destinations don't need VectorDBHandler
                    pass
                else:
                    # Default to vector DB for unknown requirements (backward compat)
                    if logger:
                        logger.warning(
                            f"Unknown processing requirement {requirement} for "
                            f"{dest.__class__.__name__}, defaulting to CHUNKS_AND_EMBEDDINGS"
                        )
                    vector_db_destinations.append(dest)

            if vector_db_destinations:
                handlers.append(DestinationHandler(destinations=vector_db_destinations))
                if logger:
                    dest_names = [d.__class__.__name__ for d in vector_db_destinations]
                    logger.info(
                        f"Created DestinationHandler for {len(vector_db_destinations)} "
                        f"destination(s): {dest_names}"
                    )
        elif logger:
            logger.info(
                f"Skipping VectorDBHandler (disabled by execution_config) for "
                f"{len(destinations)} destination(s)"
            )

    @classmethod
    def _add_raw_handler(
        cls,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add raw data handler if enabled."""
        if enabled:
            handlers.append(ArfHandler())
        elif logger:
            logger.info("Skipping RawDataHandler (disabled by execution_config)")

    @classmethod
    def _add_postgres_handler(
        cls,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add Postgres metadata handler if enabled (always last)."""
        if enabled:
            handlers.append(EntityPostgresHandler())
        elif logger:
            logger.info("Skipping PostgresMetadataHandler (disabled by execution_config)")
