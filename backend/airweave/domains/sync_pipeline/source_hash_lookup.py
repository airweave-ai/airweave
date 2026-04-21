"""Source-hash lookup for skipping unnecessary file downloads.

When a source provides a content hash from its API (e.g. SHA256 from
Google Drive), unchanged files can be identified before downloading.
This service prefetches stored source_hash values for a sync and
provides O(1) lookups for the source connector.
"""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import ContextualLogger
from airweave.models.entity import Entity


class SourceHashLookup:
    """Check stored source_hash to skip unnecessary downloads."""

    def __init__(self, sync_id: UUID, logger: ContextualLogger) -> None:
        self._sync_id = sync_id
        self._logger = logger
        self._cache: Dict[str, str] = {}  # entity_id -> source_hash
        self._prefetched = False

    async def prefetch(self, db: AsyncSession) -> None:
        """Prefetch all source_hashes for this sync into memory.

        For syncs with >1M entities this uses ~50-100MB. For most syncs
        it is much less. Logs a warning when the cache exceeds 500K entries.
        """
        stmt = select(
            Entity.entity_id,
            Entity.source_hash,
        ).where(
            Entity.sync_id == self._sync_id,
            Entity.source_hash.isnot(None),
        )
        result = await db.execute(stmt)
        for row in result:
            self._cache[row.entity_id] = row.source_hash

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

        Must call prefetch() first. Returns False if not prefetched,
        entity not found, or source_hash doesn't match.
        """
        if not self._prefetched or not source_hash:
            return False
        stored = self._cache.get(entity_id)
        return stored is not None and stored == source_hash
