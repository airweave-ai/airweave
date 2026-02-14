"""Fake source connection service for testing."""

from typing import Any, List, Optional
from uuid import UUID

from airweave.domains.source_connections.exceptions import SourceConnectionNotFoundError


class FakeSourceConnectionService:
    """Fake implementation of SourceConnectionServiceProtocol.

    Returns canned responses. Set should_raise for error paths.
    """

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        """Initialize with optional error injection."""
        self._should_raise = should_raise
        self._connections: dict[UUID, Any] = {}

    def _maybe_raise(self) -> None:
        if self._should_raise is not None:
            raise self._should_raise

    async def create(self, db: Any, *, obj_in: Any, ctx: Any) -> Any:
        self._maybe_raise()
        return None

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Any:
        self._maybe_raise()
        if id not in self._connections:
            raise SourceConnectionNotFoundError(id)
        return self._connections[id]

    async def list(
        self,
        db: Any,
        *,
        ctx: Any,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Any]:
        self._maybe_raise()
        return list(self._connections.values())

    async def update(self, db: Any, *, id: UUID, obj_in: Any, ctx: Any) -> Any:
        self._maybe_raise()
        if id not in self._connections:
            raise SourceConnectionNotFoundError(id)
        return self._connections[id]

    async def delete(self, db: Any, *, id: UUID, ctx: Any) -> Any:
        self._maybe_raise()
        if id not in self._connections:
            raise SourceConnectionNotFoundError(id)
        return self._connections.pop(id)

    async def run(self, db: Any, *, id: UUID, ctx: Any, force_full_sync: bool = False) -> Any:
        self._maybe_raise()
        return None

    async def get_jobs(self, db: Any, *, id: UUID, ctx: Any, limit: int = 100) -> List[Any]:
        self._maybe_raise()
        return []

    async def cancel_job(
        self, db: Any, *, source_connection_id: UUID, job_id: UUID, ctx: Any
    ) -> Any:
        self._maybe_raise()
        return None

    async def complete_oauth1_callback(
        self, db: Any, *, oauth_token: str, oauth_verifier: str
    ) -> Any:
        self._maybe_raise()
        return None

    async def complete_oauth2_callback(self, db: Any, *, state: str, code: str) -> Any:
        self._maybe_raise()
        return None

    # Test helpers

    def seed(self, *connections: Any) -> None:
        """Add pre-built connections."""
        for conn in connections:
            self._connections[conn.id] = conn

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        """Configure error injection."""
        self._should_raise = exc

    def clear(self) -> None:
        """Reset state."""
        self._should_raise = None
        self._connections.clear()
