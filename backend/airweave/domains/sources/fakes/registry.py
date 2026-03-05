"""Fake source registry for testing."""

from __future__ import annotations

from airweave.domains.sources.types import SourceRegistryEntry


class FakeSourceRegistry:
    """Test implementation of SourceRegistryProtocol.

    Stores entries in a dict for simple get/list. Populate via seed().

    Usage:
        fake = FakeSourceRegistry()
        fake.seed(entry_a, entry_b)

        assert fake.get("slack") == entry_a
        assert len(fake.list_all()) == 2
    """

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, SourceRegistryEntry] = {}

    def get(self, short_name: str) -> SourceRegistryEntry:
        """Get entry by short name. Raises KeyError if missing."""
        return self._entries[short_name]

    def list_all(self) -> list[SourceRegistryEntry]:
        """List all entries."""
        return list(self._entries.values())

    # Test helpers

    def seed(self, *entries: SourceRegistryEntry) -> None:
        """Populate the registry with pre-built entries."""
        for entry in entries:
            self._entries[entry.short_name] = entry

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
