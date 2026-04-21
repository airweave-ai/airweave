"""Source-hash lookup for skipping unnecessary file downloads.

When a source provides a content hash from its API (e.g. SHA256 from
Google Drive), unchanged files can be identified before downloading.
This service prefetches stored hash data for a sync and provides O(1)
lookups for the source connector.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import ContextualLogger
from airweave.domains.sync_pipeline.pipeline.entity_hasher import compute_entity_hash
from airweave.models.entity import Entity
from airweave.platform.entities._base import FileEntity


@dataclass(frozen=True, slots=True)
class StoredEntityHashes:
    """Cached hash data for a single entity from the previous sync."""

    source_hash: str
    content_hash: Optional[str]
    composite_hash: str


class SourceHashLookup:
    """Check stored hashes to skip unnecessary downloads."""

    def __init__(self, sync_id: UUID, logger: ContextualLogger) -> None:
        self._sync_id = sync_id
        self._logger = logger
        self._cache: Dict[str, StoredEntityHashes] = {}
        self._prefetched = False

    async def prefetch(self, db: AsyncSession) -> None:
        """Prefetch all hash data for this sync into memory.

        For syncs with >1M entities this uses ~100-200MB. For most syncs
        it is much less. Logs a warning when the cache exceeds 500K entries.
        """
        stmt = select(
            Entity.entity_id,
            Entity.source_hash,
            Entity.content_hash,
            Entity.hash,
        ).where(
            Entity.sync_id == self._sync_id,
            Entity.source_hash.isnot(None),
        )
        result = await db.execute(stmt)
        for row in result:
            self._cache[row.entity_id] = StoredEntityHashes(
                source_hash=row.source_hash,
                content_hash=row.content_hash,
                composite_hash=row.hash,
            )

        self._prefetched = True

        if len(self._cache) > 500_000:
            self._logger.warning(
                f"SourceHashLookup cache has {len(self._cache)} entries — "
                f"consider batch lookups for very large syncs"
            )
        elif self._cache:
            self._logger.debug(
                f"SourceHashLookup prefetched {len(self._cache)} source hashes"
            )

    def is_unchanged(self, entity_id: str, source_hash: str) -> bool:
        """Check if entity's source_hash matches the stored value.

        Used by the pipeline for content_hash reuse. Returns False if
        not prefetched, entity not found, or source_hash doesn't match.
        """
        if not self._prefetched or not source_hash:
            return False
        stored = self._cache.get(entity_id)
        return stored is not None and stored.source_hash == source_hash

    def should_skip_download(self, entity: FileEntity) -> bool:
        """Check if both content and metadata are unchanged.

        Computes a trial composite hash from the entity's current metadata
        plus the stored content_hash. If it matches the stored composite,
        nothing has changed and the download can be safely skipped.

        Note: mutates the entity by populating derived fields (entity_id,
        name, created_at, updated_at from flagged source fields) via
        ``populate_derived_fields``. This is idempotent and the pipeline
        performs the same population later.

        Returns False (do not skip) when:
        - Entity not in cache (first sync)
        - source_hash differs (content changed)
        - No stored content_hash
        - Trial composite differs from stored (metadata changed)
        """
        if not self._prefetched:
            return False

        source_hash = getattr(entity, "source_hash", None)
        entity_id = entity.entity_id
        if not source_hash or not entity_id:
            return False

        stored = self._cache.get(entity_id)
        if not stored:
            return False

        if stored.source_hash != source_hash:
            return False

        if not stored.content_hash:
            return False

        trial = compute_entity_hash(entity, content_hash=stored.content_hash)
        return trial == stored.composite_hash

    def get_stored_content_hash(self, entity_id: str) -> Optional[str]:
        """Get stored content_hash for an entity (pipeline reuse)."""
        stored = self._cache.get(entity_id)
        return stored.content_hash if stored else None
