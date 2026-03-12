"""Entity action types, resolver, and dispatcher.

Entity-specific action pipeline for sync operations.

Re-exports are lazy to avoid circular imports: entity_action_resolver imports
from .types, which triggers this __init__. Using __getattr__ breaks the cycle.
"""


def __getattr__(name: str):
    """Lazy re-exports to avoid circular imports."""
    _map = {
        "EntityActionDispatcher": (
            "airweave.domains.sync_pipeline.entity_action_dispatcher",
            "EntityActionDispatcher",
        ),
        "EntityActionResolver": (
            "airweave.domains.sync_pipeline.entity_action_resolver",
            "EntityActionResolver",
        ),
        "EntityDispatcherBuilder": (
            "airweave.platform.sync.actions.entity.builder",
            "EntityDispatcherBuilder",
        ),
        "EntityActionBatch": (
            "airweave.platform.sync.actions.entity.types",
            "EntityActionBatch",
        ),
        "EntityDeleteAction": (
            "airweave.platform.sync.actions.entity.types",
            "EntityDeleteAction",
        ),
        "EntityInsertAction": (
            "airweave.platform.sync.actions.entity.types",
            "EntityInsertAction",
        ),
        "EntityKeepAction": (
            "airweave.platform.sync.actions.entity.types",
            "EntityKeepAction",
        ),
        "EntityUpdateAction": (
            "airweave.platform.sync.actions.entity.types",
            "EntityUpdateAction",
        ),
    }
    if name in _map:
        import importlib

        module_path, attr = _map[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "EntityActionBatch",
    "EntityDeleteAction",
    "EntityInsertAction",
    "EntityKeepAction",
    "EntityUpdateAction",
    "EntityActionResolver",
    "EntityActionDispatcher",
    "EntityDispatcherBuilder",
]
