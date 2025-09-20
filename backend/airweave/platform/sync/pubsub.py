"""Sync progress tracking and Redis pubsub integration."""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.core.pubsub import core_pubsub
from airweave.core.shared_models import SyncJobStatus
from airweave.schemas.entity_count import EntityCountWithDefinition
from airweave.schemas.sync_pubsub import EntityStateUpdate, SyncCompleteMessage, SyncProgressUpdate

PUBLISH_THRESHOLD = 3


class SyncProgress:
    """Tracks sync progress and automatically publishes updates."""

    def __init__(self, job_id: UUID, logger: ContextualLogger):
        """Initialize the SyncProgress instance.

        Args:
            job_id: The sync job ID
            logger: Contextual logger with sync metadata
        """
        self.job_id = job_id
        self.stats = SyncProgressUpdate()
        self._last_published = 0
        self._publish_threshold = PUBLISH_THRESHOLD
        # CRITICAL FIX: Add async lock to prevent race conditions
        self._lock = asyncio.Lock()
        self.logger = logger
        self._last_status_update = 0
        self._status_update_interval = 50  # Log status every 50 items

    def __getattr__(self, name: str) -> int:
        """Get counter value for any stat."""
        return getattr(self.stats, name)

    async def increment(self, stat_name: str, amount: int = 1) -> None:
        """Increment a counter and trigger update if threshold reached.

        Uses async lock to prevent race conditions from concurrent workers.
        """
        async with self._lock:  # CRITICAL FIX: Synchronize access
            current_value = getattr(self.stats, stat_name, 0)
            setattr(self.stats, stat_name, current_value + amount)

            # Include ALL operations in threshold calculation (including skipped)
            total_ops = sum(
                [
                    self.stats.inserted,
                    self.stats.updated,
                    self.stats.deleted,
                    self.stats.kept,
                    self.stats.skipped,
                ]
            )

            # Check if we should publish
            if total_ops - self._last_published >= self._publish_threshold:
                self.logger.debug(
                    f"Progress threshold reached: {total_ops} total ops, publishing update"
                )
                await self._publish()
                self._last_published = total_ops

            # Check if we should log a status update (every 50 items)
            if total_ops - self._last_status_update >= self._status_update_interval:
                await self._log_status_update(total_ops)
                self._last_status_update = total_ops

    async def _publish(self) -> None:
        """Publish current progress."""
        await core_pubsub.publish("sync_job", self.job_id, self.stats.model_dump())

    async def finalize(self, is_complete: bool = True) -> None:
        """Publish final progress."""
        async with self._lock:  # Ensure finalize is also synchronized
            self.stats.is_complete = is_complete
            self.stats.is_failed = not is_complete

            # Log final status
            total_ops = sum(
                [
                    self.stats.inserted,
                    self.stats.updated,
                    self.stats.deleted,
                    self.stats.kept,
                    self.stats.skipped,
                ]
            )

            if is_complete:
                self.logger.info(
                    f"✅ Sync completed successfully - Total: {total_ops} | "
                    f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
                    f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
                    f"Skipped: {self.stats.skipped}"
                )
            else:
                self.logger.error(
                    f"❌ Sync failed - Progress before failure - Total: {total_ops} | "
                    f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
                    f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
                    f"Skipped: {self.stats.skipped}"
                )

            await self._publish()

    def to_dict(self) -> dict:
        """Convert progress to a dictionary."""
        return self.stats.model_dump()

    async def update_entities_encountered_count(
        self, entities_encountered: dict[str, set[str]]
    ) -> None:
        """Update the entities encountered tracking."""
        async with self._lock:  # Synchronize this as well
            self.stats.entities_encountered = {
                entity_type: len(entity_ids)
                for entity_type, entity_ids in entities_encountered.items()
            }

    async def _log_status_update(self, total_ops: int) -> None:
        """Log a periodic status update.

        Args:
            total_ops: Total operations processed so far
        """
        # Calculate rate if possible
        rate_info = ""
        if hasattr(self, "_start_time"):
            elapsed = asyncio.get_event_loop().time() - self._start_time
            if elapsed > 0:
                rate = total_ops / elapsed
                rate_info = f" | Rate: {rate:.1f} ops/sec"
        else:
            # Set start time on first status update
            self._start_time = asyncio.get_event_loop().time()

        # Log entity type breakdown if available
        entity_info = ""
        if self.stats.entities_encountered:
            entity_summary = ", ".join(
                [
                    f"{entity_type}: {count}"
                    for entity_type, count in self.stats.entities_encountered.items()
                ]
            )
            entity_info = f" | Entities: {entity_summary}"

        self.logger.info(
            f"📊 Sync progress - Total: {total_ops} | "
            f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
            f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
            f"Skipped: {self.stats.skipped}{rate_info}{entity_info}"
        )


