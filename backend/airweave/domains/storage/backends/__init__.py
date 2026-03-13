"""Storage backend implementations.

Each backend implements the StorageBackend protocol for a specific
storage provider.

Available backends:
    - FilesystemBackend: Local filesystem or K8s PVC mount
    - AzureBlobBackend: Azure Blob Storage
    - S3Backend: AWS S3 (and S3-compatible like MinIO)
    - GCSBackend: Google Cloud Storage

Import backends directly from their modules to avoid pulling in heavy
cloud SDKs unnecessarily::

    from airweave.domains.storage.backends.filesystem import FilesystemBackend
"""
