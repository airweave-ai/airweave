"""Cleanup module for persistent data deletion.

Provides unified cleanup for:
- Destination data (Qdrant, Vespa) via handler pattern
- ARF storage
- Temporal schedules

Usage from API:
    from airweave.platform.cleanup import cleanup_service

    # Source connection deletion
    await cleanup_service.cleanup_sync(db, sync_id, collection, ctx)

    # Collection deletion
    await cleanup_service.cleanup_collection(db, collection, ctx)

    # Schedule cleanup
    await cleanup_service.cleanup_schedules_for_syncs(sync_ids, ctx)
"""

from airweave.platform.cleanup.service import cleanup_service

__all__ = ["cleanup_service"]
