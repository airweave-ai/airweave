"""Fake auth provider domain objects for testing."""

from fastapi import HTTPException

from airweave import schemas
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


class FakeAuthProviderService:
    """In-memory fake for AuthProviderServiceProtocol."""

    def __init__(self) -> None:
        self._connections: dict[str, schemas.AuthProviderConnection] = {}
        self._calls: list[tuple[object, ...]] = []

    def seed_connection(self, connection: schemas.AuthProviderConnection) -> None:
        """Seed a connection response object by readable_id."""
        self._connections[connection.readable_id] = connection

    async def list_connections(self, db, *, ctx, skip: int = 0, limit: int = 100):
        self._calls.append(("list_connections", db, ctx, skip, limit))
        values = list(self._connections.values())
        return values[skip : skip + limit]

    async def get_connection(self, db, *, readable_id: str, ctx):
        self._calls.append(("get_connection", db, readable_id, ctx))
        if readable_id not in self._connections:
            raise HTTPException(
                status_code=404, detail=f"Auth provider connection not found: {readable_id}"
            )
        return self._connections[readable_id]

    async def create_connection(self, db, *, obj_in, ctx):
        self._calls.append(("create_connection", db, obj_in, ctx))
        return await self.get_connection(db, readable_id=obj_in.readable_id, ctx=ctx)

    async def update_connection(self, db, *, readable_id: str, obj_in, ctx):
        self._calls.append(("update_connection", db, readable_id, obj_in, ctx))
        return await self.get_connection(db, readable_id=readable_id, ctx=ctx)

    async def delete_connection(self, db, *, readable_id: str, ctx):
        self._calls.append(("delete_connection", db, readable_id, ctx))
        connection = await self.get_connection(db, readable_id=readable_id, ctx=ctx)
        self._connections.pop(readable_id, None)
        return connection
