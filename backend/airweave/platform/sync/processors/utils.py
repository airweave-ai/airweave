"""Shared utilities for content processors."""

from typing import TYPE_CHECKING, List

from airweave.platform.entities._base import BaseEntity

if TYPE_CHECKING:
    from airweave.platform.sync.context import SyncContext


async def filter_empty_representations(
    entities: List[BaseEntity],
    sync_context: "SyncContext",
    processor_name: str = "Processor",
) -> List[BaseEntity]:
    """Filter entities with empty textual_representation.

    Args:
        entities: Entities to filter
        sync_context: Sync context for logging and tracking
        processor_name: Name for logging

    Returns:
        Entities with non-empty textual representations
    """
    valid = []
    for entity in entities:
        text = entity.textual_representation
        if not text or not text.strip():
            sync_context.logger.warning(
                f"[{processor_name}] Entity {entity.entity_id} has empty text, skipping"
            )
            continue
        valid.append(entity)

    skipped = len(entities) - len(valid)
    if skipped:
        await sync_context.entity_tracker.record_skipped(skipped)

    return valid
