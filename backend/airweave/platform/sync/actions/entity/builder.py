"""Builder for entity action dispatcher."""

from typing import List, Optional

from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.sync.actions.entity.dispatcher import EntityActionDispatcher
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
        execution_config: Optional[SyncConfig] = None,
        logger: Optional[ContextualLogger] = None,
        guard_rail=None,
    ) -> EntityActionDispatcher:
        """Build dispatcher with handlers based on config.

        Args:
            destinations: Destination instances
            execution_config: Optional config to enable/disable handlers
            logger: Optional logger for logging handler creation
            guard_rail: Optional GuardRailService for EntityPostgresHandler

        Returns:
            EntityActionDispatcher with configured handlers.
        """
        handlers = cls._build_handlers(destinations, execution_config, logger, guard_rail)
        return EntityActionDispatcher(handlers=handlers)

    @classmethod
    def build_for_cleanup(
        cls,
        destinations: List[BaseDestination],
        logger: Optional[ContextualLogger] = None,
    ) -> EntityActionDispatcher:
        """Build dispatcher for cleanup operations (all handlers enabled).

        Args:
            destinations: Destinations context
            logger: Optional logger

        Returns:
            EntityActionDispatcher for cleanup.
        """
        return cls.build(destinations=destinations, execution_config=None, logger=logger)

    @classmethod
    def _build_handlers(
        cls,
        destinations: List[BaseDestination],
        execution_config: Optional[SyncConfig],
        logger: Optional[ContextualLogger],
        guard_rail=None,
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
        cls._add_arf_handler(handlers, enable_arf, logger)
        cls._add_postgres_handler(handlers, enable_postgres, logger, guard_rail)

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
                processor_info = [
                    f"{d.__class__.__name__}→{d.processing_requirement.value}" for d in destinations
                ]
                logger.info(f"Created DestinationHandler with requirements: {processor_info}")
        elif logger:
            logger.info(
                f"Skipping VectorDBHandler (disabled by execution_config) for "
                f"{len(destinations)} destination(s)"
            )

    @classmethod
    def _add_arf_handler(
        cls,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
    ) -> None:
        """Add ARF handler if enabled."""
        if enabled:
            handlers.append(ArfHandler())
            if logger:
                logger.debug("Added ArfHandler")
        elif logger:
            logger.info("Skipping ArfHandler (disabled by execution_config)")

    @classmethod
    def _add_postgres_handler(
        cls,
        handlers: List[EntityActionHandler],
        enabled: bool,
        logger: Optional[ContextualLogger],
        guard_rail=None,
    ) -> None:
        """Add Postgres metadata handler if enabled (always last)."""
        if enabled:
            handlers.append(EntityPostgresHandler(guard_rail=guard_rail))
            if logger:
                logger.debug("Added EntityPostgresHandler")
        elif logger:
            logger.info("Skipping EntityPostgresHandler (disabled by execution_config)")
