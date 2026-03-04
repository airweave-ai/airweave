"""Storage integration module for Airweave.

This module provides unified storage abstractions including:
- StorageBackend: Protocol interface for persistent storage
- Backend implementations: Filesystem, Azure Blob, AWS S3, GCP GCS
- FileService: File download and restoration to temp directory
- paths: Centralized path constants for all storage operations

Exports are lazy-loaded to avoid triggering heavy imports (like settings)
when only specific submodules are needed.
"""

from typing import TYPE_CHECKING

# These imports are lightweight (no heavy dependencies)
from airweave.platform.storage.exceptions import (
    FileSkippedException,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageQuotaExceededError,
)
from airweave.platform.storage.paths import StoragePaths, paths
from airweave.platform.storage.protocol import StorageBackend

# Lazy imports for heavy modules
if TYPE_CHECKING:
    from airweave.platform.storage.arf_reader import ArfReader
    from airweave.platform.storage.backends import (
        AzureBlobBackend,
        FilesystemBackend,
        GCSBackend,
        S3Backend,
    )
    from airweave.platform.storage.factory import get_storage_backend
    from airweave.platform.storage.file_service import FileDownloadService, FileService
    from airweave.platform.storage.replay_source import ArfReplaySource
    from airweave.platform.storage.sync_file_manager import (
        SyncFileManager,
        sync_file_manager,
    )

__all__ = [
    # Protocol
    "StorageBackend",
    # Backend implementations (lazy)
    "FilesystemBackend",
    "AzureBlobBackend",
    "S3Backend",
    "GCSBackend",
    # Factory and singleton (lazy)
    "get_storage_backend",
    "storage_backend",
    # File service (lazy)
    "FileService",
    "FileDownloadService",
    # ARF (lazy)
    "ArfReader",
    "ArfReplaySource",
    # Paths
    "StoragePaths",
    "paths",
    # Exceptions
    "StorageException",
    "StorageConnectionError",
    "StorageAuthenticationError",
    "StorageNotFoundError",
    "StorageQuotaExceededError",
    "FileSkippedException",
    # Sync file manager (lazy)
    "SyncFileManager",
    "sync_file_manager",
]


def __getattr__(name: str):
    """Lazy import heavy modules on first access."""
    if name in ("FilesystemBackend", "AzureBlobBackend", "S3Backend", "GCSBackend"):
        from airweave.platform.storage.backends import (
            AzureBlobBackend,
            FilesystemBackend,
            GCSBackend,
            S3Backend,
        )

        return {
            "FilesystemBackend": FilesystemBackend,
            "AzureBlobBackend": AzureBlobBackend,
            "S3Backend": S3Backend,
            "GCSBackend": GCSBackend,
        }[name]

    if name == "get_storage_backend":
        from airweave.platform.storage.factory import get_storage_backend

        return get_storage_backend

    if name == "storage_backend":
        from airweave.platform.storage.factory import get_storage_backend

        return get_storage_backend()

    if name in ("FileService", "FileDownloadService"):
        from airweave.platform.storage.file_service import (
            FileDownloadService,
            FileService,
        )

        return {"FileService": FileService, "FileDownloadService": FileDownloadService}[name]

    if name == "ArfReader":
        from airweave.platform.storage.arf_reader import ArfReader

        return ArfReader

    if name == "ArfReplaySource":
        from airweave.platform.storage.replay_source import ArfReplaySource

        return ArfReplaySource

    if name in ("SyncFileManager", "sync_file_manager"):
        from airweave.platform.storage.sync_file_manager import (
            SyncFileManager,
            sync_file_manager,
        )

        return {"SyncFileManager": SyncFileManager, "sync_file_manager": sync_file_manager}[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
