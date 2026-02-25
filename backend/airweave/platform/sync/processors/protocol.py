"""Content processor protocol definition.

Content processors prepare entities for specific destination requirements.
Each destination provides its own processor, inverting the dependency -
destinations know what they need, not handlers guessing based on flags.
"""

from typing import TYPE_CHECKING, List, Protocol, runtime_checkable

from airweave.platform.entities._base import BaseEntity

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


@runtime_checkable
class ContentProcessor(Protocol):
    """Protocol for content processing strategies.

    Each destination provides a processor that knows exactly what data shape
    it needs. This inverts the control - instead of handlers deciding based
    on flags, destinations declare their requirements.

    Processors are stateless and can be shared across destinations of the
    same type.
    """

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Process entities into the format the destination needs.

        Args:
            entities: Raw entities with entity_id and base metadata set
            sync_context: Sync context with logger, collection info, etc.
            runtime: Sync runtime with entity_tracker, source, etc.

        Returns:
            Processed entities ready for bulk_insert().
            May return more entities than input (chunking multiplies)
            or same count (raw/text-only).

        Contract:
            - Must not modify input entities in ways that affect other processors
            - Must set all fields required by the destination's bulk_insert()
            - Should record skipped entities via runtime.entity_tracker
        """
        ...
