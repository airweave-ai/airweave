"""Builder for entity action dispatcher."""

from typing import List, Optional

from airweave.core.logging import ContextualLogger
from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.sync_pipeline.entity_action_dispatcher import EntityActionDispatcher
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.sync.config import SyncConfig
from airweave.platform.sync.handlers.arf import ArfHandler
from airweave.platform.sync.handlers.destination import DestinationHandler
from airweave.platform.sync.handlers.entity_postgres import EntityPostgresHandler
from airweave.platform.sync.handlers.protocol import EntityActionHandler


class EntityDispatcherBuilder:
    """Builds entity action dispatcher with configured handlers."""

    @classmethod
    def build(
        cls,
        destinations: List[BaseDestination],
        arf_service: Optional[ArfServiceProtocol] = None,
        execution_config: Optional[SyncConfig] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build dispatcher with handlers based on config.

        Args:
            destinations: Destination instances
            arf_service: ARF service for raw entity capture
            execution_config: Optional config to enable/disable handlers
            logger: Optional logger for logging handler creation
        """
        handlers = cls._build_handlers(destinations, arf_service, execution_config, logger)
        return EntityActionDispatcher(handlers=handlers)

    @classmethod
    def build_for_cleanup(
        cls,
        destinations: List[BaseDestination],
        arf_service: Optional[ArfServiceProtocol] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build dispatcher for cleanup operations (all handlers enabled)."""
        return cls.build(
            destinations=destinations, arf_service=arf_service, execution_config=None, logger=logger
        )

    @classmethod
    def _build_handlers(
        cls,
        destinations: List[BaseDestination],
        arf_service: Optional[ArfServiceProtocol],
        execution_config: Optional[SyncConfig],
        logger: Optional[ContextualLogger],
    ) -> List[EntityActionHandler]:
        """Build handler list based on config."""
        enable_vector = (
            execution_config.handlers.enable_vector_handlers if execution_config else True
        )
        enable_arf = execution_config.handlers.enable_raw_data_handler if execution_config else True
        enable_postgres = (
            execution_config.handlers.enable_postgres_handler if execution_config else True
        )

        handlers: List[EntityActionHandler] = []

        cls._add_destination_handler(handlers, destinations, enable_vector, logger)
        cls._add_arf_handler(handlers, arf_service, enable_arf, logger)
        cls._add_postgres_handler(handlers, enable_postgres, logger)

        if not handlers and logger:
            logger.warning("No handlers created - sync will fetch entities but not persist them")

        return handlers

    @classmethod
    def _add_destination_handler(
        cls,
        handlers: List[EntityActionHandler],
        destinations: List[BaseDestination],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add destination handler if enabled and destinations exist."""
        if not destinations:
            return

        if enabled:
            handlers.append(DestinationHandler(destinations=destinations))
            if logger:
                dest_names = [d.__class__.__name__ for d in destinations]
                logger.info(f"Created DestinationHandler for {dest_names}")
        elif logger:
            logger.info(
                f"Skipping VectorDBHandler (disabled by execution_config) for "
                f"{len(destinations)} destination(s)"
            )

    @classmethod
    def _add_arf_handler(
        cls,
        handlers: List[EntityActionHandler],
        arf_service: Optional[ArfServiceProtocol],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add ARF handler if enabled and service available."""
        if not enabled:
            if logger:
                logger.info("Skipping ArfHandler (disabled by execution_config)")
            return

        if arf_service is None:
            if logger:
                logger.warning("Skipping ArfHandler (no arf_service provided)")
            return

        handlers.append(ArfHandler(arf_service=arf_service))
        if logger:
            logger.debug("Added ArfHandler")

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
            if logger:
                logger.debug("Added EntityPostgresHandler")
        elif logger:
            logger.info("Skipping EntityPostgresHandler (disabled by execution_config)")
