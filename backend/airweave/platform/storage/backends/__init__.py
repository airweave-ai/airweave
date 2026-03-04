"""Storage backend implementations.

Each backend implements the StorageBackend protocol for a specific
storage provider.

Available backends:
    - FilesystemBackend: Local filesystem or K8s PVC mount
    - AzureBlobBackend: Azure Blob Storage
    - S3Backend: AWS S3 (and S3-compatible like MinIO)
    - GCSBackend: Google Cloud Storage

Exports are lazy-loaded to avoid triggering heavy imports when only
specific backends are needed.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.platform.storage.backends.aws_s3 import S3Backend
    from airweave.platform.storage.backends.azure_blob import AzureBlobBackend
    from airweave.platform.storage.backends.filesystem import FilesystemBackend
    from airweave.platform.storage.backends.gcp_gcs import GCSBackend

__all__ = [
    "FilesystemBackend",
    "AzureBlobBackend",
    "S3Backend",
    "GCSBackend",
]


def __getattr__(name: str):
    """Lazy import backends on first access."""
    if name == "FilesystemBackend":
        from airweave.platform.storage.backends.filesystem import FilesystemBackend

        return FilesystemBackend

    if name == "AzureBlobBackend":
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        return AzureBlobBackend

    if name == "S3Backend":
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        return S3Backend

    if name == "GCSBackend":
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        return GCSBackend

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
