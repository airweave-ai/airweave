"""ARF handler for raw entity persistence.

Stores raw entity data to the storage backend (local filesystem or cloud storage)
for debugging, replay, and audit purposes.
"""

from typing import List

from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.platform.contexts import SyncContext
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.protocol import EntityActionHandler


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

    def __init__(self, arf_service: ArfServiceProtocol) -> None:
        """Initialize with injected ARF service."""
        self._arf_service = arf_service
        self._manifest_initialized = False

    @property
    def name(self) -> str:  # noqa: D102
        return "arf"

    async def _ensure_manifest(self, sync_context: SyncContext, runtime: SyncRuntime) -> None:
        """Ensure manifest exists for this sync (called once per sync)."""
        if self._manifest_initialized:
            return
        try:
            await self._arf_service.upsert_manifest(sync_context, runtime)
            self._manifest_initialized = True
        except Exception as e:
            sync_context.logger.warning(f"[ARF] Failed to upsert manifest: {e}")

    # -------------------------------------------------------------------------
    # Protocol: Public Interface
    # -------------------------------------------------------------------------

    async def handle_batch(  # noqa: D102
        self,
        batch: EntityActionBatch,
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        if batch.deletes:
            await self.handle_deletes(batch.deletes, sync_context)
        if batch.updates:
            await self.handle_updates(batch.updates, sync_context, runtime)
        if batch.inserts:
            await self.handle_inserts(batch.inserts, sync_context, runtime)

    async def handle_inserts(  # noqa: D102
        self,
        actions: List[EntityInsertAction],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        if not actions:
            return
        await self._ensure_manifest(sync_context, runtime)
        entities = [action.entity for action in actions]
        await self._do_upsert(entities, "insert", sync_context)

    async def handle_updates(  # noqa: D102
        self,
        actions: List[EntityUpdateAction],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        if not actions:
            return
        await self._ensure_manifest(sync_context, runtime)
        entities = [action.entity for action in actions]
        await self._do_upsert(entities, "update", sync_context)

    async def handle_deletes(  # noqa: D102
        self,
        actions: List[EntityDeleteAction],
        sync_context: SyncContext,
    ) -> None:
        if not actions:
            return
        entity_ids = [str(action.entity_id) for action in actions]
        await self._do_delete(entity_ids, "delete", sync_context)

    async def handle_orphan_cleanup(  # noqa: D102
        self,
        orphan_entity_ids: List[str],
        sync_context: SyncContext,
    ) -> None:
        if not orphan_entity_ids:
            return
        await self._do_delete(orphan_entity_ids, "orphan_cleanup", sync_context)

    # -------------------------------------------------------------------------
    # Private: Implementation
    # -------------------------------------------------------------------------

    async def _do_upsert(
        self,
        entities: List[BaseEntity],
        operation: str,
        sync_context: SyncContext,
    ) -> None:
        try:
            count = await self._arf_service.upsert_entities(
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
        sync_context: SyncContext,
    ) -> None:
        try:
            deleted = await self._arf_service.delete_entities(
                entity_ids=entity_ids,
                sync_context=sync_context,
            )
            if deleted:
                sync_context.logger.debug(f"[ARF] {operation}: deleted {deleted} entities")
        except Exception as e:
            raise SyncFailureError(f"[ARF] {operation} failed: {e}") from e
