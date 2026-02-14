"""Fake integration credential repository for testing."""

from typing import Any, Optional
from uuid import uuid4


class FakeIntegrationCredentialRepository:
    """In-memory fake for IntegrationCredentialRepositoryProtocol.

    Stores credentials in a dict keyed by ID. Returns simple namespace
    objects so tests can access .id, .encrypted_credentials, etc.
    """

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[Any, Any] = {}

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Store a credential and return a fake ORM object."""
        cred_id = uuid4()
        record = type(
            "FakeCredential",
            (),
            {
                "id": cred_id,
                "name": getattr(obj_in, "name", ""),
                "integration_short_name": getattr(obj_in, "integration_short_name", ""),
                "encrypted_credentials": getattr(obj_in, "encrypted_credentials", ""),
                "authentication_method": getattr(obj_in, "authentication_method", None),
                "oauth_type": getattr(obj_in, "oauth_type", None),
                "auth_config_class": getattr(obj_in, "auth_config_class", None),
            },
        )()
        self._store[cred_id] = record
        return record

    async def get(self, db: Any, *, id: Any, ctx: Any) -> Optional[Any]:
        """Get a credential by ID, or None."""
        return self._store.get(id)

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update a credential's fields from obj_in."""
        if hasattr(obj_in, "encrypted_credentials") and obj_in.encrypted_credentials is not None:
            db_obj.encrypted_credentials = obj_in.encrypted_credentials
        return db_obj

    # Test helpers

    def clear(self) -> None:
        """Remove all stored credentials."""
        self._store.clear()

    @property
    def created_count(self) -> int:
        """Number of credentials created."""
        return len(self._store)
