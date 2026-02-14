"""Fake connection repository for testing."""

from typing import Any, Optional
from uuid import UUID, uuid4


class FakeConnectionRepository:
    """In-memory fake for ConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[UUID, Any] = {}
        self._by_readable_id: dict[str, Any] = {}

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create and store a fake connection."""
        conn_id = uuid4()
        if isinstance(obj_in, dict):
            record = type("FakeConnection", (), {"id": conn_id, **obj_in})()
        else:
            data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else {}
            data["id"] = conn_id
            record = type("FakeConnection", (), data)()
        self._store[conn_id] = record
        readable_id = getattr(record, "readable_id", None)
        if readable_id:
            self._by_readable_id[readable_id] = record
        return record

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get by ID."""
        return self._store.get(id)

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get by readable ID."""
        return self._by_readable_id.get(readable_id)

    def seed(self, *items: Any) -> None:
        """Add pre-built items."""
        for item in items:
            self._store[item.id] = item
            readable_id = getattr(item, "readable_id", None)
            if readable_id:
                self._by_readable_id[readable_id] = item

    def clear(self) -> None:
        """Reset state."""
        self._store.clear()
        self._by_readable_id.clear()
