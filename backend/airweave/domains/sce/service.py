"""SCE orchestration service."""

from typing import AsyncGenerator, List

from airweave.domains.sce.protocols import (
    ExtractorProtocol,
    StructuralContextExtractorServiceProtocol,
)
from airweave.domains.sce.types import EntityAnnotations, EntityExtractionInput, ExtractedRef


class StructuralContextExtractorService(StructuralContextExtractorServiceProtocol):
    """Orchestrates multiple extractors to produce entity annotations."""

    def __init__(self, extractors: List[ExtractorProtocol]):
        """Initialize with a list of extractors."""
        self.extractors = extractors

    async def extract(self, entity_input: EntityExtractionInput) -> List[ExtractedRef]:
        """Run applicable extractors on a single entity, deduplicating results."""
        seen: set[str] = set()
        refs: List[ExtractedRef] = []

        for extractor in self.extractors:
            if not extractor.should_extract(entity_input.entity_type):
                continue
            extracted_refs = await extractor.extract(entity_input.text)
            for ref in extracted_refs:
                if ref.prefixed not in seen:
                    seen.add(ref.prefixed)
                    refs.append(ref)
        return refs

    async def process_entities(
        self, entity_inputs: List[EntityExtractionInput]
    ) -> AsyncGenerator[EntityAnnotations, None]:
        """Process multiple entities, yielding annotations for each."""
        for entity_input in entity_inputs:
            refs = await self.extract(entity_input)
            yield EntityAnnotations(entity_id=entity_input.entity_id, refs=refs)
