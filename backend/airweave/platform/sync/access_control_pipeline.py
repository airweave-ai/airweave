"""Pipeline for access control membership processing.

Mirrors EntityPipeline but for membership tuples.
Uses the handler/dispatcher architecture for consistency and future extensibility.

Key difference from old implementation:
- Now supports orphan detection and deletion (critical for security)
- When permissions are revoked at the source, the corresponding DB records are deleted
"""

from typing import TYPE_CHECKING, List, Set, Tuple

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sync.actions.access_control import ACActionDispatcher, ACActionResolver
from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class AccessControlPipeline:
    """Orchestrates membership processing through resolver → dispatcher → handlers.

    Mirrors EntityPipeline pattern for consistency:
    1. Resolve: Determine actions for each membership
    2. Dispatch: Route actions to handlers
    3. Handle: Persist to destinations (currently just Postgres)
    4. Cleanup: Delete orphan memberships (revoked permissions)

    This architecture supports:
    - Deduplication within a sync
    - Orphan detection (memberships in DB but not seen = revoked permissions)
    - Future extensions (additional destinations, caching, etc.)
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
        memberships: List[MembershipTuple],
        sync_context: "SyncContext",
    ) -> int:
        """Process a batch of membership tuples and cleanup orphans.

        Args:
            memberships: Membership tuples to process (may include duplicates)
            sync_context: Sync context

        Returns:
            Number of memberships upserted (does not include deleted orphans)
        """
        upserted_count = 0

        # Step 1: Track + dedupe memberships (for orphan detection + stats)
        unique_memberships: List[MembershipTuple] = []
        for membership in memberships:
            is_new = self._tracker.track_membership(
                member_id=membership.member_id,
                member_type=membership.member_type,
                group_id=membership.group_id,
            )
            if is_new:
                unique_memberships.append(membership)
                if len(unique_memberships) % 100 == 0:
                    sync_context.logger.debug(
                        f"🔐 Collected {len(unique_memberships)} unique memberships so far..."
                    )

        stats = self._tracker.get_stats()
        sync_context.logger.info(
            f"🔐 Collected {stats.encountered} unique memberships "
            f"({stats.duplicates_skipped} duplicates skipped)"
        )

        # Step 2: Process memberships (upsert)
        if unique_memberships:
            # Resolve to actions
            batch = await self._resolver.resolve(unique_memberships, sync_context)

            # Dispatch to handlers
            upserted_count = await self._dispatcher.dispatch(batch, sync_context)
            self._tracker.record_upserted(upserted_count)

            sync_context.logger.info(f"🔐 Upserted {upserted_count} ACL memberships to PostgreSQL")

        # Step 3: Cleanup orphan memberships (critical for security!)
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

        Args:
            sync_context: Sync context with source_connection_id and organization_id
            encountered_keys: Set of (member_id, member_type, group_id) tuples
                            that were encountered during this sync

        Returns:
            Number of orphan memberships deleted
        """
        # Fetch all stored memberships for this source_connection
        async with get_db_context() as db:
            stored_memberships = await crud.access_control_membership.get_by_source_connection(
                db=db,
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
            )

        if not stored_memberships:
            sync_context.logger.debug("🔐 No existing memberships in DB for this source connection")
            return 0

        # Find orphans: memberships in DB but not encountered during sync
        orphans = []
        for membership in stored_memberships:
            key = (membership.member_id, membership.member_type, membership.group_id)
            if key not in encountered_keys:
                orphans.append(membership)
                sync_context.logger.debug(
                    f"🔐 Orphan detected: {membership.member_id} ({membership.member_type}) "
                    f"→ {membership.group_id} (group_name={membership.group_name})"
                )

        if not orphans:
            sync_context.logger.info("🔐 No orphan memberships to clean up")
            return 0

        # Log details about what's being deleted
        sync_context.logger.info(
            f"🔐 Found {len(orphans)} orphan memberships (out of {len(stored_memberships)} stored) "
            f"- these represent revoked permissions"
        )

        # Delete orphans
        async with get_db_context() as db:
            orphan_ids = [m.id for m in orphans]
            deleted_count = await crud.access_control_membership.bulk_delete(
                db=db,
                ids=orphan_ids,
            )

        return deleted_count
