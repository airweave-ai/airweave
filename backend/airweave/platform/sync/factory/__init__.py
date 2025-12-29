"""Sync factory module - creates orchestrators for sync operations.

Public API:
    from airweave.platform.sync.factory import SyncFactory

    orchestrator = await SyncFactory.create_orchestrator(...)

Internal builders (for sibling modules like multiplex/):
    Import directly from private modules:
    from airweave.platform.sync.factory._destination import DestinationBuilder
    from airweave.platform.sync.factory._context import ReplayContextBuilder
    from airweave.platform.sync.factory._pipeline import PipelineBuilder
"""

from airweave.platform.sync.factory._factory import SyncFactory

__all__ = ["SyncFactory"]
