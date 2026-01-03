"""ARF (Airweave Raw Format) module for entity storage and replay.

Stores raw entities during sync for:
- Audit trail of what was synced
- Replay with different configurations
- Debugging sync issues

Storage structure:
    raw/{sync_id}/
    ├── manifest.json           # Sync metadata
    ├── entities/
    │   └── {entity_id}.json    # One file per entity
    └── files/
        └── {entity_id}_{name}.{ext}  # File attachments
"""

from .schema import SyncManifest
from .service import ArfService, arf_service

__all__ = [
    "ArfService",
    "SyncManifest",
    "arf_service",
]
