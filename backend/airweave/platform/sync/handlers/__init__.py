"""Handlers module for sync pipeline.

Contains handlers that execute resolved actions.

Handler Types:
- DestinationHandler: Generic handler using processor strategy pattern
- ArfHandler: Raw entity storage for audit/replay (ARF = Airweave Raw Format)
- PostgresMetadataHandler: Metadata persistence (runs last)

Architecture:
    All handlers implement ActionHandler protocol via duck typing. They receive
    resolved actions and persist them to their destination. The ActionDispatcher
    runs destination handlers concurrently, then PostgresMetadataHandler sequentially.

Processor Pattern:
    DestinationHandler maps ProcessingRequirement enum to processor singletons.
    Destinations declare what they need, handler owns processor lifecycle.
"""

from .arf import ArfHandler
from .destination import DestinationHandler
from .postgres import PostgresMetadataHandler
from .protocol import ActionHandler

__all__ = [
    "ActionHandler",
    "ArfHandler",
    "DestinationHandler",
    "PostgresMetadataHandler",
]
