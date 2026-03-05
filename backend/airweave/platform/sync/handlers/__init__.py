"""Handlers module for sync pipeline.

Contains handlers that execute resolved actions.

Generic Protocol:
    ActionHandler[T, B] - parameterized by payload type T and batch type B

Type Aliases:
    EntityActionHandler = ActionHandler[BaseEntity, EntityActionBatch]

Entity Handlers:
- DestinationHandler: Generic handler using processor strategy pattern
- ArfHandler: Raw entity storage for audit/replay (ARF = Airweave Raw Format)
- EntityPostgresHandler: Entity metadata persistence (runs last)

Architecture:
    All handlers implement ActionHandler[T, B] with their specific types.
    Entity handlers use T=BaseEntity, B=EntityActionBatch.
    The dispatchers call handlers concurrently for their respective sync types.
"""

# Handlers
from .access_control_postgres import ACPostgresHandler
from .arf import ArfHandler
from .destination import DestinationHandler
from .entity_postgres import EntityPostgresHandler

# Protocol and type aliases
from .protocol import ACActionHandler, EntityActionHandler

__all__ = [
    # Protocol and type aliases
    "ACActionHandler",
    "EntityActionHandler",
    # Entity handlers
    "ACPostgresHandler",
    "ArfHandler",
    "DestinationHandler",
    "EntityPostgresHandler",
]
