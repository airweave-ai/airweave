"""SCE protocol definitions."""

from typing import AsyncGenerator, List, Protocol

from airweave.platform.sce.types import EntityAnnotations, EntityExtractionInput, ExtractedRef


class ExtractorProtocol(Protocol):
    """Interface for an extractor."""

    async def extract(self, text: str) -> List[ExtractedRef]:
        """Extract references from text."""
        ...


class StructuralContextExtractorServiceProtocol(Protocol):
    """Interface for the SCE orchestration service."""

    async def extract(self, entity_input: EntityExtractionInput) -> List[ExtractedRef]:
        """Extract references from a single entity."""
        ...

    def process_entities(
        self, entity_inputs: List[EntityExtractionInput]
    ) -> AsyncGenerator[EntityAnnotations, None]:
        """Process multiple entities, yielding annotations."""
        ...
