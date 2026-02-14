"""Fake collection repository for testing."""

from typing import Any, Optional


class FakeCollectionRepository:
    """In-memory fake for CollectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize empty store."""
        self._by_readable_id: dict[str, Any] = {}

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get by readable ID."""
        return self._by_readable_id.get(readable_id)

    def seed(self, *items: Any) -> None:
        """Add pre-built items keyed by readable_id."""
        for item in items:
            self._by_readable_id[item.readable_id] = item

    def clear(self) -> None:
        """Reset state."""
        self._by_readable_id.clear()
