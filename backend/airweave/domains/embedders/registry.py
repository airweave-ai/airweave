"""Embedder registries — in-memory registries built once at startup."""

from airweave.core.logging import logger
from airweave.domains.embedders.protocols import (
    DenseEmbedderRegistryProtocol,
    SparseEmbedderRegistryProtocol,
)
from airweave.domains.embedders.types import DenseEmbedderEntry, SparseEmbedderEntry

registry_logger = logger.with_prefix("EmbedderRegistry: ").with_context(
    component="embedder_registry"
)


class DenseEmbedderRegistry(DenseEmbedderRegistryProtocol):
    """In-memory dense embedder registry, built from manual registration data."""

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, DenseEmbedderEntry] = {}
        self._by_provider: dict[str, list[DenseEmbedderEntry]] = {}

    def get(self, short_name: str) -> DenseEmbedderEntry:
        """Get a dense embedder entry by short name.

        Args:
            short_name: The unique identifier (e.g. "openai_text_embedding_3_small").

        Returns:
            The dense embedder entry.

        Raises:
            KeyError: If no entry with the given short name is registered.
        """
        return self._entries[short_name]

    def list_all(self) -> list[DenseEmbedderEntry]:
        """List all registered dense embedder entries."""
        return list(self._entries.values())

    def list_for_provider(self, provider: str) -> list[DenseEmbedderEntry]:
        """List all dense embedder entries for a provider.

        Args:
            provider: Provider name (e.g. "openai", "mistral", "local").

        Returns:
            All entries for the provider, or empty list if none.
        """
        return self._by_provider.get(provider, [])

    def build(self) -> None:
        """Build the registry from DENSE_EMBEDDERS in the platform layer.

        Called once at startup. After this, all lookups are dict reads.
        """
        from airweave.domains.embedders.registry_data import DENSE_EMBEDDERS

        for spec in DENSE_EMBEDDERS:
            entry = DenseEmbedderEntry(
                short_name=spec.short_name,
                name=spec.name,
                description=spec.description,
                class_name=spec.embedder_class.__name__,
                provider=spec.provider,
                api_model_name=spec.api_model_name,
                max_dimensions=spec.max_dimensions,
                max_tokens=spec.max_tokens,
                supports_matryoshka=spec.supports_matryoshka,
                embedder_class_ref=spec.embedder_class,
                required_setting=spec.required_setting,
            )
            self._entries[entry.short_name] = entry
            self._by_provider.setdefault(entry.provider, []).append(entry)

        registry_logger.info(f"Built dense embedder registry with {len(self._entries)} entries.")


class SparseEmbedderRegistry(SparseEmbedderRegistryProtocol):
    """In-memory sparse embedder registry, built from manual registration data."""

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, SparseEmbedderEntry] = {}
        self._by_provider: dict[str, list[SparseEmbedderEntry]] = {}

    def get(self, short_name: str) -> SparseEmbedderEntry:
        """Get a sparse embedder entry by short name.

        Args:
            short_name: The unique identifier (e.g. "fastembed_bm25").

        Returns:
            The sparse embedder entry.

        Raises:
            KeyError: If no entry with the given short name is registered.
        """
        return self._entries[short_name]

    def list_all(self) -> list[SparseEmbedderEntry]:
        """List all registered sparse embedder entries."""
        return list(self._entries.values())

    def list_for_provider(self, provider: str) -> list[SparseEmbedderEntry]:
        """List all sparse embedder entries for a provider.

        Args:
            provider: Provider name (e.g. "fastembed").

        Returns:
            All entries for the provider, or empty list if none.
        """
        return self._by_provider.get(provider, [])

    def build(self) -> None:
        """Build the registry from SPARSE_EMBEDDERS in the platform layer.

        Called once at startup. After this, all lookups are dict reads.
        """
        from airweave.domains.embedders.registry_data import SPARSE_EMBEDDERS

        for spec in SPARSE_EMBEDDERS:
            entry = SparseEmbedderEntry(
                short_name=spec.short_name,
                name=spec.name,
                description=spec.description,
                class_name=spec.embedder_class.__name__,
                provider=spec.provider,
                api_model_name=spec.api_model_name,
                embedder_class_ref=spec.embedder_class,
                required_setting=spec.required_setting,
            )
            self._entries[entry.short_name] = entry
            self._by_provider.setdefault(entry.provider, []).append(entry)

        registry_logger.info(f"Built sparse embedder registry with {len(self._entries)} entries.")
