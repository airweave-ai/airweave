"""ARF handler for raw entity persistence.

Stores raw entity data to the storage backend (local filesystem or cloud storage)
for debugging, replay, and audit purposes.
"""

from typing import TYPE_CHECKING, List

from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.protocol import EntityActionHandler

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime
    from airweave.platform.entities import BaseEntity


class ArfHandler(EntityActionHandler):
    """Handler for ARF (Airweave Raw Format) storage.

    Stores entity JSON to the ARF store (entity-level files).
    Enables replay of syncs and provides audit trail.

    Storage structure:
        raw/{sync_id}/
        ├── manifest.json
        ├── entities/{entity_id}.json
        └── files/{entity_id}_{name}.{ext}
    """

    def __init__(self):
        """Initialize handler with manifest tracking."""
        self._manifest_initialized = False

    @property
    def name(self) -> str:
        """Handler name."""
        return "arf"

    async def _ensure_manifest(self, sync_context: "SyncContext", runtime: "SyncRuntime") -> None:
        """Ensure manifest exists for this sync (called once per sync)."""
        if self._manifest_initialized:
            return

        from airweave.platform.sync.arf import arf_service

        try:
            await arf_service.upsert_manifest(sync_context, runtime)
            self._manifest_initialized = True
        except Exception as e:
            sync_context.logger.warning(f"[ARF] Failed to upsert manifest: {e}")

    # -------------------------------------------------------------------------
    # Protocol: Public Interface
    # -------------------------------------------------------------------------

    async def handle_batch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle a full action batch."""
        # Order: deletes first, then updates, then inserts
        if batch.deletes:
            await self.handle_deletes(batch.deletes, sync_context)
        if batch.updates:
            await self.handle_updates(batch.updates, sync_context, runtime)
        if batch.inserts:
            await self.handle_inserts(batch.inserts, sync_context, runtime)

    async def handle_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Store inserted entities to ARF."""
        if not actions:
            return

        # Ensure manifest exists (lazily created on first write)
        await self._ensure_manifest(sync_context, runtime)

        entities = [action.entity for action in actions]
        await self._do_upsert(entities, "insert", sync_context)

    async def handle_updates(
        self,
        actions: List[EntityUpdateAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Update entities in ARF."""
        if not actions:
            return

        # Ensure manifest exists (lazily created on first write)
        await self._ensure_manifest(sync_context, runtime)

        entities = [action.entity for action in actions]
        await self._do_upsert(entities, "update", sync_context)

    async def handle_deletes(
        self,
        actions: List[EntityDeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Delete entities from ARF."""
        if not actions:
            return
        entity_ids = [str(action.entity_id) for action in actions]
        await self._do_delete(entity_ids, "delete", sync_context)

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Delete orphaned entities from ARF."""
        if not orphan_entity_ids:
            return
        await self._do_delete(orphan_entity_ids, "orphan_cleanup", sync_context)

    # -------------------------------------------------------------------------
    # Private: Implementation
    # -------------------------------------------------------------------------

    async def _do_upsert(
        self,
        entities: List["BaseEntity"],
        operation: str,
        sync_context: "SyncContext",
    ) -> None:
        """Upsert entities to ARF store."""
        from airweave.platform.sync.arf import arf_service

        try:
            count = await arf_service.upsert_entities(
                entities=entities,
                sync_context=sync_context,
            )
            if count:
                sync_context.logger.debug(f"[ARF] {operation}: stored {count} entities")
        except Exception as e:
            raise SyncFailureError(f"[ARF] {operation} failed: {e}") from e

    async def _do_delete(
        self,
        entity_ids: List[str],
        operation: str,
        sync_context: "SyncContext",
    ) -> None:
        """Delete entities from ARF store."""
        from airweave.platform.sync.arf import arf_service

        try:
            deleted = await arf_service.delete_entities(
                entity_ids=entity_ids,
                sync_context=sync_context,
            )
            if deleted:
                sync_context.logger.debug(f"[ARF] {operation}: deleted {deleted} entities")
        except Exception as e:
            raise SyncFailureError(f"[ARF] {operation} failed: {e}") from e
