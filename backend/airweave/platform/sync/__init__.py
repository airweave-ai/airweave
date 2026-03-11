"""Sync module for Airweave.

Provides:
- SyncOrchestrator: Coordinates the entire sync workflow
- EntityPipeline: Processes entities through transformation stages
- SyncContext: Immutable container for sync resources

ARF has been migrated to domains/arf/. Lazy re-exports are kept for backward compat.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.domains.arf.service import ArfService
    from airweave.domains.arf.types import SyncManifest

__all__ = [
    "ArfService",
    "SyncManifest",
]


def __getattr__(name: str):
    """Lazy imports for backward compatibility."""
    if name == "ArfService":
        from airweave.domains.arf.service import ArfService

        return ArfService

    if name == "SyncManifest":
        from airweave.domains.arf.types import SyncManifest

        return SyncManifest

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
