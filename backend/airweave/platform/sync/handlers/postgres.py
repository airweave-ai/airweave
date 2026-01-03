"""PostgreSQL metadata handler for entity persistence.

Stores entity metadata (entity_id, hash, definition_id) to PostgreSQL.
This handler is SPECIAL: it runs AFTER all other handlers succeed to ensure
consistency between vector stores and metadata.
"""

import asyncio
from typing import TYPE_CHECKING, Dict, List, Tuple
from uuid import UUID

from airweave import crud, schemas
from airweave.core.shared_models import ActionType
from airweave.db.session import get_db_context
from airweave.platform.sync.actions.types import (
    ActionBatch,
    DeleteAction,
    InsertAction,
    UpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.base import ActionHandler

if TYPE_CHECKING:
    from airweave.platform.sync.context import SyncContext


class PostgresMetadataHandler(ActionHandler):
    """Handler for PostgreSQL entity metadata.

    Stores entity records with:
    - entity_id: Unique identifier from source
    - entity_definition_id: Type classification
    - hash: Content hash for change detection
    - sync_id, sync_job_id: Sync tracking

    IMPORTANT: This handler should run AFTER destination handlers succeed.
    The dispatcher calls this handler separately, not concurrently with others.
    """

    @property
    def name(self) -> str:
        """Handler name."""
        return "postgres_metadata"

    async def handle_batch(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Handle full batch in a single transaction.

        Overrides default to process all operations in one transaction
        for better performance and atomicity.

        Args:
            batch: ActionBatch with all resolved actions
            sync_context: Sync context
        """
        if not batch.has_mutations:
            return

        # Execute with deadlock retry
        await self._execute_with_retry(batch, sync_context)

        # Increment guard rail usage
        total_synced = len(batch.inserts) + len(batch.updates)
        if total_synced > 0:
            await sync_context.guard_rail.increment(ActionType.ENTITIES, amount=total_synced)
            sync_context.logger.debug(f"[Postgres] Incremented guard_rail by {total_synced}")

    async def _execute_with_retry(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
        max_retries: int = 3,
    ) -> None:
        """Execute database operations with deadlock retry.

        Args:
            batch: ActionBatch to persist
            sync_context: Sync context
            max_retries: Maximum retry attempts for deadlocks
        """
        from sqlalchemy.exc import DBAPIError

        for attempt in range(max_retries + 1):
            try:
                await self._execute_operations(batch, sync_context)
                return
            except DBAPIError as e:
                error_msg = str(e).lower()
                is_deadlock = "deadlock detected" in error_msg

                if is_deadlock and attempt < max_retries:
                    wait_time = 0.1 * (2**attempt)
                    sync_context.logger.warning(
                        f"[Postgres] Deadlock detected, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise SyncFailureError(f"[Postgres] Database error: {e}") from e

    async def _execute_operations(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Execute INSERT, UPDATE, DELETE in a single transaction.

        Args:
            batch: ActionBatch to persist
            sync_context: Sync context
        """
        async with get_db_context() as db:
            if batch.inserts:
                await self._execute_inserts(batch.inserts, sync_context, db)

            if batch.updates:
                await self._execute_updates(batch.updates, batch.existing_map, sync_context, db)

            if batch.deletes:
                await self._execute_deletes(batch.deletes, batch.existing_map, sync_context, db)

            await db.commit()

        sync_context.logger.debug(
            f"[Postgres] Persisted {len(batch.inserts)} inserts, "
            f"{len(batch.updates)} updates, {len(batch.deletes)} deletes"
        )

    async def _execute_inserts(
        self,
        actions: List[InsertAction],
        sync_context: "SyncContext",
        db,
    ) -> None:
        """Execute INSERT operations.

        Args:
            actions: Insert actions
            sync_context: Sync context
            db: Database session
        """
        # Deduplicate within batch (keep latest)
        deduped = self._deduplicate_inserts(actions, sync_context)

        if not deduped:
            return

        # Check if hash updates should be skipped
        skip_hashes = (
            sync_context.execution_config and sync_context.execution_config.skip_hash_updates
        )

        # Build create objects with deterministic ordering
        create_objs = []
        for action in deduped:
            if not skip_hashes and not action.entity.airweave_system_metadata.hash:
                raise SyncFailureError(f"Entity {action.entity_id} missing hash")

            create_objs.append(
                schemas.EntityCreate(
                    sync_job_id=sync_context.sync_job.id,
                    sync_id=sync_context.sync.id,
                    entity_id=action.entity_id,
                    entity_definition_id=action.entity_definition_id,
                    hash="" if skip_hashes else action.entity.airweave_system_metadata.hash,
                )
            )

        # Sort to avoid deadlock cycles
        create_objs.sort(key=lambda obj: (obj.entity_definition_id.int, obj.entity_id))

        # Log for debugging
        sample_ids = [obj.entity_id for obj in create_objs[:10]]
        hash_note = " (without hashes)" if skip_hashes else ""
        sync_context.logger.debug(
            f"[Postgres] Upserting {len(create_objs)} inserts{hash_note} (sample: {sample_ids})"
        )

        await crud.entity.bulk_create(db, objs=create_objs, ctx=sync_context.ctx)

    async def _execute_updates(
        self,
        actions: List[UpdateAction],
        existing_map: Dict[Tuple[str, UUID], any],
        sync_context: "SyncContext",
        db,
    ) -> None:
        """Execute UPDATE operations (hash updates).

        Args:
            actions: Update actions
            existing_map: Map of existing DB records
            sync_context: Sync context
            db: Database session
        """
        # Check if hash updates should be skipped
        if sync_context.execution_config and sync_context.execution_config.skip_hash_updates:
            sync_context.logger.info(
                f"[Postgres] Skipping hash updates for {len(actions)} entities (skip_hash_updates=True)"
            )
            return

        update_pairs = []

        for action in actions:
            if not action.entity.airweave_system_metadata.hash:
                raise SyncFailureError(f"Entity {action.entity_id} missing hash")

            key = (action.entity_id, action.entity_definition_id)
            if key not in existing_map:
                raise SyncFailureError(f"UPDATE entity {action.entity_id} not in existing_map")

            db_id = existing_map[key].id
            new_hash = action.entity.airweave_system_metadata.hash
            update_pairs.append((db_id, new_hash))

        if not update_pairs:
            return

        # Sort to avoid deadlocks
        update_pairs.sort(key=lambda pair: pair[0])

        sample_ids = [str(pair[0])[:8] for pair in update_pairs[:10]]
        sync_context.logger.debug(
            f"[Postgres] Updating {len(update_pairs)} hashes (sample: {sample_ids})"
        )

        await crud.entity.bulk_update_hash(db, rows=update_pairs)

    async def _execute_deletes(
        self,
        actions: List[DeleteAction],
        existing_map: Dict[Tuple[str, UUID], any],
        sync_context: "SyncContext",
        db,
    ) -> None:
        """Execute DELETE operations.

        Args:
            actions: Delete actions
            existing_map: Map of existing DB records
            sync_context: Sync context
            db: Database session
        """
        db_ids = []

        for action in actions:
            key = (action.entity_id, action.entity_definition_id)
            if key in existing_map:
                db_ids.append(existing_map[key].id)
            else:
                sync_context.logger.debug(
                    f"DELETE entity {action.entity_id} not in DB (never synced)"
                )

        if not db_ids:
            return

        sync_context.logger.debug(f"[Postgres] Deleting {len(db_ids)} entity records")

        await crud.entity.bulk_remove(db, ids=db_ids, ctx=sync_context.ctx)

    def _deduplicate_inserts(
        self,
        actions: List[InsertAction],
        sync_context: "SyncContext",
    ) -> List[InsertAction]:
        """Deduplicate inserts within batch (keep latest).

        Args:
            actions: Insert actions
            sync_context: Sync context for logging

        Returns:
            Deduplicated list of insert actions
        """
        seen: Dict[str, int] = {}
        deduped: List[InsertAction] = []

        for action in actions:
            if action.entity_id in seen:
                sync_context.logger.debug(
                    f"[Postgres] Duplicate in batch: {action.entity_id} - using latest"
                )
                deduped[seen[action.entity_id]] = action
            else:
                seen[action.entity_id] = len(deduped)
                deduped.append(action)

        if len(deduped) < len(actions):
            sync_context.logger.debug(
                f"[Postgres] Deduplicated {len(actions)} → {len(deduped)} inserts"
            )

        return deduped

    # -------------------------------------------------------------------------
    # Individual handlers (called by default handle_batch)
    # -------------------------------------------------------------------------

    async def handle_inserts(
        self,
        actions: List[InsertAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle insert actions."""
        # Not used when handle_batch is overridden
        pass

    async def handle_updates(
        self,
        actions: List[UpdateAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle update actions."""
        # Not used when handle_batch is overridden
        pass

    async def handle_deletes(
        self,
        actions: List[DeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle delete actions."""
        # Not used when handle_batch is overridden
        pass

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Delete orphaned entity records from PostgreSQL (no-op, handled by CleanupService)."""
        # Orphan cleanup for Postgres is handled separately by CleanupService
        # because it needs the full Entity models for bulk_remove
        pass
