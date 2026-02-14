"""Fake source connection repository for testing."""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class FakeSourceConnectionRepository:
    """In-memory fake for SourceConnectionRepositoryProtocol.

    Stores source connections in a dict. Returns simple namespace objects.
    """

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[UUID, Any] = {}
        self._removed: list[UUID] = []

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get by ID or None."""
        return self._store.get(id)

    async def get_multi_with_stats(
        self, db: Any, *, ctx: Any, collection_id: Optional[str], skip: int, limit: int
    ) -> List[Dict[str, Any]]:
        """Return all stored items as stat dicts."""
        items = list(self._store.values())
        if collection_id:
            items = [
                i for i in items if getattr(i, "readable_collection_id", None) == collection_id
            ]
        return [
            {
                "id": getattr(i, "id", uuid4()),
                "name": getattr(i, "name", ""),
                "short_name": getattr(i, "short_name", ""),
                "readable_collection_id": getattr(i, "readable_collection_id", ""),
                "created_at": getattr(i, "created_at", None),
                "modified_at": getattr(i, "modified_at", None),
                "is_authenticated": getattr(i, "is_authenticated", True),
                "is_active": True,
                "authentication_method": "direct",
                "last_job": None,
                "entity_count": 0,
                "federated_search": False,
            }
            for i in items[skip : skip + limit]
        ]

    async def get_by_query_and_org(self, db: Any, ctx: Any, **kwargs: Any) -> Optional[Any]:
        """Find first matching item by kwargs."""
        for item in self._store.values():
            if all(getattr(item, k, None) == v for k, v in kwargs.items()):
                return item
        return None

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Store and return a fake record."""
        record_id = uuid4()
        if isinstance(obj_in, dict):
            record = type("FakeSourceConnection", (), {"id": record_id, **obj_in})()
        else:
            data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else {"id": record_id}
            data["id"] = record_id
            record = type("FakeSourceConnection", (), data)()
        self._store[record_id] = record
        return record

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update fields on db_obj from obj_in."""
        if hasattr(obj_in, "model_dump"):
            updates = {k: v for k, v in obj_in.model_dump().items() if v is not None}
        elif isinstance(obj_in, dict):
            updates = {k: v for k, v in obj_in.items() if v is not None}
        else:
            updates = {}
        for k, v in updates.items():
            setattr(db_obj, k, v)
        return db_obj

    async def remove(self, db: Any, *, id: UUID, ctx: Any) -> Any:
        """Remove from store."""
        removed = self._store.pop(id, None)
        if removed:
            self._removed.append(id)
        return removed

    async def get_schedule_info(self, db: Any, source_connection: Any) -> Optional[Dict[str, Any]]:
        """Return None (no schedule by default)."""
        return None

    # Test helpers

    def seed(self, *items: Any) -> None:
        """Add pre-built items to the store."""
        for item in items:
            self._store[item.id] = item

    def clear(self) -> None:
        """Reset all state."""
        self._store.clear()
        self._removed.clear()

    @property
    def created_count(self) -> int:
        """Number of items in store."""
        return len(self._store)
