"""Storage domain.

Unified storage abstractions for persistent file and object storage
across filesystem, Azure Blob, AWS S3, and GCP GCS backends.
"""

from airweave.domains.storage.exceptions import (
    FileSkippedException,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageQuotaExceededError,
)
from airweave.domains.storage.paths import StoragePaths, paths
from airweave.domains.storage.protocols import StorageBackend

__all__ = [
    "StorageBackend",
    "StoragePaths",
    "paths",
    "StorageException",
    "StorageConnectionError",
    "StorageAuthenticationError",
    "StorageNotFoundError",
    "StorageQuotaExceededError",
    "FileSkippedException",
]
