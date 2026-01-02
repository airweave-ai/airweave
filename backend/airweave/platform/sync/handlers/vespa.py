"""Vespa destination handler for self-processing destinations.

This handler:
1. Receives resolved actions with raw entities
2. Sends raw entities to Vespa (no pre-processing)
3. Vespa handles chunking and embedding internally

Key characteristics:
- Does NOT perform chunking or embedding (Vespa does it)
- Sends raw BaseEntity to Vespa
- Only handles destinations with processing_requirement=RAW_ENTITIES
"""

import asyncio
from typing import TYPE_CHECKING, Any, Callable, List

from airweave.platform.destinations._base import BaseDestination
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


class VespaHandler(ActionHandler):
    """Handler for self-processing destinations (Vespa).

    Vespa handles chunking and embedding internally via its schema configuration.
    This handler simply forwards raw entities to Vespa without any preprocessing.

    Key differences from VectorDBHandler:
    - Does NOT chunk or embed entities
    - Sends raw parent entities directly to Vespa
    - Vespa's schema defines how to chunk and embed the content field
    """

    def __init__(self, destinations: List[BaseDestination]):
        """Initialize handler with specific Vespa-like destinations.

        Args:
            destinations: List of destinations that handle their own processing.
                         These should have processing_requirement=RAW_ENTITIES.
        """
        self._destinations = destinations

    @property
    def name(self) -> str:
        """Handler name for logging and debugging."""
        if not self._destinations:
            return "vespa[]"
        dest_names = [d.__class__.__name__ for d in self._destinations]
        return f"vespa[{','.join(dest_names)}]"

    # -------------------------------------------------------------------------
    # ActionHandler Protocol Implementation
    # -------------------------------------------------------------------------

    async def handle_batch(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Handle a full action batch.

        Unlike VectorDBHandler, no preprocessing is needed - Vespa handles it.

        Args:
            batch: ActionBatch with resolved actions
            sync_context: Sync context

        Raises:
            SyncFailureError: If dispatch fails
        """
        if not self._destinations:
            sync_context.logger.debug(f"[{self.name}] No destinations configured, skipping")
            return

        # Dispatch directly - no content processing needed
        await super().handle_batch(batch, sync_context)

    async def handle_inserts(
        self,
        actions: List[InsertAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle insert actions by sending raw entities to Vespa.

        Args:
            actions: Insert actions with raw entities
            sync_context: Sync context

        Raises:
            SyncFailureError: If any destination fails
        """
        if not actions:
            return

        entities = [action.entity for action in actions]
        sync_context.logger.debug(f"[{self.name}] Inserting {len(entities)} raw entities to Vespa")

        for dest in self._destinations:
            await self._execute_with_availability_retry(
                operation=lambda d=dest: d.bulk_insert_raw(entities),
                operation_name=f"insert_to_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    async def handle_updates(
        self,
        actions: List[UpdateAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle update actions: delete old documents, insert new entities.

        Args:
            actions: Update actions with raw entities
            sync_context: Sync context

        Raises:
            SyncFailureError: If any destination fails
        """
        if not actions:
            return

        # 1. Delete old documents
        entity_ids = [action.entity_id for action in actions]
        for dest in self._destinations:
            await self._execute_with_availability_retry(
                operation=lambda d=dest: d.bulk_delete_by_entity_ids(
                    entity_ids, sync_context.sync.id
                ),
                operation_name=f"update_clear_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

        # 2. Insert new documents
        entities = [action.entity for action in actions]
        for dest in self._destinations:
            await self._execute_with_availability_retry(
                operation=lambda d=dest: d.bulk_insert_raw(entities),
                operation_name=f"update_insert_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    async def handle_deletes(
        self,
        actions: List[DeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle delete actions by removing documents from Vespa.

        Args:
            actions: Delete actions
            sync_context: Sync context

        Raises:
            SyncFailureError: If any destination fails
        """
        if not actions:
            return

        entity_ids = [action.entity_id for action in actions]
        sync_context.logger.debug(f"[{self.name}] Deleting {len(entity_ids)} entities")

        for dest in self._destinations:
            await self._execute_with_availability_retry(
                operation=lambda d=dest: d.bulk_delete_by_entity_ids(
                    entity_ids, sync_context.sync.id
                ),
                operation_name=f"delete_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Clean up orphaned entities from Vespa.

        Args:
            orphan_entity_ids: Entity IDs to clean up
            sync_context: Sync context

        Raises:
            SyncFailureError: If any destination fails
        """
        if not orphan_entity_ids:
            return

        sync_context.logger.debug(
            f"[{self.name}] Cleaning up {len(orphan_entity_ids)} orphaned entities"
        )

        for dest in self._destinations:
            await self._execute_with_availability_retry(
                operation=lambda d=dest: d.bulk_delete_by_entity_ids(
                    orphan_entity_ids, sync_context.sync.id
                ),
                operation_name=f"orphan_cleanup_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    # -------------------------------------------------------------------------
    # Retry Logic (availability retries)
    # -------------------------------------------------------------------------

    async def _execute_with_availability_retry(
        self,
        operation: Callable,
        operation_name: str,
        sync_context: "SyncContext",
        max_retries: int = 4,
    ) -> Any:
        """Execute operation with retries ONLY for availability issues.

        Logic:
        - If service is down (ConnectionRefused, 503), wait and retry.
        - If permanent error (400, DataError), fail immediately.

        Args:
            operation: Async callable to execute
            operation_name: Name for logging
            sync_context: Sync context
            max_retries: Maximum retry attempts

        Returns:
            Operation result

        Raises:
            SyncFailureError: If operation fails after retries or encounters permanent error
        """
        # Define what constitutes an availability failure
        retryable_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Try to import httpcore/httpx for network errors if available
        try:
            import httpcore
            import httpx

            retryable_errors += (
                httpx.NetworkError,
                httpx.TimeoutException,
                httpcore.NetworkError,
                httpcore.TimeoutException,
            )
        except ImportError:
            pass

        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except retryable_errors as e:
                if attempt < max_retries:
                    wait_time = 2 * (2**attempt)  # 2, 4, 8, 16s
                    sync_context.logger.warning(
                        f"⚠️ [{self.name}] {operation_name} unavailable "
                        f"(attempt {attempt + 1}/{max_retries}): "
                        f"{type(e).__name__} - {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    sync_context.logger.error(
                        f"💥 [{self.name}] {operation_name} unavailable "
                        f"after {max_retries} retries."
                    )
                    raise SyncFailureError(f"Destination unavailable: {e}") from e
            except Exception as e:
                # Check for permanent errors (like 400 Bad Request)
                if self._is_permanent_error(e):
                    sync_context.logger.error(
                        f"💥 [{self.name}] Permanent error in {operation_name}: {e}"
                    )
                    raise SyncFailureError(f"Destination error: {e}") from e

                # Fail fast on non-network errors to respect UoW
                sync_context.logger.error(f"💥 [{self.name}] Error in {operation_name}: {e}")
                raise SyncFailureError(f"Destination failed: {e}") from e

    def _is_permanent_error(self, e: Exception) -> bool:
        """Check if error is definitely permanent.

        Args:
            e: Exception to check

        Returns:
            True if error is permanent (should not retry)
        """
        msg = str(e).lower()
        return any(x in msg for x in ["400", "401", "403", "404", "validation error"])
