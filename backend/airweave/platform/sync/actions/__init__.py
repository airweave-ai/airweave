"""Actions module for sync pipelines.

Organized by domain:
- entity/: Entity action types, resolver, dispatcher, builder

Each domain has its own types, resolver, and dispatcher tailored to its needs.
"""

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
