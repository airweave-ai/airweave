"""Contexts for platform operations.

Context Types:
- SyncContext: Full sync context (inherits BaseContext, flat fields)
- CleanupContext: Minimal context for deletion operations (inherits BaseContext)
"""

from airweave.platform.contexts.cleanup import CleanupContext
from airweave.platform.contexts.sync import SyncContext

__all__ = [
    "CleanupContext",
    "SyncContext",
]
