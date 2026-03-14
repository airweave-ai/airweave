"""ARF service for entity capture and retrieval.

Stores raw entities during sync with entity-level granularity.
Supports full syncs, incremental syncs, manifest management, and replay stats.

Storage layout:
    raw/{sync_id}/
    ├── manifest.json
    ├── entities/{entity_id}.json
    └── files/{entity_id}_{name}.{ext}
"""

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiofiles

from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.arf.types import SyncManifest
from airweave.domains.storage.exceptions import StorageNotFoundError
from airweave.domains.storage.protocols import StorageBackend
from airweave.platform.contexts import SyncContext
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.entities._base import BaseEntity


class ArfService(ArfServiceProtocol):
    """Service for capturing and retrieving raw entity data.

    Implements ArfServiceProtocol.
    All storage I/O is delegated to the injected StorageBackend.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize with injected storage backend."""
        self._storage = storage

    # =========================================================================
    # Path helpers
    # =========================================================================

    @staticmethod
    def _sync_path(sync_id: str) -> str:
        return f"raw/{sync_id}"

    @classmethod
    def _manifest_path(cls, sync_id: str) -> str:
        return f"{cls._sync_path(sync_id)}/manifest.json"

    @classmethod
    def _entity_path(cls, sync_id: str, entity_id: str) -> str:
        safe_id = cls._safe_filename(entity_id)
        return f"{cls._sync_path(sync_id)}/entities/{safe_id}.json"

    @classmethod
    def _file_path(cls, sync_id: str, entity_id: str, filename: str = "") -> str:
        safe_id = cls._safe_filename(entity_id)
        if filename:
            safe_name = cls._safe_filename(Path(filename).stem)
            ext = Path(filename).suffix or ""
            return f"{cls._sync_path(sync_id)}/files/{safe_id}_{safe_name}{ext}"
        return f"{cls._sync_path(sync_id)}/files/{safe_id}"

    @staticmethod
    def _safe_filename(value: str, max_length: int = 200) -> str:
        safe = re.sub(r'[/\\:*?"<>|]', "_", str(value))
        safe = re.sub(r"_+", "_", safe).strip("_")
        if len(safe) > max_length or safe != value:
            prefix = safe[:50] if len(safe) > 50 else safe
            hash_suffix = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()[:12]
            safe = f"{prefix}_{hash_suffix}"
        return safe[:max_length]

    # =========================================================================
    # Entity serialization helpers
    # =========================================================================

    @staticmethod
    def _get_source_short_name(sync_context: SyncContext, runtime: SyncRuntime) -> str:
        source = runtime.source
        name = getattr(source, "short_name", "") or ""
        return name or source.__class__.__name__.lower().replace("source", "")

    @staticmethod
    def _is_file_entity(entity: BaseEntity) -> bool:
        for cls in entity.__class__.__mro__:
            if cls.__name__ == "FileEntity":
                return True
        return False

    @staticmethod
    def _serialize_entity(entity: BaseEntity) -> Dict[str, Any]:
        entity_dict = entity.model_dump(mode="json")
        entity_dict["__entity_class__"] = entity.__class__.__name__
        entity_dict["__entity_module__"] = entity.__class__.__module__
        entity_dict["__captured_at__"] = datetime.now(timezone.utc).isoformat()
        return entity_dict

    # =========================================================================
    # Core operations
    # =========================================================================

    async def upsert_entity(self, entity: BaseEntity, sync_context: SyncContext) -> None:
        """Store or update a single entity."""
        sync_id = str(sync_context.sync.id)
        entity_id = str(entity.entity_id)
        entity_path = self._entity_path(sync_id, entity_id)

        is_update = await self._storage.exists(entity_path)
        if is_update:
            try:
                old_entity = await self._storage.read_json(entity_path)
                old_file = old_entity.get("__stored_file__")
                if old_file:
                    await self._storage.delete(old_file)
            except Exception:
                pass

        entity_dict = self._serialize_entity(entity)

        if self._is_file_entity(entity) and hasattr(entity, "local_path"):
            local_path = getattr(entity, "local_path", None)
            if local_path and Path(local_path).exists():
                filename = Path(local_path).name
                file_path = self._file_path(sync_id, entity_id, filename)
                try:
                    async with aiofiles.open(local_path, "rb") as f:
                        content = await f.read()
                    await self._storage.write_file(file_path, content)
                    entity_dict["__stored_file__"] = file_path
                except Exception as e:
                    sync_context.logger.warning(f"Could not store file for {entity_id}: {e}")

        await self._storage.write_json(entity_path, entity_dict)

    async def upsert_entities(self, entities: List[BaseEntity], sync_context: SyncContext) -> int:
        """Store or update multiple entities."""
        for entity in entities:
            await self.upsert_entity(entity, sync_context)
        return len(entities)

    async def delete_entity(self, entity_id: str, sync_context: SyncContext) -> bool:
        """Delete an entity and its associated files."""
        sync_id = str(sync_context.sync.id)
        entity_path = self._entity_path(sync_id, entity_id)

        if not await self._storage.exists(entity_path):
            return False

        try:
            entity_dict = await self._storage.read_json(entity_path)
            stored_file = entity_dict.get("__stored_file__")
            if stored_file:
                await self._storage.delete(stored_file)
        except Exception:
            pass

        deleted = await self._storage.delete(entity_path)
        if deleted:
            sync_context.logger.debug(f"Deleted ARF entity: {entity_id}")
        return deleted

    async def delete_entities(self, entity_ids: List[str], sync_context: SyncContext) -> int:
        """Delete multiple entities."""
        deleted_count = 0
        for entity_id in entity_ids:
            if await self.delete_entity(entity_id, sync_context):
                deleted_count += 1
        return deleted_count

    async def get_entity(self, sync_id: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entity by ID."""
        entity_path = self._entity_path(sync_id, entity_id)
        try:
            return await self._storage.read_json(entity_path)
        except StorageNotFoundError:
            return None

    async def iter_entities(
        self, sync_id: str, batch_size: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate over all entity dicts with batched concurrent reads."""
        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            files = await self._storage.list_files(entities_dir)
        except Exception:
            return

        json_files = [f for f in files if f.endswith(".json")]

        for i in range(0, len(json_files), batch_size):
            batch = json_files[i : i + batch_size]
            results = await asyncio.gather(
                *[self._storage.read_json(file_path) for file_path in batch],
                return_exceptions=True,
            )
            for result in results:
                if not isinstance(result, Exception):
                    yield result

    # =========================================================================
    # Full sync support
    # =========================================================================

    async def cleanup_stale_entities(self, sync_context: SyncContext, runtime: SyncRuntime) -> int:
        """Delete entities not seen during the current sync."""
        sync_id = str(sync_context.sync.id)
        seen_ids = runtime.entity_tracker.get_all_encountered_ids_flat()
        current_ids = await self._list_entity_ids(sync_id)
        stale_ids = [eid for eid in current_ids if eid not in seen_ids]

        if stale_ids:
            sync_context.logger.info(f"Cleaning up {len(stale_ids)} stale entities from ARF store")
            return await self.delete_entities(stale_ids, sync_context)
        return 0

    # =========================================================================
    # Manifest management
    # =========================================================================

    async def get_manifest(self, sync_id: str) -> Optional[SyncManifest]:
        """Get manifest for a sync."""
        manifest_path = self._manifest_path(sync_id)
        try:
            data = await self._storage.read_json(manifest_path)
            return SyncManifest.model_validate(data)
        except StorageNotFoundError:
            return None

    async def upsert_manifest(self, sync_context: "SyncContext", runtime: "SyncRuntime") -> None:
        """Create or update manifest for a sync job."""
        sync_id = str(sync_context.sync.id)
        manifest_path = self._manifest_path(sync_id)
        now = datetime.now(timezone.utc).isoformat()
        job_id = str(sync_context.sync_job.id)

        existing_manifest = await self.get_manifest(sync_id)

        if existing_manifest:
            if job_id not in existing_manifest.sync_jobs:
                existing_manifest.sync_jobs.append(job_id)
            existing_manifest.updated_at = now
            await self._storage.write_json(manifest_path, existing_manifest.model_dump())
        else:
            manifest = SyncManifest(
                sync_id=sync_id,
                source_short_name=self._get_source_short_name(sync_context, runtime),
                collection_id=str(sync_context.collection.id),
                collection_readable_id=sync_context.collection.readable_id,
                organization_id=str(sync_context.collection.organization_id),
                created_at=now,
                updated_at=now,
                sync_jobs=[job_id],
                vector_size=runtime.dense_embedder.dimensions,
                embedding_model_name=runtime.dense_embedder.model_name,
            )
            await self._storage.write_json(manifest_path, manifest.model_dump())

    # =========================================================================
    # Store management
    # =========================================================================

    async def list_syncs(self) -> List[str]:
        """List all sync IDs with ARF stores."""
        try:
            dirs = await self._storage.list_dirs("raw")
            return [d.split("/")[-1] for d in dirs]
        except Exception:
            return []

    async def sync_exists(self, sync_id: str) -> bool:
        """Check if an ARF store exists for a sync."""
        return await self._storage.exists(self._manifest_path(sync_id))

    async def delete_sync(self, sync_id: str) -> bool:
        """Delete entire ARF store for a sync."""
        return await self._storage.delete(self._sync_path(sync_id))

    async def get_entity_count(self, sync_id: str) -> int:
        """Count entities in store."""
        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            return await self._storage.count_files(entities_dir, pattern="*.json")
        except Exception:
            return 0

    async def get_replay_stats(self, sync_id: str) -> Dict[str, Any]:
        """Get stats for a potential replay operation."""
        manifest = await self.get_manifest(sync_id)
        if not manifest:
            return {"exists": False}

        entity_count = await self.get_entity_count(sync_id)
        return {
            "exists": True,
            "sync_id": manifest.sync_id,
            "source": manifest.source_short_name,
            "entity_count": entity_count,
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "sync_jobs": manifest.sync_jobs,
        }

    # =========================================================================
    # Private helpers
    # =========================================================================

    async def _list_entity_ids(self, sync_id: str) -> List[str]:
        """List all entity IDs in a sync's ARF store."""
        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            files = await self._storage.list_files(entities_dir)
        except Exception:
            return []

        entity_ids: List[str] = []
        for file_path in files:
            if file_path.endswith(".json"):
                try:
                    entity_dict = await self._storage.read_json(file_path)
                    entity_id = entity_dict.get("entity_id")
                    if entity_id:
                        entity_ids.append(str(entity_id))
                except Exception:
                    continue
        return entity_ids
