"""Pipeline for access control membership processing.

Mirrors EntityPipeline but for membership tuples.
Uses the handler/dispatcher architecture for consistency and future extensibility.
"""

from typing import TYPE_CHECKING, List

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sync.actions.access_control import ACActionDispatcher, ACActionResolver
from airweave.platform.sync.handlers.access_control_postgres import ACPostgresHandler

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class AccessControlPipeline:
    """Orchestrates membership processing through resolver → dispatcher → handlers.

    Mirrors EntityPipeline pattern for consistency:
    1. Resolve: Determine actions for each membership
    2. Dispatch: Route actions to handlers
    3. Handle: Persist to destinations (currently just Postgres)

    This architecture supports future extensions:
    - Additional destinations (e.g., Redis for caching)
    - More action types (e.g., delete stale memberships)
    """

    def __init__(self):
        """Initialize pipeline with default components."""
        self._resolver = ACActionResolver()
        # TODO: Move to builder as it gets more complex
        self._dispatcher = ACActionDispatcher(handlers=[ACPostgresHandler()])

    async def process(
        self,
        memberships: List[MembershipTuple],
        sync_context: "SyncContext",
    ) -> int:
        """Process a batch of membership tuples.

        Args:
            memberships: Membership tuples to process
            sync_context: Sync context

        Returns:
            Number of memberships processed
        """
        if not memberships:
            return 0

        # Step 1: Resolve to actions
        batch = await self._resolver.resolve(memberships, sync_context)

        # Step 2: Dispatch to handlers
        count = await self._dispatcher.dispatch(batch, sync_context)

        return count
