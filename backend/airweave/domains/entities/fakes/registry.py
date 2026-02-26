"""Fake entity definition registry for testing."""

from airweave.domains.entities.types import EntityDefinitionEntry


class FakeEntityDefinitionRegistry:
    """Test implementation of EntityDefinitionRegistryProtocol.

    Stores entries in a dict with a by-source index. Populate via seed().

    Usage:
        fake = FakeEntityDefinitionRegistry()
        fake.seed(entry_a, entry_b)

        assert fake.get("asana_task_entity") == entry_a
        assert fake.list_for_source("asana") == [entry_a]
    """

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, EntityDefinitionEntry] = {}
        self._by_source: dict[str, list[EntityDefinitionEntry]] = {}

    def get(self, short_name: str) -> EntityDefinitionEntry:
        """Get entry by short name. Raises KeyError if missing."""
        return self._entries[short_name]

    def list_all(self) -> list[EntityDefinitionEntry]:
        """List all entries."""
        return list(self._entries.values())

    def list_for_source(self, source_short_name: str) -> list[EntityDefinitionEntry]:
        """List all entity definitions for a given source."""
        return self._by_source.get(source_short_name, [])

    # Test helpers

    def seed(self, *entries: EntityDefinitionEntry) -> None:
        """Populate the registry with pre-built entries.

        Automatically builds the by-source index from module_name.
        """
        for entry in entries:
            self._entries[entry.short_name] = entry
            self._by_source.setdefault(entry.module_name, []).append(entry)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
        self._by_source.clear()
