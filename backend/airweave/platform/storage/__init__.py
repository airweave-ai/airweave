"""Storage integration module for Airweave.

This module provides unified storage abstractions including:
- StorageBackend: Abstract interface for persistent storage (filesystem, Azure Blob)
- FileService: File download and restoration to temp directory
- paths: Centralized path constants for all storage operations
"""

from airweave.core.config import settings
from airweave.platform.storage.arf_reader import ArfReader
from airweave.platform.storage.backend import (
    AzureBlobBackend,
    FilesystemBackend,
    StorageBackend,
)
from airweave.platform.storage.exceptions import (
    FileSkippedException,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageQuotaExceededError,
)
from airweave.platform.storage.file_service import FileDownloadService, FileService
from airweave.platform.storage.paths import StoragePaths, paths
from airweave.platform.storage.replay_source import ArfReplaySource
from airweave.platform.storage.sync_file_manager import (
    SyncFileManager,
    sync_file_manager,
)

__all__ = [
    # Backend
    "StorageBackend",
    "FilesystemBackend",
    "AzureBlobBackend",
    "storage_backend",
    # File service
    "FileService",
    "FileDownloadService",  # Backwards compatibility
    # ARF
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
    # Sync file manager
    "SyncFileManager",
    "sync_file_manager",
]


def _get_storage_backend() -> StorageBackend:
    """Factory function to get the appropriate storage backend based on settings."""
    if settings.ENVIRONMENT in ["local", "test"]:
        return FilesystemBackend(base_path=settings.STORAGE_PATH)
    elif settings.ENVIRONMENT in ["dev", "prd"]:
        return AzureBlobBackend(
            storage_account=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container=settings.AZURE_RAW_DATA_CONTAINER,
        )
    else:
        raise ValueError(f"Unsupported environment for storage backend: {settings.ENVIRONMENT}")


storage_backend: StorageBackend = _get_storage_backend()
