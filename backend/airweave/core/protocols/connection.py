"""Protocol for connection data access.

Cross-cutting: used by source connections, search, source builder.
"""

from typing import Any, Optional, Protocol
from uuid import UUID


class ConnectionRepositoryProtocol(Protocol):
    """Data access for Connection records."""

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create a connection record."""
        ...

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a connection by ID."""
        ...

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get a connection by readable ID."""
        ...
