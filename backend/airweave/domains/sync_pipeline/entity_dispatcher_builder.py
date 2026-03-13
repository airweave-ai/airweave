"""Builder for entity action dispatcher."""

from typing import List, Optional

from airweave.core.logging import ContextualLogger
from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.entities.protocols import EntityRepositoryProtocol
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.sync_pipeline.entity_action_dispatcher import EntityActionDispatcher
from airweave.domains.sync_pipeline.handlers.arf import ArfHandler
from airweave.domains.sync_pipeline.handlers.destination import DestinationHandler
from airweave.domains.sync_pipeline.handlers.entity_postgres import EntityPostgresHandler
from airweave.domains.sync_pipeline.handlers.protocol import EntityActionHandler
from airweave.domains.sync_pipeline.protocols import ChunkEmbedProcessorProtocol
from airweave.platform.destinations._base import BaseDestination


class EntityDispatcherBuilder:
    """Builds entity action dispatcher with configured handlers."""

    def __init__(
        self,
        processor: ChunkEmbedProcessorProtocol,
        entity_repo: EntityRepositoryProtocol,
        arf_service: Optional[ArfServiceProtocol] = None,
    ) -> None:
        """Initialize with processor and entity repository."""
        self._processor = processor
        self._entity_repo = entity_repo
        self._arf_service = arf_service

    def build(
        self,
        destinations: List[BaseDestination],
        execution_config: Optional[SyncConfig] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build a dispatcher with all configured handlers."""
        handlers = self._build_handlers(destinations, execution_config, logger)
        return EntityActionDispatcher(handlers=handlers)

    def build_for_cleanup(
        self,
        destinations: List[BaseDestination],
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build a dispatcher configured for cleanup (no execution config)."""
        return self.build(destinations=destinations, execution_config=None, logger=logger)

    def _build_handlers(
        self,
        destinations: List[BaseDestination],
        execution_config: Optional[SyncConfig],
        logger: Optional[ContextualLogger],
    ) -> List[EntityActionHandler]:
        enable_vector = (
            execution_config.handlers.enable_vector_handlers if execution_config else True
        )
        enable_arf = execution_config.handlers.enable_raw_data_handler if execution_config else True
        enable_postgres = (
            execution_config.handlers.enable_postgres_handler if execution_config else True
        )

        handlers: List[EntityActionHandler] = []

        self._add_destination_handler(handlers, destinations, enable_vector, logger)
        self._add_arf_handler(handlers, enable_arf, logger)
        self._add_postgres_handler(handlers, enable_postgres, logger)

        if not handlers and logger:
            logger.warning("No handlers created - sync will fetch entities but not persist them")

        return handlers

    def _add_destination_handler(
        self,
        handlers: List[EntityActionHandler],
        destinations: List[BaseDestination],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        if not destinations:
            return

        if enabled:
            handlers.append(
                DestinationHandler(destinations=destinations, processor=self._processor)
            )
            if logger:
                dest_names = [d.__class__.__name__ for d in destinations]
                logger.info(f"Created DestinationHandler for {dest_names}")
        elif logger:
            logger.info(
                f"Skipping VectorDBHandler (disabled by execution_config) for "
                f"{len(destinations)} destination(s)"
            )

    def _add_arf_handler(
        self,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        if not enabled:
            if logger:
                logger.info("Skipping ArfHandler (disabled by execution_config)")
            return

        if self._arf_service is None:
            if logger:
                logger.warning("Skipping ArfHandler (no arf_service provided)")
            return

        handlers.append(ArfHandler(arf_service=self._arf_service))
        if logger:
            logger.debug("Added ArfHandler")

    def _add_postgres_handler(
        self,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        if enabled:
            handlers.append(EntityPostgresHandler(entity_repo=self._entity_repo))
            if logger:
                logger.debug("Added EntityPostgresHandler")
        elif logger:
            logger.info("Skipping EntityPostgresHandler (disabled by execution_config)")
