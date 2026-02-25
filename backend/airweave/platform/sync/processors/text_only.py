"""Text-only processor for destinations that embed internally.

Used by: Vespa (and future destinations with server-side embedding)
"""

from typing import TYPE_CHECKING, List

from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.pipeline.text_builder import text_builder
from airweave.platform.sync.processors.protocol import ContentProcessor
from airweave.platform.sync.processors.utils import filter_empty_representations

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


class TextOnlyProcessor(ContentProcessor):
    """Processor that only builds textual representation.

    Skips chunking and embedding - destination handles these internally.

    Pipeline:
    1. Build textual representation (text extraction from files/web)

    Output:
        Same entities with:
        - textual_representation: full extracted text
        - entity_id: unchanged (no chunking)
        - NO vectors (destination embeds server-side)
    """

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Build text representations only - no chunking or embedding."""
        if not entities:
            return []

        # Build textual representations
        processed = await text_builder.build_for_batch(entities, sync_context, runtime)

        # Filter empty representations
        processed = await filter_empty_representations(processed, sync_context, runtime, "TextOnly")

        sync_context.logger.debug(
            f"[TextOnlyProcessor] Built text for {len(processed)}/{len(entities)} entities"
        )

        return processed
