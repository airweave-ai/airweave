"""Protocol for integration credential data access.

Cross-cutting: used by CredentialService, and in future by destinations,
token manager, auth providers, and any domain that persists credentials.
"""

from typing import Any, Optional, Protocol


class IntegrationCredentialRepositoryProtocol(Protocol):
    """Data access for integration credentials."""

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create an integration credential record."""
        ...

    async def get(self, db: Any, *, id: Any, ctx: Any) -> Optional[Any]:
        """Get an integration credential by ID."""
        ...

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update an integration credential."""
        ...
