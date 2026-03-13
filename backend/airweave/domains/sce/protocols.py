"""SCE protocol definitions."""

from typing import AsyncGenerator, List, Protocol

from airweave.domains.sce.types import EntityAnnotations, EntityExtractionInput, ExtractedRef


class ExtractorProtocol(Protocol):
    """Interface for an extractor."""

    excluded_entity_types: set[str] | None

    def should_extract(self, entity_type: str | None) -> bool:
        """Check if the extractor should run for the given entity type."""
        if self.excluded_entity_types is None:
            return True
        return (
            entity_type is not None
            and entity_type not in self.excluded_entity_types
        )

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
