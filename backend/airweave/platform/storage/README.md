# Storage Module

File storage abstractions for Airweave sync operations.

## Architecture

The storage module uses a **protocol-based architecture** with pluggable backends:

```
storage/
├── protocol.py         # StorageBackend Protocol (interface)
├── factory.py          # get_storage_backend() factory
├── backends/           # Backend implementations
│   ├── filesystem.py   # Local filesystem / K8s PVC
│   ├── azure_blob.py   # Azure Blob Storage
│   ├── aws_s3.py       # AWS S3 (and S3-compatible)
│   └── gcp_gcs.py      # Google Cloud Storage
├── paths.py            # StoragePaths - centralized path constants
├── arf_reader.py       # ArfReader - entity reconstruction for replay
├── replay_source.py    # ArfReplaySource - internal source for ARF replay
├── file_service.py     # FileService - file download/restoration
├── sync_file_manager.py # SyncFileManager - sync-scoped file management
└── exceptions.py       # Storage-specific exceptions
```

## Configuration

Storage backend is selected via environment variables:

```bash
# Primary selector (auto-resolves from ENVIRONMENT if not set)
STORAGE_BACKEND=filesystem|azure|aws|gcp

# Filesystem
STORAGE_PATH=/data/airweave

# Azure Blob Storage
STORAGE_AZURE_ACCOUNT=myaccount
STORAGE_AZURE_CONTAINER=raw
STORAGE_AZURE_PREFIX=

# AWS S3
STORAGE_AWS_BUCKET=mybucket
STORAGE_AWS_REGION=us-east-1
STORAGE_AWS_PREFIX=
STORAGE_AWS_ENDPOINT_URL=  # For MinIO, LocalStack

# GCP Cloud Storage
STORAGE_GCP_BUCKET=mybucket
STORAGE_GCP_PROJECT=myproject
STORAGE_GCP_PREFIX=
```

## Usage

```python
from airweave.platform.storage import storage_backend, StorageBackend

# Use the singleton (configured from environment)
await storage_backend.write_json("raw/sync123/manifest.json", {"key": "value"})
data = await storage_backend.read_json("raw/sync123/manifest.json")

# Or get a fresh instance
from airweave.platform.storage import get_storage_backend
backend = get_storage_backend()
```

## Backend Implementations

| Backend | Class | Auth Method |
|---------|-------|-------------|
| Filesystem | `FilesystemBackend` | N/A (local paths) |
| Azure Blob | `AzureBlobBackend` | DefaultAzureCredential |
| AWS S3 | `S3Backend` | Standard AWS credential chain |
| GCP GCS | `GCSBackend` | Application Default Credentials |

---

## Airweave Raw Format (ARF)

ARF is the schema for capturing raw entity data during syncs. It enables replay, debugging, and evaluation.

### Structure

```
raw/{sync_id}/
├── manifest.json       # Sync metadata
├── entities/           # One JSON file per entity
│   └── {entity_id}.json
└── files/              # Binary files (optional)
    └── {entity_id}_{filename.ext}
```

### manifest.json

```json
{
  "sync_id": "uuid",
  "source_short_name": "asana",
  "entity_count": 42,
  "file_count": 10
}
```

### Entity Files

Each entity JSON contains original fields plus reconstruction metadata:

```json
{
  "entity_id": "123",
  "__entity_class__": "AsanaTaskEntity",
  "__entity_module__": "airweave.platform.entities.asana",
  "__captured_at__": "ISO-8601"
}
```

### Storage Locations

| Environment | Backend | Location |
|-------------|---------|----------|
| Local | Filesystem | `./local_storage/raw/` |
| K8s (Azure) | Azure Blob | `{storage_account}/{container}/raw/` |
| K8s (AWS) | S3 | `s3://{bucket}/raw/` |
| K8s (GCP) | GCS | `gs://{bucket}/raw/` |
