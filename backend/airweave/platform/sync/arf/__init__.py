"""ARF backward-compat shim.

# [code blue] can be deleted once all imports are migrated to domains.arf
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
    if name == "ArfService":
        from airweave.domains.arf.service import ArfService

        return ArfService

    if name == "SyncManifest":
        from airweave.domains.arf.types import SyncManifest

        return SyncManifest

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
