"""Contexts for platform operations.

Context Types:
- SyncContext: Frozen data for sync operations (inherits BaseContext)
- SyncRuntime: Live services for a sync run (source, cursor, trackers, etc.)
- CleanupContext: Minimal context for deletion operations (inherits BaseContext)
"""

from airweave.platform.contexts.cleanup import CleanupContext
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.contexts.sync import SyncContext

__all__ = [
    "CleanupContext",
    "SyncContext",
    "SyncRuntime",
]