class SyncEntityStateTracker:
    """Tracks total entity counts during sync, publishing absolute values.

    This tracker maintains the total count of entities per type during a sync,
    publishing updates to Redis for real-time monitoring. Unlike the differential
    progress tracker, this publishes absolute totals.
    """

    def __init__(
        self,
        job_id: UUID,
        sync_id: UUID,
        initial_counts: List[EntityCountWithDefinition],
        logger: ContextualLogger,
    ):
        """Initialize the entity state tracker.

        Args:
            job_id: The sync job ID
            sync_id: The sync ID
            initial_counts: Initial entity counts from the database
            logger: Contextual logger for debugging
        """
        self.job_id = job_id
        self.sync_id = sync_id
        self.logger = logger

        # Initialize with database counts
        self.entity_counts: Dict[UUID, int] = {
            count.entity_definition_id: count.count for count in initial_counts
        }

        # Track entity definition metadata for name resolution
        self.entity_metadata: Dict[UUID, Dict] = {}
        for count in initial_counts:
            self.entity_metadata[count.entity_definition_id] = {
                "name": count.entity_definition_name,
                "type": count.entity_definition_type,
                "description": count.entity_definition_description,
            }
            self.logger.info(
                f"📚 Loaded metadata for {count.entity_definition_id}: "
                f"{count.entity_definition_name} (count={count.count})"
            )

        # Publishing control
        self._lock = asyncio.Lock()
        self._last_published = datetime.utcnow()
        self._publish_interval = 0.5  # Publish every 500ms max

        # Track the total operations for debugging
        self._total_operations = 0

    async def update_entity_count(
        self,
        entity_definition_id: UUID,
        action: str,  # 'insert', 'update', 'delete'
        delta: int = 1,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_description: Optional[str] = None,
    ) -> None:
        """Update entity count based on action.

        Args:
            entity_definition_id: The entity definition ID
            action: The action performed ('insert', 'update', 'delete')
            delta: The number of entities affected (default: 1)
            entity_name: The entity definition name (for new entity types)
            entity_type: The entity definition type (for new entity types)
            entity_description: The entity definition description (for new entity types)
        """
        async with self._lock:
            # Initialize count if this is a new entity type
            if entity_definition_id not in self.entity_counts:
                self.entity_counts[entity_definition_id] = 0
                self.logger.info(
                    f"🆕 New entity type encountered: {entity_definition_id}, name={entity_name}"
                )

            # Always update or register metadata if entity_name is provided
            # This handles cases where initial_counts might be empty or incomplete
            if entity_name and entity_definition_id not in self.entity_metadata:
                self.entity_metadata[entity_definition_id] = {
                    "name": entity_name,
                    "type": entity_type or "unknown",
                    "description": entity_description or "",
                }
                self.logger.info(
                    f"📝 Registered metadata for entity {entity_definition_id}: {entity_name}"
                )

            # Log the action for debugging
            old_count = self.entity_counts[entity_definition_id]

            # Update count based on action
            # Note: 'update' actions don't change the total count
            if action == "insert":
                self.entity_counts[entity_definition_id] += delta
                self._total_operations += 1
            elif action == "delete":
                self.entity_counts[entity_definition_id] = max(
                    0, self.entity_counts[entity_definition_id] - delta
                )
                self._total_operations += 1
            elif action == "update":
                # Updates don't change the count, just track the operation
                self._total_operations += 1

            new_count = self.entity_counts[entity_definition_id]
            entity_name_display = self.entity_metadata.get(entity_definition_id, {}).get(
                "name", str(entity_definition_id)
            )
            self.logger.debug(
                f"🔢 Entity count update: {entity_name_display} - action={action}, "
                f"count: {old_count} → {new_count}, total_ops={self._total_operations}"
            )

            # Check if we should publish based on time interval
            now = datetime.utcnow()
            if (now - self._last_published).total_seconds() >= self._publish_interval:
                await self._publish_state()
                self._last_published = now

    async def _publish_state(self) -> None:
        """Publish current total state to Redis."""
        # Debug log the current state
        self.logger.debug(
            f"📊 Publishing state - entity_counts has {len(self.entity_counts)} types, "
            f"metadata has {len(self.entity_metadata)} types"
        )

        # Build entity counts with clean names
        entity_counts_named = {}
        for def_id, count in self.entity_counts.items():
            if def_id in self.entity_metadata:
                name = self.entity_metadata[def_id]["name"]
                # Clean entity name (remove "Entity" suffix if present)
                clean_name = name.replace("Entity", "").strip()
                if clean_name:  # Only add if name is not empty
                    entity_counts_named[clean_name] = count
            else:
                # If we don't have metadata, use the UUID as a fallback
                # This ensures ALL entities are counted in the breakdown
                self.logger.warning(
                    f"⚠️ No metadata for entity {def_id} (count={count}), using ID as name"
                )
                entity_counts_named[str(def_id)] = count

        # Calculate total entities
        total_entities = sum(self.entity_counts.values())

        # Create properly typed state update
        state_update = EntityStateUpdate(
            job_id=self.job_id,
            sync_id=self.sync_id,
            entity_counts=entity_counts_named,
            total_entities=total_entities,
            job_status=SyncJobStatus.RUNNING,  # Always RUNNING during updates
        )

        try:
            # Use the new core_pubsub with "sync_job_state" namespace
            subscribers = await core_pubsub.publish(
                "sync_job_state", self.job_id, state_update.model_dump_json()
            )

            self.logger.debug(
                f"✅ Published entity state to {subscribers} subscribers: {entity_counts_named}"
            )
        except Exception as e:
            self.logger.error(f"Failed to publish entity state: {e}")

    async def finalize(self, is_complete: bool = True, error: Optional[str] = None) -> None:
        """Publish final state with completion flag.

        Args:
            is_complete: Whether the sync completed successfully
            error: Error message if the sync failed
        """
        async with self._lock:
            # Always publish final state
            await self._publish_state()

            # Build final counts with names for the completion message
            final_counts_named = {}
            for def_id, count in self.entity_counts.items():
                if def_id in self.entity_metadata:
                    name = self.entity_metadata[def_id]["name"]
                    clean_name = name.replace("Entity", "").strip()
                    if clean_name:
                        final_counts_named[clean_name] = count
                else:
                    # Include entities without metadata using UUID as name
                    final_counts_named[str(def_id)] = count

            # Send completion message with proper status
            final_status = SyncJobStatus.COMPLETED if is_complete else SyncJobStatus.FAILED

            completion_msg = SyncCompleteMessage(
                job_id=self.job_id,
                sync_id=self.sync_id,
                is_complete=is_complete,
                is_failed=not is_complete,
                final_counts=final_counts_named,
                total_entities=sum(self.entity_counts.values()),
                total_operations=self._total_operations,
                final_status=final_status,
                error=error,  # Include the error message
            )

            try:
                await core_pubsub.publish(
                    "sync_job_state", self.job_id, completion_msg.model_dump_json()
                )

                self.logger.info(
                    f"Sync finalized: {'completed' if is_complete else 'failed'}, "
                    f"{sum(self.entity_counts.values())} total entities, "
                    f"{self._total_operations} operations"
                )
            except Exception as e:
                self.logger.error(f"Failed to publish completion message: {e}")

    def get_current_state(self) -> Dict:
        """Get the current state snapshot.

        Returns:
            Dictionary with current entity counts and metadata
        """
        entity_counts_named = {}
        for def_id, count in self.entity_counts.items():
            if def_id in self.entity_metadata:
                name = self.entity_metadata[def_id]["name"]
                clean_name = name.replace("Entity", "").strip()
                if clean_name:
                    entity_counts_named[clean_name] = count
            else:
                # Include entities without metadata using UUID as name
                entity_counts_named[str(def_id)] = count

        return {
            "entity_counts": entity_counts_named,
            "total_entities": sum(self.entity_counts.values()),
            "total_operations": self._total_operations,
            "job_id": str(self.job_id),
            "sync_id": str(self.sync_id),
        }
