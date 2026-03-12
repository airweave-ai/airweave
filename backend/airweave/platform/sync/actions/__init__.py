"""Actions module for sync pipelines.

Organized by domain:
- entity/: Entity action types, resolver, dispatcher, builder
- access_control/: Access control action types, resolver, dispatcher

Each domain has its own types, resolver, and dispatcher tailored to its needs.

Entity re-exports are lazy to avoid circular imports with domains/sync_pipeline.
"""

from airweave.platform.sync.actions.access_control import (
    ACActionDispatcher,
    ACActionResolver,
    ACDeleteAction,
    ACInsertAction,
    ACKeepAction,
    ACUpdateAction,
)


def __getattr__(name: str):
    """Lazy re-exports for entity action symbols."""
    from airweave.platform.sync.actions import entity as _entity_pkg

    if name in _entity_pkg.__all__:
        return getattr(_entity_pkg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Access control types
    "ACDeleteAction",
    "ACInsertAction",
    "ACKeepAction",
    "ACUpdateAction",
    # Access control resolver and dispatcher
    "ACActionResolver",
    "ACActionDispatcher",
    # Entity types (lazy)
    "EntityActionBatch",
    "EntityDeleteAction",
    "EntityInsertAction",
    "EntityKeepAction",
    "EntityUpdateAction",
    # Entity resolver and dispatcher (lazy)
    "EntityActionResolver",
    "EntityActionDispatcher",
    "EntityDispatcherBuilder",
]
