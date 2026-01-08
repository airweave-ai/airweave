"""Access control filter operation.

Resolves user's access context and builds the access control filter
that restricts search results to entities the user has permission to view.

This operation runs before UserFilter and writes to state["access_control_filter"]
which UserFilter then merges with user-provided filters.
"""

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.platform.access_control.broker import access_broker
from airweave.search.context import SearchContext

from ._base import SearchOperation


class AccessControlFilter(SearchOperation):
    """Resolve access context and build access control filter.

    This operation:
    1. Checks if the collection has any sources with access control enabled
    2. If yes, resolves the user's access context (expands group memberships)
    3. Builds an access control filter for the destination

    The filter is written to state["access_control_filter"] for UserFilter to merge.

    Mixed Collection Support:
    - For collections with BOTH AC and non-AC sources, entities without access
      fields should still be visible. The filter handles this via:
      - is_public = true OR viewers contains principal OR access field is absent
    - For Vespa: uses isNull() check on access_is_public field
    - For Qdrant: relies on entities not having the access.is_public field
    """

    def __init__(
        self,
        db: AsyncSession,
        user_email: str,
        organization_id: UUID,
    ) -> None:
        """Initialize with database session and user info.

        Args:
            db: Database session for AccessBroker queries
            user_email: User's email for principal resolution
            organization_id: Organization ID for scoped queries
        """
        self.db = db
        self.user_email = user_email
        self.organization_id = organization_id

    def depends_on(self) -> List[str]:
        """No dependencies - runs early in the pipeline."""
        return []

    async def execute(
        self,
        context: SearchContext,
        state: Dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Resolve access context and build filter."""
        ctx.logger.info("[AccessControlFilter] Resolving access context...")

        # Resolve access context for this collection
        # Returns None if collection has no AC sources (skip filtering)
        access_context = await access_broker.resolve_access_context_for_collection(
            db=self.db,
            user_principal=self.user_email,
            readable_collection_id=context.readable_collection_id,
            organization_id=self.organization_id,
        )

        if access_context is None:
            # No AC sources in collection - skip filtering entirely
            ctx.logger.info(
                "[AccessControlFilter] Collection has no access-control-enabled sources. "
                "Skipping access filtering - all entities visible."
            )
            state["access_control_filter"] = None
            state["access_principals"] = None
            await context.emitter.emit(
                "access_control_skipped",
                {"reason": "no_ac_sources_in_collection"},
                op_name=self.__class__.__name__,
            )
            return

        # Build the access control filter
        principals = access_context.all_principals
        ctx.logger.info(
            f"[AccessControlFilter] ✓ Resolved {len(principals)} principals for user "
            f"'{self.user_email}'"
        )
        ctx.logger.debug(f"[AccessControlFilter] Principals: {principals}")

        # Build filter - destination will translate to appropriate format (YQL for Vespa, etc.)
        access_filter = self._build_access_control_filter(principals)

        # Store in state for UserFilter to merge
        state["access_control_filter"] = access_filter
        state["access_principals"] = list(principals)

        await context.emitter.emit(
            "access_control_resolved",
            {
                "principal_count": len(principals),
                "user_email": self.user_email,
            },
            op_name=self.__class__.__name__,
        )

        ctx.logger.info(
            f"[AccessControlFilter] ✓ Access control filter built with {len(principals)} principals"
        )

    def _build_access_control_filter(self, principals: List[str]) -> Dict[str, Any]:
        """Build access control filter in Airweave canonical format.

        Returns filter that matches if:
        1. Entity has NO access control field (non-AC source → visible to all), OR
        2. Entity is public (access.is_public = true), OR
        3. access.viewers contains ANY of the user's principals

        Note: This filter format is destination-agnostic. VespaDestination and
        QdrantDestination both translate this to their native format.

        Mixed Collections Support:
        - Entities from non-AC sources won't have access fields at all
        - We use is_null check to include these entities (visible to everyone)
        - Vespa: translates to isNull(access_is_public)
        - Qdrant: field absence check (may need different handling)

        Args:
            principals: List of principals (e.g., ["user:john@acme.com", "group:sp:42"])

        Returns:
            Filter dict in Airweave canonical format
        """
        if not principals:
            # No principals = only public entities OR entities without access control visible
            return {
                "should": [
                    # Option 1: Entity has no access control (non-AC source)
                    {"key": "access.is_public", "is_null": True},
                    # Option 2: Entity is explicitly public
                    {"key": "access.is_public", "match": {"value": True}},
                ]
            }

        # Build OR condition: no access control OR public OR matching principals
        return {
            "should": [
                # Option 1: Entity has no access control field (non-AC source)
                # These entities should be visible to everyone
                {"key": "access.is_public", "is_null": True},
                # Option 2: Entity is explicitly public
                {"key": "access.is_public", "match": {"value": True}},
                # Option 3: User has matching principal in viewers array
                {"key": "access.viewers", "match": {"any": principals}},
            ]
        }
