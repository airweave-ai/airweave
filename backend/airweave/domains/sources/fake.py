"""Fake source registry and service for testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from airweave.domains.sources.types import SourceRegistryEntry

if TYPE_CHECKING:
    from airweave import schemas


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


class FakeSourceService:
    """Test implementation of SourceServiceProtocol.

    Returns canned schemas. Populate via seed().

    Usage:
        fake = FakeSourceService()
        fake.seed(source_schema_a, source_schema_b)

        result = await fake.list()
        assert len(result) == 2
    """

    def __init__(self) -> None:
        """Initialize with empty sources."""
        self._sources: dict[str, schemas.Source] = {}

    async def get(self, short_name: str, *args, **kwargs) -> schemas.Source:
        """Get source by short name. Raises SourceNotFoundError if missing."""
        try:
            return self._sources[short_name]
        except KeyError:
            from airweave.domains.sources.exceptions import SourceNotFoundError

            raise SourceNotFoundError(short_name)

    async def list(self, *args, **kwargs) -> list[schemas.Source]:
        """List all sources."""
        return list(self._sources.values())

    # Test helpers

    def seed(self, *sources: schemas.Source) -> None:
        """Populate with pre-built source schemas."""
        for source in sources:
            self._sources[source.short_name] = source

    def clear(self) -> None:
        """Remove all sources."""
        self._sources.clear()
