"""Access control pipeline for processing membership tuples."""

from typing import List

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.access_control.schemas import AccessControlMembership
from airweave.platform.sync.context import SyncContext


class AccessControlPipeline:
    """Simplified pipeline for processing access control memberships.

    Much simpler than EntityPipeline:
    - No transformers
    - No embeddings/vectorization
    - No Qdrant storage
    - Just: normalize + persist to PostgreSQL
    """

    async def process(
        self, memberships: List[AccessControlMembership], sync_context: SyncContext
    ) -> None:
        """Process batch of memberships - persist to database.

        Args:
            memberships: List of AccessControlMembership objects
            sync_context: Sync context with logger and progress tracking
        """
        if not memberships:
            return

        # 1. Normalize (deduplicate by user_email + group_id)
        normalized = self._deduplicate_memberships(memberships)

        sync_context.logger.debug(
            f"Processing {len(normalized)} unique memberships (from {len(memberships)} total)"
        )

        # 2. Persist to database (bulk upsert with ON CONFLICT)
        async with get_db_context() as db:
            count = await crud.access_control_membership.bulk_create(
                db=db,
                memberships=normalized,
                organization_id=sync_context.ctx.organization.id,
                source_connection_id=sync_context.source_connection.id,
                source_name=sync_context.source_connection.short_name,
                ctx=sync_context.ctx,
            )

        sync_context.logger.debug(f"Persisted {count} memberships to database")

    def _deduplicate_memberships(
        self, memberships: List[AccessControlMembership]
    ) -> List[AccessControlMembership]:
        """Remove duplicate memberships (same member_id + member_type + group_id).

        Args:
            memberships: List of membership objects

        Returns:
            Deduplicated list of memberships
        """
        seen = set()
        unique = []

        for m in memberships:
            # Create key: (member_id, member_type, group_id)
            # Normalize member_id to lowercase for case-insensitive deduplication
            key = (m.member_id.lower(), m.member_type, m.group_id)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique
