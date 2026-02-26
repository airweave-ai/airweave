"""Fake auth provider registry for testing."""

from airweave.domains.auth_provider.types import AuthProviderRegistryEntry


class FakeAuthProviderRegistry:
    """Test implementation of AuthProviderRegistryProtocol.

    Stores entries in a dict for simple get/list. Populate via seed().

    Usage:
        fake = FakeAuthProviderRegistry()
        fake.seed(entry_a, entry_b)

        assert fake.get("pipedream") == entry_a
        assert len(fake.list_all()) == 2
    """

    def __init__(self) -> None:
        """Initialize with empty entries."""
        self._entries: dict[str, AuthProviderRegistryEntry] = {}

    def get(self, short_name: str) -> AuthProviderRegistryEntry:
        """Get entry by short name. Raises KeyError if missing."""
        return self._entries[short_name]

    def list_all(self) -> list[AuthProviderRegistryEntry]:
        """List all entries."""
        return list(self._entries.values())

    # Test helpers

    def seed(self, *entries: AuthProviderRegistryEntry) -> None:
        """Populate the registry with pre-built entries."""
        for entry in entries:
            self._entries[entry.short_name] = entry

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
