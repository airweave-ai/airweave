"""Actions module for sync pipelines.

Organized by domain:
- entity/: Entity action types, resolver, dispatcher, builder
- access_control/: Access control action types, resolver, dispatcher

Each domain has its own types, resolver, and dispatcher tailored to its needs.
"""

from airweave.platform.sync.actions.access_control import (
    ACActionDispatcher,
    ACActionResolver,
    ACDeleteAction,
    ACInsertAction,
    ACKeepAction,
    ACUpdateAction,
)
from airweave.platform.sync.actions.entity import (
    EntityActionBatch,
    EntityActionDispatcher,
    EntityActionResolver,
    EntityDeleteAction,
    EntityDispatcherBuilder,
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)

__all__ = [
    # Access control types
    "ACDeleteAction",
    "ACInsertAction",
    "ACKeepAction",
    "ACUpdateAction",
    # Access control resolver and dispatcher
    "ACActionResolver",
    "ACActionDispatcher",
    # Entity types
    "EntityActionBatch",
    "EntityDeleteAction",
    "EntityInsertAction",
    "EntityKeepAction",
    "EntityUpdateAction",
    # Entity resolver and dispatcher
    "EntityActionResolver",
    "EntityActionDispatcher",
    "EntityDispatcherBuilder",
]
