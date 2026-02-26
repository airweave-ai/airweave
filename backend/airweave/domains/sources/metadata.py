from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry


class SourceMetadataService:
    """Service for managing source metadata."""

    def __init__(self, source_registry: SourceRegistryProtocol) -> None:
        """Initialize the source metadata service."""
        self.source_registry = source_registry

    def get_source_metadata(self, short_name: str) -> SourceRegistryEntry:
        """Get source metadata by short name."""
        return self.source_registry.get(short_name)
