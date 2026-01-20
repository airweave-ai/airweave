"""Pipeline for access control membership processing.

Mirrors EntityPipeline but for membership tuples.
Uses the resolver → dispatcher → handler architecture for consistency.

Key features:
- Full sync: Fetches all memberships, does orphan detection (critical for security)
- Incremental sync: Uses DirSync changes, no orphan detection (faster)
- Cursor management: Updates DirSync cookie after sync

The pipeline decides internally whether to do full or incremental sync based on:
- Whether the source supports incremental ACL (has get_acl_changes method)
- Whether a valid DirSync cookie exists in the cursor
- Whether a periodic full sync is needed (e.g., weekly)
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Set, Tuple

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.access_control.schemas import (
    ACLChangeType,
    MembershipChange,
    MembershipTuple,
)
from airweave.platform.sync.actions.access_control import ACActionDispatcher, ACActionResolver
from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class AccessControlPipeline:
    """Orchestrates membership processing through resolver → dispatcher → handlers.

    Architecture:
    1. Pipeline.process() decides: incremental or full sync?
    2. Collects data: calls source.get_acl_changes() or source.generate_access_control_memberships()
    3. Resolve: Convert to actions (ACUpsertAction, ACDeleteAction, etc.)
    4. Dispatch: Route actions to handlers
    5. Handle: Persist to PostgreSQL
    6. Cleanup: Delete orphan memberships (full sync only)
    7. Update cursor: Store new DirSync cookie

    The orchestrator just calls pipeline.process() - all ACL logic lives here.
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
        source: object,
        sync_context: "SyncContext",
    ) -> int:
        """Process access control memberships from a source.

        Automatically chooses between incremental and full sync based on:
        - Source capabilities (supports_incremental_acl)
        - Cursor state (has valid DirSync cookie)
        - Periodic full sync requirements

        Args:
            source: Source instance with generate_access_control_memberships() method
            sync_context: Sync context

        Returns:
            Number of memberships processed
        """
        source_name = getattr(source, "_name", "unknown")
        sync_context.logger.info(f"🔐 Starting ACL sync from {source_name}")

        # Check if source has the required method
        if not hasattr(source, "generate_access_control_memberships"):
            sync_context.logger.warning(
                f"Source {source_name} has supports_access_control=True but no "
                "generate_access_control_memberships() method. Skipping ACL sync."
            )
            return 0

        # Try incremental sync if supported
        if self._should_do_incremental_sync(source, sync_context):
            return await self._process_incremental(source, sync_context)

        # Fall back to full sync
        return await self._process_full(source, sync_context)

    def _should_do_incremental_sync(self, source: object, sync_context: "SyncContext") -> bool:
        """Determine if incremental ACL sync should be used.

        Returns True only if:
        1. Source supports incremental ACL (has get_acl_changes + supports_incremental_acl)
        2. Valid DirSync cookie exists in cursor
        3. Source doesn't require full sync (cookie not expired, periodic sync not needed)
        """
        # Check if source supports incremental ACL
        if not hasattr(source, "get_acl_changes"):
            return False
        if not hasattr(source, "supports_incremental_acl"):
            return False
        if not source.supports_incremental_acl():
            return False

        # Check cursor for DirSync cookie
        cursor_data = sync_context.cursor.data if sync_context.cursor else {}
        dirsync_cookie = cursor_data.get("acl_dirsync_cookie", "")

        # Debug: log cursor keys to diagnose persistence issues
        sync_context.logger.debug(
            f"🔐 ACL cursor check: keys={list(cursor_data.keys())}, "
            f"has_dirsync_cookie={bool(dirsync_cookie)}, "
            f"cookie_len={len(dirsync_cookie) if dirsync_cookie else 0}"
        )

        if not dirsync_cookie:
            sync_context.logger.info("🔐 No DirSync cookie - will do FULL ACL sync")
            return False

        # Check if source wants full sync (e.g., cookie expired, periodic sync)
        if hasattr(source, "_should_do_full_acl_sync"):
            should_full, reason = source._should_do_full_acl_sync()
            if should_full:
                sync_context.logger.info(f"🔐 FULL ACL sync required: {reason}")
                return False

        return True

    async def _process_incremental(
        self,
        source: object,
        sync_context: "SyncContext",
    ) -> int:
        """Process ACL using incremental DirSync.

        Faster than full sync but does NOT do orphan cleanup.
        Orphan cleanup only happens during periodic full syncs.

        With INCREMENTAL_VALUES flag, DirSync returns deltas directly:
        - member;range=0-X = REMOVED members
        - member;range=(X+1)-* = ADDED members

        The LDAP layer parses these ranges and emits both ADD and REMOVE changes.
        """
        sync_context.logger.info("⚡ INCREMENTAL ACL sync (using DirSync)")

        cursor_data = sync_context.cursor.data if sync_context.cursor else {}
        dirsync_cookie = cursor_data.get("acl_dirsync_cookie", "")

        try:
            # Get changes from source via DirSync
            # DirSync with INCREMENTAL_VALUES provides both ADD and REMOVE changes
            result = await source.get_acl_changes(dirsync_cookie=dirsync_cookie)
            changes: List[MembershipChange] = list(result.changes)

            if not changes:
                sync_context.logger.info("🔐 No ACL changes detected (incremental)")
                # Still update cookie even if no changes
                self._update_cursor_after_incremental(sync_context, result.cookie_b64, 0)
                return 0

            # Log change breakdown
            add_count = sum(1 for c in changes if c.change_type == ACLChangeType.ADD)
            remove_count = sum(1 for c in changes if c.change_type == ACLChangeType.REMOVE)
            sync_context.logger.info(
                f"🔐 Processing {len(changes)} incremental ACL changes "
                f"({add_count} adds, {remove_count} removes)"
            )

            # Resolve changes to actions
            batch = await self._resolver.resolve_changes(changes, sync_context)

            # Dispatch to handlers
            processed_count = await self._dispatcher.dispatch(batch, sync_context)

            # Update cursor with new cookie
            self._update_cursor_after_incremental(sync_context, result.cookie_b64, len(changes))

            return processed_count

        except Exception as e:
            sync_context.logger.warning(f"Incremental ACL sync failed: {e}. Falling back to full.")
            return await self._process_full(source, sync_context)

    async def _process_full(
        self,
        source: object,
        sync_context: "SyncContext",
    ) -> int:
        """Process ACL using full sync with orphan detection.

        Slower but ensures data integrity by:
        - Fetching ALL memberships from source
        - Detecting orphan memberships (in DB but not in source = revoked)
        - Deleting orphans (critical for security!)
        """
        sync_context.logger.info("🔐 FULL ACL sync (with orphan detection)")

        # Collect memberships from source generator
        memberships: List[MembershipTuple] = []
        try:
            async for membership in source.generate_access_control_memberships():
                memberships.append(membership)

                # Log progress every 100 memberships
                if len(memberships) % 100 == 0:
                    sync_context.logger.debug(
                        f"🔐 Collected {len(memberships)} memberships so far..."
                    )
        except Exception as e:
            sync_context.logger.error(f"Error collecting ACL memberships: {e}", exc_info=True)
            # Don't do orphan cleanup if collection failed (could delete valid data!)
            return 0

        # Track + dedupe memberships (for orphan detection + stats)
        unique_memberships: List[MembershipTuple] = []
        for membership in memberships:
            is_new = self._tracker.track_membership(
                member_id=membership.member_id,
                member_type=membership.member_type,
                group_id=membership.group_id,
            )
            if is_new:
                unique_memberships.append(membership)

        stats = self._tracker.get_stats()
        sync_context.logger.info(
            f"🔐 Collected {stats.encountered} unique memberships "
            f"({stats.duplicates_skipped} duplicates skipped)"
        )

        # Resolve to actions and dispatch
        upserted_count = 0
        if unique_memberships:
            batch = await self._resolver.resolve(unique_memberships, sync_context)
            upserted_count = await self._dispatcher.dispatch(batch, sync_context)
            self._tracker.record_upserted(upserted_count)
            sync_context.logger.info(f"🔐 Upserted {upserted_count} ACL memberships")

        # Cleanup orphan memberships (critical for security!)
        deleted_count = await self._cleanup_orphan_memberships(
            sync_context, self._tracker.get_encountered_keys()
        )
        self._tracker.record_deleted(deleted_count)
        if deleted_count > 0:
            sync_context.logger.warning(
                f"🗑️ Deleted {deleted_count} orphan ACL memberships (revoked permissions)"
            )

        # Log final summary
        self._tracker.log_summary()

        # Get DirSync cookie for future incremental syncs (if supported)
        await self._store_dirsync_cookie_after_full(source, sync_context, len(unique_memberships))

        return upserted_count

    async def _cleanup_orphan_memberships(
        self,
        sync_context: "SyncContext",
        encountered_keys: Set[Tuple[str, str, str]],
    ) -> int:
        """Delete memberships in DB that weren't encountered during sync.

        This is critical for security: when a permission is revoked at the source,
        the membership tuple is no longer yielded. We need to detect and delete
        these orphan records to ensure the user can no longer see restricted documents.
        """
        async with get_db_context() as db:
            stored_memberships = await crud.access_control_membership.get_by_source_connection(
                db=db,
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
            )

        if not stored_memberships:
            sync_context.logger.debug("🔐 No existing memberships in DB")
            return 0

        # Find orphans: in DB but not encountered during sync
        orphans = []
        for membership in stored_memberships:
            key = (membership.member_id, membership.member_type, membership.group_id)
            if key not in encountered_keys:
                orphans.append(membership)

        if not orphans:
            sync_context.logger.info("🔐 No orphan memberships to clean up")
            return 0

        sync_context.logger.info(
            f"🔐 Found {len(orphans)} orphan memberships (revoked permissions)"
        )

        async with get_db_context() as db:
            orphan_ids = [m.id for m in orphans]
            return await crud.access_control_membership.bulk_delete(db=db, ids=orphan_ids)

    def _update_cursor_after_incremental(
        self,
        sync_context: "SyncContext",
        new_cookie: str,
        changes_count: int,
    ) -> None:
        """Update cursor after incremental ACL sync."""
        if sync_context.cursor:
            now = datetime.utcnow().isoformat() + "Z"
            sync_context.cursor.update(
                acl_dirsync_cookie=new_cookie,
                last_acl_sync_timestamp=now,
                last_acl_changes_count=changes_count,
            )
            sync_context.logger.info(f"📝 Updated DirSync cookie ({changes_count} changes)")

    async def _store_dirsync_cookie_after_full(
        self,
        source: object,
        sync_context: "SyncContext",
        membership_count: int,
    ) -> None:
        """Get and store DirSync cookie after full sync for future incremental syncs."""
        if not hasattr(source, "get_acl_changes"):
            return
        if not hasattr(source, "supports_incremental_acl"):
            return
        if not source.supports_incremental_acl():
            return

        try:
            # Get initial cookie by doing a DirSync with no cookie
            result = await source.get_acl_changes(dirsync_cookie="")

            if sync_context.cursor:
                cookie_b64 = result.cookie_b64
                now = datetime.utcnow().isoformat() + "Z"

                # Debug: verify cookie is valid before storing
                if not cookie_b64:
                    sync_context.logger.warning(
                        "🔐 DirSync returned empty cookie - incremental ACL sync won't work"
                    )
                    return

                sync_context.cursor.update(
                    acl_dirsync_cookie=cookie_b64,
                    last_acl_sync_timestamp=now,
                    last_acl_changes_count=membership_count,
                    total_acl_memberships=membership_count,
                )

                # Debug: verify cookie was stored in cursor
                stored_cookie = sync_context.cursor.data.get("acl_dirsync_cookie", "")
                sync_context.logger.info(
                    f"📝 Stored DirSync cookie for future incremental ACL syncs "
                    f"(cookie_len={len(cookie_b64)}, verified_in_cursor={len(stored_cookie)})"
                )
        except Exception as e:
            sync_context.logger.warning(f"Failed to get DirSync cookie: {e}")
