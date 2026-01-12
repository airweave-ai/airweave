"""Entity action types, resolver, and dispatcher.

Entity-specific action pipeline for sync operations.
"""

from airweave.platform.sync.actions.entity.builder import EntityDispatcherBuilder
from airweave.platform.sync.actions.entity.dispatcher import EntityActionDispatcher
from airweave.platform.sync.actions.entity.resolver import EntityActionResolver
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)

__all__ = [
    # Types
    "EntityActionBatch",
    "EntityDeleteAction",
    "EntityInsertAction",
    "EntityKeepAction",
    "EntityUpdateAction",
    # Resolver and Dispatcher
    "EntityActionResolver",
    "EntityActionDispatcher",
    "EntityDispatcherBuilder",
]
