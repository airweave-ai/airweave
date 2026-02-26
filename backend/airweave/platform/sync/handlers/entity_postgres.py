"""PostgreSQL metadata handler for entity persistence.

Stores entity metadata (entity_id, hash, definition_id) to PostgreSQL.
This handler runs AFTER destination handlers to ensure consistency.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.shared_models import ActionType
from airweave.db.session import get_db_context
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


class EntityPostgresHandler(EntityActionHandler):
    """Handler for PostgreSQL entity metadata.

    Stores entity records with:
    - entity_id: Unique identifier from source
    - entity_definition_id: Type classification
    - hash: Content hash for change detection
    - sync_id, sync_job_id: Sync tracking

    Runs AFTER destination handlers succeed (dispatcher handles ordering).
    """

    def __init__(self, guard_rail=None):
        """Initialize with optional guard rail service.

        Args:
            guard_rail: GuardRailService for usage tracking (injected by factory)
        """
        self._guard_rail = guard_rail

    @property
    def name(self) -> str:
        """Handler name."""
        return "entity_postgres_metadata"

    # -------------------------------------------------------------------------
    # Protocol: Public Interface
    # -------------------------------------------------------------------------

    async def handle_batch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle full batch in a single transaction."""
        if not batch.has_mutations:
            return

        await self._do_batch_with_retry(batch, sync_context)

        # Update guard rail (unless explicitly skipped)
        skip_guardrails = (
            sync_context.execution_config
            and sync_context.execution_config.behavior
            and sync_context.execution_config.behavior.skip_guardrails
        )
        if not skip_guardrails:
            total_synced = len(batch.inserts) + len(batch.updates)
            if total_synced > 0:
                await self._guard_rail.increment(ActionType.ENTITIES, amount=total_synced)
                sync_context.logger.debug(f"[EntityPostgres] guard_rail += {total_synced}")

    async def handle_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle inserts - create entity records."""
        if not actions:
            return
        async with get_db_context() as db:
            await self._do_inserts(actions, sync_context, db)
            await db.commit()
        sync_context.logger.debug(f"[EntityPostgres] Inserted {len(actions)} entities")

    async def handle_updates(
        self,
        actions: List[EntityUpdateAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle updates - update entity hashes."""
        if not actions:
            return
        async with get_db_context() as db:
            existing_map = await self._fetch_existing_map(actions, sync_context, db)
            await self._do_updates(actions, existing_map, sync_context, db)
            await db.commit()
        sync_context.logger.debug(f"[EntityPostgres] Updated {len(actions)} entities")

    async def handle_deletes(
        self,
        actions: List[EntityDeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle deletes - remove entity records."""
        if not actions:
            return
        async with get_db_context() as db:
            existing_map = await self._fetch_existing_map(actions, sync_context, db)
            await self._do_deletes(actions, existing_map, sync_context, db)
            await db.commit()
        sync_context.logger.debug(f"[EntityPostgres] Deleted {len(actions)} entities")

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Delete orphaned entity records from PostgreSQL."""
        if not orphan_entity_ids:
            return
        await self._do_orphan_cleanup(orphan_entity_ids, sync_context)

    # -------------------------------------------------------------------------
    # Private: Batch Operations
    # -------------------------------------------------------------------------

    async def _do_batch_with_retry(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
        max_retries: int = 3,
    ) -> None:
        """Execute batch with deadlock retry."""
        from sqlalchemy.exc import DBAPIError

        for attempt in range(max_retries + 1):
            try:
                await self._do_batch(batch, sync_context)
                return
            except DBAPIError as e:
                if "deadlock detected" in str(e).lower() and attempt < max_retries:
                    wait = 0.1 * (2**attempt)
                    sync_context.logger.warning(
                        f"[EntityPostgres] Deadlock, retry in {wait}s ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise SyncFailureError(f"[EntityPostgres] Database error: {e}") from e

    async def _do_batch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Execute INSERT, UPDATE, DELETE in single transaction."""
        async with get_db_context() as db:
            if batch.inserts:
                await self._do_inserts(batch.inserts, sync_context, db)
            if batch.updates:
                await self._do_updates(batch.updates, batch.existing_map, sync_context, db)
            if batch.deletes:
                await self._do_deletes(batch.deletes, batch.existing_map, sync_context, db)
            await db.commit()

        sync_context.logger.debug(
            f"[EntityPostgres] Persisted {len(batch.inserts)}I/"
            f"{len(batch.updates)}U/{len(batch.deletes)}D"
        )

    async def _do_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> None:
        """Execute INSERT operations."""
        deduped = self._deduplicate_inserts(actions, sync_context)
        if not deduped:
            return

        create_objs = []
        for action in deduped:
            if not action.entity.airweave_system_metadata.hash:
                raise SyncFailureError(f"Entity {action.entity_id} missing hash")
            create_objs.append(
                schemas.EntityCreate(
                    sync_job_id=sync_context.sync_job.id,
                    sync_id=sync_context.sync.id,
                    entity_id=action.entity_id,
                    entity_definition_id=action.entity_definition_id,
                    hash=action.entity.airweave_system_metadata.hash,
                )
            )

        # Sort to avoid deadlocks
        create_objs.sort(key=lambda o: (o.entity_definition_id.int, o.entity_id))

        sample_ids = [o.entity_id for o in create_objs[:5]]
        sync_context.logger.debug(
            f"[EntityPostgres] Upserting {len(create_objs)} (sample: {sample_ids})"
        )
        await crud.entity.bulk_create(db, objs=create_objs, ctx=sync_context)

    async def _do_updates(
        self,
        actions: List[EntityUpdateAction],
        existing_map: Dict[Tuple[str, UUID], Any],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> None:
        """Execute UPDATE operations (hash updates)."""
        update_pairs = []
        for action in actions:
            if not action.entity.airweave_system_metadata.hash:
                raise SyncFailureError(f"Entity {action.entity_id} missing hash")

            key = (action.entity_id, action.entity_definition_id)
            if key not in existing_map:
                raise SyncFailureError(f"UPDATE entity {action.entity_id} not in existing_map")

            update_pairs.append((existing_map[key].id, action.entity.airweave_system_metadata.hash))

        if not update_pairs:
            return

        update_pairs.sort(key=lambda p: p[0])
        sync_context.logger.debug(f"[EntityPostgres] Updating {len(update_pairs)} hashes")
        await crud.entity.bulk_update_hash(db, rows=update_pairs)

    async def _do_deletes(
        self,
        actions: List[EntityDeleteAction],
        existing_map: Dict[Tuple[str, UUID], Any],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> None:
        """Execute DELETE operations."""
        db_ids = []
        for action in actions:
            key = (action.entity_id, action.entity_definition_id)
            if key in existing_map:
                db_ids.append(existing_map[key].id)
            else:
                sync_context.logger.debug(f"DELETE {action.entity_id} not in DB (never synced)")

        if not db_ids:
            return

        sync_context.logger.debug(f"[EntityPostgres] Deleting {len(db_ids)} records")
        await crud.entity.bulk_remove(db, ids=db_ids, ctx=sync_context)

    # -------------------------------------------------------------------------
    # Private: Orphan Cleanup
    # -------------------------------------------------------------------------

    async def _do_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Delete orphaned entity records."""
        sync_context.logger.info(f"[EntityPostgres] Cleaning {len(orphan_entity_ids)} orphans")

        async with get_db_context() as db:
            entity_map = await crud.entity.bulk_get_by_entity_and_sync(
                db=db,
                entity_ids=orphan_entity_ids,
                sync_id=sync_context.sync.id,
            )

            if not entity_map:
                sync_context.logger.debug("[EntityPostgres] No orphans found in DB")
                return

            db_ids = [e.id for e in entity_map.values()]
            await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context)
            await db.commit()

            sync_context.logger.info(f"[EntityPostgres] Deleted {len(db_ids)} orphan records")

    # -------------------------------------------------------------------------
    # Private: Helpers
    # -------------------------------------------------------------------------

    async def _fetch_existing_map(
        self,
        actions: List[EntityUpdateAction] | List[EntityDeleteAction],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> Dict[Tuple[str, UUID], Any]:
        """Fetch existing DB records for update/delete actions."""
        entity_requests = [(a.entity_id, a.entity_definition_id) for a in actions]
        return await crud.entity.bulk_get_by_entity_sync_and_definition(
            db=db, sync_id=sync_context.sync.id, entity_requests=entity_requests
        )

    def _deduplicate_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
    ) -> List[EntityInsertAction]:
        """Deduplicate inserts within batch (keep latest)."""
        seen: Dict[str, int] = {}
        deduped: List[EntityInsertAction] = []

        for action in actions:
            if action.entity_id in seen:
                sync_context.logger.debug(
                    f"[EntityPostgres] Dup: {action.entity_id} - using latest"
                )
                deduped[seen[action.entity_id]] = action
            else:
                seen[action.entity_id] = len(deduped)
                deduped.append(action)

        if len(deduped) < len(actions):
            sync_context.logger.debug(f"[EntityPostgres] Deduped {len(actions)} → {len(deduped)}")

        return deduped
