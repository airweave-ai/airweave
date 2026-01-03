"""Handler protocol for action execution.

Handlers receive resolved actions and persist them to their destination.
All handlers are called concurrently by the ActionDispatcher.

Protocol Methods (public interface):
- handle_batch: Main entry point for batch processing
- handle_inserts/updates/deletes: Individual action handlers
- handle_orphan_cleanup: End-of-sync cleanup

Implementation Pattern:
- Public methods should be thin wrappers calling private _do_* methods
- Private methods contain the actual logic
- This allows handlers to override behavior at either level
"""

from typing import TYPE_CHECKING, List, Protocol, runtime_checkable

from airweave.platform.sync.actions.types import (
    ActionBatch,
    DeleteAction,
    InsertAction,
    UpdateAction,
)

if TYPE_CHECKING:
    from airweave.platform.sync.context import SyncContext


@runtime_checkable
class ActionHandler(Protocol):
    """Protocol defining the ActionHandler interface.

    Handlers receive resolved actions and persist them to their destination.
    All handlers are called concurrently for each batch by the ActionDispatcher.

    Contract:
    - Handlers MUST be idempotent (safe to retry on failure)
    - Handlers MUST raise SyncFailureError for non-recoverable errors
    - Handlers receive actions AFTER chunking/embedding (for destination handlers)

    Execution Order:
    1. All destination handlers receive ActionBatch concurrently
    2. If ANY handler fails, SyncFailureError bubbles up (all-or-nothing)
    3. PostgresMetadataHandler runs AFTER other handlers succeed (consistency)

    Implementation Pattern:
    - Public methods are the protocol interface
    - Each public method should delegate to a private _do_* method
    - Private methods contain actual logic and can be overridden/reused
    """

    @property
    def name(self) -> str:
        """Handler name for logging and debugging."""
        ...

    async def handle_batch(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Handle a full action batch (main entry point).

        Default implementation calls handle_inserts/updates/deletes.
        Override for custom batch handling (e.g., single transaction).

        Args:
            batch: ActionBatch with resolved actions
            sync_context: Sync context

        Raises:
            SyncFailureError: If any operation fails
        """
        ...

    async def handle_inserts(
        self,
        actions: List[InsertAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle insert actions.

        Args:
            actions: List of InsertAction objects
            sync_context: Sync context

        Raises:
            SyncFailureError: If inserts fail
        """
        ...

    async def handle_updates(
        self,
        actions: List[UpdateAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle update actions.

        Args:
            actions: List of UpdateAction objects
            sync_context: Sync context

        Raises:
            SyncFailureError: If updates fail
        """
        ...

    async def handle_deletes(
        self,
        actions: List[DeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle delete actions.

        Args:
            actions: List of DeleteAction objects
            sync_context: Sync context

        Raises:
            SyncFailureError: If deletes fail
        """
        ...

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Handle orphaned entity cleanup at sync end.

        Called for entities in DB but not encountered during sync
        (indicating deletion at source).

        Args:
            orphan_entity_ids: List of entity IDs that are orphaned
            sync_context: Sync context

        Raises:
            SyncFailureError: If cleanup fails
        """
        ...
