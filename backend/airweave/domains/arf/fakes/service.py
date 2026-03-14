"""In-memory fake for ArfServiceProtocol."""

from typing import Any, Dict, List, Optional

from airweave.domains.arf.types import SyncManifest
from airweave.domains.sync_pipeline.contexts import SyncContext
from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime
from airweave.platform.entities._base import BaseEntity


class FakeArfService:
    """In-memory fake for ArfServiceProtocol.

    Stores entities and manifests in dicts for assertions.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._manifests: Dict[str, SyncManifest] = {}
        self._calls: List[tuple] = []
        self._should_raise: Optional[Exception] = None

    # -- Test helpers ----------------------------------------------------------

    def seed(self, sync_id: str, entity_id: str, entity_dict: Dict[str, Any]) -> None:
        """Pre-populate an entity."""
        self._store.setdefault(sync_id, {})[entity_id] = entity_dict

    def seed_manifest(self, sync_id: str, manifest: SyncManifest) -> None:
        """Pre-populate a manifest."""
        self._manifests[sync_id] = manifest

    def set_error(self, error: Exception) -> None:
        """Configure next call to raise."""
        self._should_raise = error

    def get_calls(self, method: str) -> List[tuple]:
        """Return calls for a specific method."""
        return [c for c in self._calls if c[0] == method]

    def entity_count_for(self, sync_id: str) -> int:
        """Count entities stored for a sync."""
        return len(self._store.get(sync_id, {}))

    # -- Protocol implementation -----------------------------------------------

    async def upsert_manifest(self, sync_context: SyncContext, runtime: SyncRuntime) -> None:
        self._calls.append(("upsert_manifest", sync_context, runtime))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc

    async def upsert_entities(self, entities: List[BaseEntity], sync_context: SyncContext) -> int:
        self._calls.append(("upsert_entities", entities, sync_context))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        sync_id = str(sync_context.sync.id)
        bucket = self._store.setdefault(sync_id, {})
        for entity in entities:
            bucket[str(entity.entity_id)] = entity.model_dump(mode="json")
        return len(entities)

    async def delete_entities(self, entity_ids: List[str], sync_context: SyncContext) -> int:
        self._calls.append(("delete_entities", entity_ids, sync_context))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        sync_id = str(sync_context.sync.id)
        bucket = self._store.get(sync_id, {})
        deleted = 0
        for eid in entity_ids:
            if eid in bucket:
                del bucket[eid]
                deleted += 1
        return deleted

    async def cleanup_stale_entities(self, sync_context: SyncContext, runtime: SyncRuntime) -> int:
        self._calls.append(("cleanup_stale_entities", sync_context, runtime))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return 0

    async def get_entity_count(self, sync_id: str) -> int:
        self._calls.append(("get_entity_count", sync_id))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return len(self._store.get(sync_id, {}))

    async def sync_exists(self, sync_id: str) -> bool:
        self._calls.append(("sync_exists", sync_id))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return sync_id in self._manifests or sync_id in self._store

    async def delete_sync(self, sync_id: str) -> bool:
        self._calls.append(("delete_sync", sync_id))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        existed = sync_id in self._store or sync_id in self._manifests
        self._store.pop(sync_id, None)
        self._manifests.pop(sync_id, None)
        return existed

    async def get_manifest(self, sync_id: str) -> Optional[SyncManifest]:
        self._calls.append(("get_manifest", sync_id))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return self._manifests.get(sync_id)

    async def get_replay_stats(self, sync_id: str) -> Dict[str, Any]:
        self._calls.append(("get_replay_stats", sync_id))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        manifest = self._manifests.get(sync_id)
        if not manifest:
            return {"exists": False}
        return {
            "exists": True,
            "sync_id": manifest.sync_id,
            "source": manifest.source_short_name,
            "entity_count": len(self._store.get(sync_id, {})),
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "sync_jobs": manifest.sync_jobs,
        }
