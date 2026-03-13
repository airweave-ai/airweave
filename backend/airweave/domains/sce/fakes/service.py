"""Fake SCE service for testing."""

from typing import AsyncGenerator, List

from airweave.domains.sce.types import EntityAnnotations, EntityExtractionInput, ExtractedRef


class FakeSceService:
    """No-op SCE service that returns empty annotations."""

    async def extract(self, entity_input: EntityExtractionInput) -> List[ExtractedRef]:
        """Return empty refs."""
        return []

    async def process_entities(
        self, entity_inputs: List[EntityExtractionInput]
    ) -> AsyncGenerator[EntityAnnotations, None]:
        """Yield empty annotations for each entity."""
        for entity_input in entity_inputs:
            yield EntityAnnotations(entity_id=entity_input.entity_id, refs=[])
