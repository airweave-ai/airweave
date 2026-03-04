"""Centralized entity state tracker for sync operations.

EntityTracker is the single source of truth for entity state during sync:
- Tracks entities encountered (for deduplication and orphan detection)
- Tracks entity counts by definition (for state queries)
- Tracks global operation counts (inserted, updated, deleted, kept, skipped)

This is a PURE STATE TRACKER - it does NOT handle event publishing.
Event publishing is handled by the per-sync EventBus via SyncProgressRelay.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set
from uuid import UUID

from airweave.schemas.entity_count import EntityCountWithDefinition

if TYPE_CHECKING:
    from airweave.core.logging import ContextualLogger


@dataclass
class SyncStats:
    """Global sync statistics."""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    entities_encountered: Dict[str, int] = field(default_factory=dict)
    total_operations: int = 0


class EntityTracker:
    """Single source of truth for entity state during sync.

    Responsibilities:
    - Track entities encountered by type (for deduplication & orphan detection)
    - Track total entity counts by definition (for state queries)
    - Track global progress stats
    - Provide atomic operations for concurrent access

    NOT responsible for:
    - Event publishing (handled by EventBus via SyncProgressRelay)
    - Sync finalization (handled by orchestrator via SyncProgressRelay)

    Thread-safety: All mutation methods use async locks for concurrent batch processing.
    """

    def __init__(
        self,
        job_id: UUID,
        sync_id: UUID,
        logger: "ContextualLogger",
        initial_counts: Optional[List[EntityCountWithDefinition]] = None,
    ):
        """Initialize the entity tracker.

        Args:
            job_id: The sync job ID
            sync_id: The sync ID
            logger: Contextual logger for debugging
            initial_counts: Initial entity counts from database (for existing syncs)
        """
        self.job_id = job_id
        self.sync_id = sync_id
        self.logger = logger

        # Global stats (single source of truth)
        self.stats = SyncStats()

        # Entity encounter tracking (for dedup + orphan detection)
        # The set tracks IDs, stats.entities_encountered tracks counts
        self._encountered_by_type: Dict[str, Set[str]] = defaultdict(set)

        # Entity count tracking
        self._counts_by_definition: Dict[UUID, int] = {}
        self._definition_metadata: Dict[UUID, Dict] = {}

        # Initialize with database counts if provided
        if initial_counts:
            for count in initial_counts:
                self._counts_by_definition[count.entity_definition_id] = count.count
                self._definition_metadata[count.entity_definition_id] = {
                    "name": count.entity_definition_name,
                    "type": count.entity_definition_type,
                    "description": count.entity_definition_description,
                }
                self.logger.debug(
                    f"📚 Loaded initial count for {count.entity_definition_name}: {count.count}"
                )

        # Concurrency control
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Entity Encounter Tracking (for dedup + orphan detection)
    # -------------------------------------------------------------------------

    async def track_entity(self, entity_type: str, entity_id: str) -> bool:
        """Track an entity as encountered. Returns True if new, False if duplicate.

        This is the FIRST operation in the pipeline for each entity.
        Thread-safe: uses async lock for concurrent batch processing.

        Args:
            entity_type: The entity class name (e.g., "AsanaTaskEntity")
            entity_id: The unique entity ID

        Returns:
            True if this is a new entity (first time encountered)
            False if this is a duplicate (already encountered in this sync)
        """
        async with self._lock:
            if entity_id in self._encountered_by_type[entity_type]:
                return False  # Duplicate
            self._encountered_by_type[entity_type].add(entity_id)
            # Update stats directly
            self.stats.entities_encountered[entity_type] = (
                self.stats.entities_encountered.get(entity_type, 0) + 1
            )
            return True  # New

    async def track_entities_batch(self, entities: List[tuple]) -> List[tuple]:
        """Track multiple entities and return only the new ones.

        More efficient than calling track_entity in a loop when batch is large.

        Args:
            entities: List of (entity_type, entity_id) tuples

        Returns:
            List of (entity_type, entity_id) tuples that are NEW (not duplicates)
        """
        new_entities = []
        async with self._lock:
            for entity_type, entity_id in entities:
                if entity_id not in self._encountered_by_type[entity_type]:
                    self._encountered_by_type[entity_type].add(entity_id)
                    # Update stats directly
                    self.stats.entities_encountered[entity_type] = (
                        self.stats.entities_encountered.get(entity_type, 0) + 1
                    )
                    new_entities.append((entity_type, entity_id))
        return new_entities

    def get_encountered_ids(self) -> Dict[str, Set[str]]:
        """Get all encountered entity IDs by type (for orphan detection at sync end)."""
        return dict(self._encountered_by_type)

    def get_encountered_count(self) -> Dict[str, int]:
        """Get count of encountered entities by type."""
        return dict(self.stats.entities_encountered)

    def get_all_encountered_ids_flat(self) -> Set[str]:
        """Get all encountered entity IDs as a flat set."""
        all_ids: Set[str] = set()
        for ids in self._encountered_by_type.values():
            all_ids.update(ids)
        return all_ids

    # -------------------------------------------------------------------------
    # Entity Count Tracking & Global Stats
    # -------------------------------------------------------------------------

    async def record_inserts(
        self,
        entity_definition_id: UUID,
        count: int = 1,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> None:
        """Record successful insert(s)."""
        async with self._lock:
            self._ensure_definition(entity_definition_id, entity_name, entity_type)
            self._counts_by_definition[entity_definition_id] += count
            self.stats.inserted += count
            self.stats.total_operations += count

    async def record_updates(
        self,
        entity_definition_id: UUID,
        count: int = 1,
    ) -> None:
        """Record successful update(s)."""
        async with self._lock:
            self.stats.updated += count
            self.stats.total_operations += count

    async def record_deletes(
        self,
        entity_definition_id: UUID,
        count: int = 1,
    ) -> None:
        """Record successful delete(s)."""
        async with self._lock:
            if entity_definition_id in self._counts_by_definition:
                self._counts_by_definition[entity_definition_id] = max(
                    0, self._counts_by_definition[entity_definition_id] - count
                )
            self.stats.deleted += count
            self.stats.total_operations += count

    async def record_kept(self, count: int = 1) -> None:
        """Record kept entity(s) (unchanged)."""
        async with self._lock:
            self.stats.kept += count
            self.stats.total_operations += count

    async def record_skipped(self, count: int = 1) -> None:
        """Record skipped entity(s) (errors/filtered)."""
        async with self._lock:
            self.stats.skipped += count
            self.stats.total_operations += count

    async def record_batch_results(
        self,
        inserts_by_def: Dict[UUID, int],
        updates_by_def: Dict[UUID, int],
        deletes_by_def: Dict[UUID, int],
        keeps_count: int = 0,
        skipped_count: int = 0,
        entity_names: Optional[Dict[UUID, str]] = None,
    ) -> None:
        """Record results for an entire batch at once (more efficient)."""
        async with self._lock:
            total_ops = 0

            # Process inserts
            for def_id, count in inserts_by_def.items():
                name = entity_names.get(def_id) if entity_names else None
                self._ensure_definition(def_id, name)
                self._counts_by_definition[def_id] += count
                self.stats.inserted += count
                total_ops += count

            # Process updates
            for count in updates_by_def.values():
                self.stats.updated += count
                total_ops += count

            # Process deletes
            for def_id, count in deletes_by_def.items():
                if def_id in self._counts_by_definition:
                    self._counts_by_definition[def_id] = max(
                        0, self._counts_by_definition[def_id] - count
                    )
                self.stats.deleted += count
                total_ops += count

            # Keeps and skips
            if keeps_count > 0:
                self.stats.kept += keeps_count
                total_ops += keeps_count

            if skipped_count > 0:
                self.stats.skipped += skipped_count
                total_ops += skipped_count

            self.stats.total_operations += total_ops

    def _ensure_definition(
        self,
        entity_definition_id: UUID,
        name: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> None:
        """Ensure definition exists in tracking."""
        if entity_definition_id not in self._counts_by_definition:
            self._counts_by_definition[entity_definition_id] = 0
            self.logger.debug(f"🆕 New entity definition encountered: {entity_definition_id}")

        if name and entity_definition_id not in self._definition_metadata:
            self._definition_metadata[entity_definition_id] = {
                "name": name,
                "type": entity_type or "unknown",
            }
            self.logger.debug(f"📝 Registered metadata for {entity_definition_id}: {name}")

    # -------------------------------------------------------------------------
    # State Access
    # -------------------------------------------------------------------------

    def get_counts_by_definition(self) -> Dict[UUID, int]:
        """Get raw counts by entity definition ID."""
        return dict(self._counts_by_definition)

    def get_named_counts(self) -> Dict[str, int]:
        """Get entity counts with cleaned names for display."""
        counts_named = {}
        for def_id, count in self._counts_by_definition.items():
            if def_id in self._definition_metadata:
                name = self._definition_metadata[def_id]["name"]
                # Clean entity name (remove "Entity" suffix)
                clean_name = name.replace("Entity", "").strip()
                if clean_name:
                    counts_named[clean_name] = count
            else:
                # Fallback to UUID string
                counts_named[str(def_id)] = count
        return counts_named

    def get_total_entities(self) -> int:
        """Get total entity count across all definitions."""
        return sum(self._counts_by_definition.values())

    def get_total_operations(self) -> int:
        """Get total number of operations processed."""
        return self.stats.total_operations

    def get_stats(self) -> SyncStats:
        """Get global sync statistics."""
        return self.stats

    def get_current_state(self) -> SyncStats:
        """Get current state snapshot for debugging/testing."""
        return self.stats
