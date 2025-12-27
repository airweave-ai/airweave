"""Storage integration module for Airweave."""

from airweave.core.config import settings
from airweave.platform.storage.backend import (
    AzureBlobBackend,
    FilesystemBackend,
    StorageBackend,
)
from airweave.platform.storage.exceptions import (
    StorageAuthenticationError,
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageQuotaExceededError,
)
from airweave.platform.storage.sync_file_manager import (
    SyncFileManager,
    sync_file_manager,
)

__all__ = [
    "StorageBackend",
    "FilesystemBackend",
    "AzureBlobBackend",
    "storage_backend",
    "StorageException",
    "StorageConnectionError",
    "StorageAuthenticationError",
    "StorageNotFoundError",
    "StorageQuotaExceededError",
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
