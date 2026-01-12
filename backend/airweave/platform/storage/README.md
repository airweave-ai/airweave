# Storage Module

File storage abstractions for Airweave sync operations.

## Components

| File | Description |
|------|-------------|
| `backend.py` | `StorageBackend` interface + Filesystem/Azure Blob implementations |
| `paths.py` | `StoragePaths` - centralized path constants for ARF and temp storage |
| `arf_reader.py` | `ArfReader` - entity reconstruction for replay |
| `replay_source.py` | `ArfReplaySource` - internal source for ARF replay mode |
| `file_service.py` | `FileService` - file download and restoration to temp directory |
| `exceptions.py` | Storage-specific exceptions |

## Usage

```python
from airweave.platform.storage import StorageManager

manager = StorageManager()
await manager.save_file_from_entity(logger, sync_id, entity)
```

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

### Location

- **Local**: `backend/local_storage/raw/`
- **Kubernetes**: PVC-mounted at configured `STORAGE_PATH`
