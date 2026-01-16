"""Access control filter operation.

Resolves user's access context and builds the access control filter
that restricts search results to entities the user has permission to view.

This operation writes directly to state.filter, merging with any existing
filter from QueryInterpretation. This makes it independent of UserFilter.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.platform.access_control.broker import access_broker
from airweave.search.context import SearchContext

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.search.state import SearchState


class AccessControlFilter(SearchOperation):
    """Resolve access context and build access control filter.

    This operation:
    1. Checks if the collection has any sources with access control enabled
    2. If yes, resolves the user's access context (expands group memberships)
    3. Builds an access control filter and writes it directly to state["filter"]

    The filter is written to state["filter"], merging with any existing filter
    (e.g., from QueryInterpretation). This operation is self-contained and does
    not depend on UserFilter running.

    Mixed Collection Support:
    - Non-AC source entities have access_is_public = true by default
    - This is set during indexing (see VespaDestination._add_access_control_fields)
    - No need to check for field absence - all entities have access fields
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
        state: "SearchState",
        ctx: ApiContext,
    ) -> None:
        """Resolve access context and build filter.

        Writes directly to state.filter, merging with any existing filter.
        """
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
            state.access_principals = None
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

        # Merge with any existing filter in state (e.g., from QueryInterpretation)
        existing_filter = state.filter
        merged_filter = self._merge_with_existing_filter(access_filter, existing_filter)

        # Write directly to state.filter - no dependency on UserFilter
        state.filter = merged_filter
        state.access_principals = list(principals)

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
        1. Entity is public (access.is_public = true), OR
        2. access.viewers contains ANY of the user's principals

        Note: This filter format is destination-agnostic. VespaDestination and
        QdrantDestination both translate this to their native format.

        Mixed Collections Support:
        - Non-AC source entities have access_is_public = true by default
        - This is set during indexing (see VespaDestination._add_access_control_fields)
        - No need to check for field absence - all entities have access fields

        Args:
            principals: List of principals (e.g., ["user:john@acme.com", "group:sp:42"])

        Returns:
            Filter dict in Airweave canonical format
        """
        if not principals:
            # No principals = only public entities visible
            return {
                "should": [
                    {"key": "access.is_public", "match": {"value": True}},
                ]
            }

        # Build OR condition: public OR matching principals
        return {
            "should": [
                # Option 1: Entity is explicitly public (including non-AC source entities)
                {"key": "access.is_public", "match": {"value": True}},
                # Option 2: User has matching principal in viewers array
                {"key": "access.viewers", "match": {"any": principals}},
            ]
        }

    def _merge_with_existing_filter(
        self,
        access_filter: Dict[str, Any],
        existing_filter: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge access control filter with existing filter using AND semantics.

        Results must satisfy BOTH:
        - Access control filter (at least one principal matches)
        - Existing filter (all conditions) if present

        Args:
            access_filter: The access control filter we just built
            existing_filter: Any existing filter from state (e.g., from QueryInterpretation)

        Returns:
            Merged filter dict
        """
        if not existing_filter:
            return access_filter

        # Both present - wrap in must[] for AND semantics
        return {"must": [access_filter, existing_filter]}
