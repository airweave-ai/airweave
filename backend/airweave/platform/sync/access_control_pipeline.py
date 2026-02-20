"""Pipeline for access control membership processing.

Supports two sync modes:
1. Full sync: Collect all memberships from source, upsert, detect + delete orphans
2. Incremental sync: Apply DirSync delta changes (adds/removes) without orphan cleanup

The pipeline decides which mode to use based on the source's capabilities and cursor state.
After a full sync, it seeds a DirSync cookie for future incremental syncs.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Set, Tuple

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.access_control.schemas import (
    ACLChangeType,
    MembershipTuple,
)
from airweave.platform.sync.actions.access_control import ACActionDispatcher, ACActionResolver
from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker
from airweave.platform.utils.error_utils import get_error_message

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


class AccessControlPipeline:
    """Orchestrates membership processing with full and incremental sync support.

    Full sync path:
    1. Collect all memberships from source
    2. Dedupe + resolve + dispatch (upsert to Postgres)
    3. Delete orphan memberships (revoked permissions)
    4. Seed DirSync cookie for future incremental syncs

    Incremental sync path:
    1. Call source.get_acl_changes() with DirSync cookie
    2. Apply ADD changes (upsert) and REMOVE changes (delete by key)
    3. Update cursor with new DirSync cookie
    """

    def __init__(
        self,
        resolver: ACActionResolver,
        dispatcher: ACActionDispatcher,
        tracker: ACLMembershipTracker,
    ):
        """Initialize pipeline with injected components."""
        self._resolver = resolver
        self._dispatcher = dispatcher
        self._tracker = tracker

    async def process(
        self,
        source,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> int:
        """Process access control memberships from the source.

        Decides between full and incremental sync based on source capabilities
        and cursor state, then delegates to the appropriate path.

        Args:
            source: Source instance (e.g. SharePoint2019V2Source)
            sync_context: Sync context with cursor, IDs, logger
            runtime: Sync runtime with live services

        Returns:
            Number of memberships processed
        """
        if self._should_do_incremental_sync(source, sync_context, runtime):
            return await self._process_incremental(source, sync_context, runtime)
        else:
            return await self._process_full(source, sync_context, runtime)

    # -------------------------------------------------------------------------
    # Sync mode decision
    # -------------------------------------------------------------------------

    def _should_do_incremental_sync(
        self, source, sync_context: "SyncContext", runtime: "SyncRuntime"
    ) -> bool:
        """Determine if incremental ACL sync is possible.

        Requires:
        - Source supports incremental ACL (has get_acl_changes + supports_incremental_acl)
        - A DirSync cookie exists in the cursor
        - Not a forced full sync
        """
        # Check source has incremental ACL support
        if not hasattr(source, "supports_incremental_acl"):
            return False
        if not source.supports_incremental_acl():
            return False

        # Check we have a DirSync cookie from a previous sync
        cursor_data = runtime.cursor.data if runtime.cursor else {}
        if not cursor_data.get("acl_dirsync_cookie"):
            sync_context.logger.info("No DirSync cookie found -- will do full ACL sync")
            return False

        # Check not forced full sync
        if getattr(sync_context, "force_full_sync", False):
            sync_context.logger.info("Force full sync requested -- skipping incremental ACL")
            return False

        return True

    # -------------------------------------------------------------------------
    # Full ACL sync (existing logic + DirSync cookie seeding)
    # -------------------------------------------------------------------------

    async def _process_full(  # noqa: C901
        self, source, sync_context: "SyncContext", runtime: "SyncRuntime"
    ) -> int:
        """Full ACL sync: stream memberships to DB in batches, then cleanup orphans.

        Memberships are deduped and written to PostgreSQL in batches as they
        stream from the source. This ensures partial progress is persisted even
        if the sync is interrupted. Orphan cleanup runs after all memberships
        have been collected.

        After completion, seeds a DirSync cookie for future incremental syncs.

        Args:
            source: Source instance
            sync_context: Sync context
            runtime: Sync runtime with live services

        Returns:
            Number of memberships upserted
        """
        sync_context.logger.info("Starting FULL ACL sync")

        BATCH_SIZE = 500
        upserted_count = 0
        total_collected = 0
        batch_buffer: List[MembershipTuple] = []
        collection_complete = False

        if not hasattr(source, "generate_access_control_memberships"):
            sync_context.logger.warning(
                "Source has supports_access_control=True but no "
                "generate_access_control_memberships() method. Skipping."
            )
            return 0

        # Stream memberships from source, dedupe, and write to DB in batches
        try:
            async for membership in source.generate_access_control_memberships():
                total_collected += 1

                # Dedupe via tracker (also records key for orphan detection)
                is_new = self._tracker.track_membership(
                    member_id=membership.member_id,
                    member_type=membership.member_type,
                    group_id=membership.group_id,
                )
                if not is_new:
                    continue

                batch_buffer.append(membership)

                # Flush batch to DB when full
                if len(batch_buffer) >= BATCH_SIZE:
                    upserted_count += await self._flush_batch(batch_buffer, sync_context)
                    batch_buffer = []

                # Progress logging + heartbeat
                if total_collected % 1000 == 0:
                    stats = self._tracker.get_stats()
                    sync_context.logger.debug(
                        f"ACL progress: {total_collected} collected, "
                        f"{stats.encountered} unique, "
                        f"{upserted_count} written to DB"
                    )
                    await runtime.state_publisher.publish_progress()

            collection_complete = True

        except Exception as e:
            sync_context.logger.error(
                f"Error collecting memberships: {get_error_message(e)}",
                exc_info=True,
            )
            # Flush whatever we have in the buffer before giving up
            if batch_buffer:
                upserted_count += await self._flush_batch(batch_buffer, sync_context)
            sync_context.logger.info(
                f"ACL collection failed after {upserted_count} memberships written to DB"
            )
            # Don't do orphan cleanup if collection failed (incomplete data)
            return upserted_count

        # Flush remaining batch
        if batch_buffer:
            upserted_count += await self._flush_batch(batch_buffer, sync_context)

        stats = self._tracker.get_stats()
        sync_context.logger.info(
            f"ACL collection complete: {total_collected} total, "
            f"{stats.encountered} unique, {upserted_count} written to DB "
            f"({stats.duplicates_skipped} duplicates skipped)"
        )

        # Orphan cleanup (only if collection completed successfully)
        if collection_complete:
            deleted_count = await self._cleanup_orphan_memberships(
                sync_context, self._tracker.get_encountered_keys()
            )
            self._tracker.record_deleted(deleted_count)
            if deleted_count > 0:
                sync_context.logger.warning(
                    f"Deleted {deleted_count} orphan ACL memberships (revoked permissions)"
                )

        self._tracker.log_summary()

        # Step 5: Seed DirSync cookie for future incremental syncs
        await self._store_dirsync_cookie_after_full(source, sync_context, runtime)

        return upserted_count

    async def _flush_batch(
        self,
        batch: List[MembershipTuple],
        sync_context: "SyncContext",
    ) -> int:
        """Write a batch of deduplicated memberships to PostgreSQL.

        Uses the resolver/dispatcher pipeline for consistency with
        the existing action architecture.

        Args:
            batch: List of unique MembershipTuple objects to persist.
            sync_context: Sync context.

        Returns:
            Number of memberships upserted.
        """
        if not batch:
            return 0

        resolved = await self._resolver.resolve(batch, sync_context)
        count = await self._dispatcher.dispatch(resolved, sync_context)
        self._tracker.record_upserted(count)
        return count

    # -------------------------------------------------------------------------
    # Incremental ACL sync (DirSync delta changes)
    # -------------------------------------------------------------------------

    async def _process_incremental(
        self, source, sync_context: "SyncContext", runtime: "SyncRuntime"
    ) -> int:
        """Incremental ACL sync: apply DirSync delta changes.

        Calls source.get_acl_changes() with the stored cookie to get only
        changed memberships. Applies ADDs via upsert and REMOVEs via delete.

        Falls back to full sync on failure.

        Args:
            source: Source instance with get_acl_changes()
            sync_context: Sync context
            runtime: Sync runtime with cursor

        Returns:
            Number of changes applied
        """
        cursor_data = runtime.cursor.data if runtime.cursor else {}
        cookie = cursor_data.get("acl_dirsync_cookie", "")

        sync_context.logger.info("Starting INCREMENTAL ACL sync via DirSync")

        try:
            result = await source.get_acl_changes(dirsync_cookie=cookie)
        except Exception as e:
            sync_context.logger.error(
                f"Incremental ACL failed: {get_error_message(e)}. Falling back to full sync.",
                exc_info=True,
            )
            return await self._process_full(source, sync_context, runtime)

        deleted_group_ids = getattr(result, "deleted_group_ids", set())

        if not result.changes and not deleted_group_ids:
            sync_context.logger.info("No ACL changes detected (DirSync returned 0 changes)")
            # Still update cursor with new cookie to advance the position
            self._update_cursor_after_incremental(sync_context, runtime, result)
            return 0

        sync_context.logger.info(
            f"Processing {len(result.changes)} ACL changes "
            f"({len(result.modified_group_ids)} groups modified, "
            f"{len(deleted_group_ids)} groups deleted)"
        )

        adds = 0
        removes = 0
        group_deletes = 0

        async with get_db_context() as db:
            for change in result.changes:
                if change.change_type == ACLChangeType.ADD:
                    await crud.access_control_membership.upsert(
                        db,
                        member_id=change.member_id,
                        member_type=change.member_type,
                        group_id=change.group_id,
                        group_name=change.group_name or "",
                        organization_id=sync_context.organization_id,
                        source_connection_id=sync_context.source_connection_id,
                        source_name=getattr(source, "_short_name", "unknown"),
                    )
                    adds += 1

                elif change.change_type == ACLChangeType.REMOVE:
                    await crud.access_control_membership.delete_by_key(
                        db,
                        member_id=change.member_id,
                        member_type=change.member_type,
                        group_id=change.group_id,
                        source_connection_id=sync_context.source_connection_id,
                        organization_id=sync_context.organization_id,
                    )
                    removes += 1

            # Handle deleted AD groups -- immediately remove all memberships
            # so that revoked access is reflected without waiting for a full sync
            for group_id in deleted_group_ids:
                deleted = await crud.access_control_membership.delete_by_group(
                    db,
                    group_id=group_id,
                    source_connection_id=sync_context.source_connection_id,
                    organization_id=sync_context.organization_id,
                )
                group_deletes += deleted

        if group_deletes > 0:
            sync_context.logger.warning(
                f"Deleted {group_deletes} memberships from "
                f"{len(deleted_group_ids)} deleted AD groups"
            )

        sync_context.logger.info(
            f"Incremental ACL complete: {adds} adds, {removes} removes, "
            f"{group_deletes} group-deletion removals"
        )

        # Update cursor with new DirSync cookie
        self._update_cursor_after_incremental(sync_context, runtime, result)

        return adds + removes + group_deletes

    # -------------------------------------------------------------------------
    # Cursor management
    # -------------------------------------------------------------------------

    def _update_cursor_after_incremental(
        self, sync_context: "SyncContext", runtime: "SyncRuntime", result
    ) -> None:
        """Update cursor with new DirSync cookie after incremental sync."""
        if not runtime.cursor:
            return

        now = datetime.utcnow().isoformat() + "Z"
        runtime.cursor.update(
            acl_dirsync_cookie=result.cookie_b64,
            last_acl_sync_timestamp=now,
            last_acl_changes_count=len(result.changes),
        )

    async def _store_dirsync_cookie_after_full(
        self, source, sync_context: "SyncContext", runtime: "SyncRuntime"
    ) -> None:
        """After a full sync, obtain and store an initial DirSync cookie.

        This seeds the cookie so the next sync can be incremental.
        Calls get_acl_changes with an empty cookie to get the initial state.
        """
        if not hasattr(source, "get_acl_changes"):
            return
        if not hasattr(source, "supports_incremental_acl"):
            return
        if not source.supports_incremental_acl():
            return
        if not runtime.cursor:
            return

        try:
            sync_context.logger.info(
                "Obtaining initial DirSync cookie for future incremental ACL syncs..."
            )
            result = await source.get_acl_changes(dirsync_cookie="")

            if result.cookie_b64:
                now = datetime.utcnow().isoformat() + "Z"
                runtime.cursor.update(
                    acl_dirsync_cookie=result.cookie_b64,
                    last_acl_sync_timestamp=now,
                    last_acl_changes_count=0,
                )
                sync_context.logger.info(
                    f"Stored initial DirSync cookie (len={len(result.new_cookie)})"
                )
            else:
                sync_context.logger.warning(
                    "DirSync returned empty cookie -- incremental ACL not available"
                )
        except Exception as e:
            sync_context.logger.warning(
                f"Could not obtain DirSync cookie: {get_error_message(e)}. "
                "Future syncs will use full ACL sync."
            )

    # -------------------------------------------------------------------------
    # Orphan cleanup (full sync only)
    # -------------------------------------------------------------------------

    async def _cleanup_orphan_memberships(
        self,
        sync_context: "SyncContext",
        encountered_keys: Set[Tuple[str, str, str]],
    ) -> int:
        """Delete memberships in DB that weren't encountered during full sync.

        Critical for security: when a permission is revoked at the source,
        the membership tuple is no longer yielded. These orphan records must
        be deleted to prevent unauthorized access.
        """
        async with get_db_context() as db:
            stored_memberships = await crud.access_control_membership.get_by_source_connection(
                db=db,
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
            )

        if not stored_memberships:
            sync_context.logger.debug("No existing memberships in DB for this source connection")
            return 0

        orphans = []
        for membership in stored_memberships:
            key = (membership.member_id, membership.member_type, membership.group_id)
            if key not in encountered_keys:
                orphans.append(membership)

        if not orphans:
            sync_context.logger.info("No orphan memberships to clean up")
            return 0

        sync_context.logger.info(
            f"Found {len(orphans)} orphan memberships (out of {len(stored_memberships)} stored)"
        )

        async with get_db_context() as db:
            deleted_count = await crud.access_control_membership.bulk_delete(
                db=db,
                ids=[m.id for m in orphans],
            )

        return deleted_count
