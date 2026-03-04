"""Fake embedder registries for testing."""

from airweave.domains.embedders.types import DenseEmbedderEntry, SparseEmbedderEntry


class FakeDenseEmbedderRegistry:
    """Test implementation of DenseEmbedderRegistryProtocol.

    Usage:
        fake = FakeDenseEmbedderRegistry()
        fake.seed(entry_a, entry_b)

        assert fake.get("openai_text_embedding_3_small") == entry_a
        assert fake.list_for_provider("openai") == [entry_a]
    """

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, DenseEmbedderEntry] = {}
        self._by_provider: dict[str, list[DenseEmbedderEntry]] = {}

    def get(self, short_name: str) -> DenseEmbedderEntry:
        """Get entry by short name. Raises KeyError if missing."""
        return self._entries[short_name]

    def list_all(self) -> list[DenseEmbedderEntry]:
        """List all entries."""
        return list(self._entries.values())

    def list_for_provider(self, provider: str) -> list[DenseEmbedderEntry]:
        """List all entries for a provider."""
        return self._by_provider.get(provider, [])

    # Test helpers

    def seed(self, *entries: DenseEmbedderEntry) -> None:
        """Populate the registry with pre-built entries."""
        for entry in entries:
            self._entries[entry.short_name] = entry
            self._by_provider.setdefault(entry.provider, []).append(entry)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
        self._by_provider.clear()


class FakeSparseEmbedderRegistry:
    """Test implementation of SparseEmbedderRegistryProtocol.

    Usage:
        fake = FakeSparseEmbedderRegistry()
        fake.seed(entry)

        assert fake.get("fastembed_bm25") == entry
    """

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, SparseEmbedderEntry] = {}
        self._by_provider: dict[str, list[SparseEmbedderEntry]] = {}

    def get(self, short_name: str) -> SparseEmbedderEntry:
        """Get entry by short name. Raises KeyError if missing."""
        return self._entries[short_name]

    def list_all(self) -> list[SparseEmbedderEntry]:
        """List all entries."""
        return list(self._entries.values())

    def list_for_provider(self, provider: str) -> list[SparseEmbedderEntry]:
        """List all entries for a provider."""
        return self._by_provider.get(provider, [])

    # Test helpers

    def seed(self, *entries: SparseEmbedderEntry) -> None:
        """Populate the registry with pre-built entries."""
        for entry in entries:
            self._entries[entry.short_name] = entry
            self._by_provider.setdefault(entry.provider, []).append(entry)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
        self._by_provider.clear()
