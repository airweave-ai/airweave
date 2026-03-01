"""Context cache protocol for API request data.

Caches org/user/API-key data on the hot path (``deps.get_context``).
Adapters: Redis (production), in-memory dict (testing).

Invalidation strategy:
- 30s TTL as fallback for everything
- ``invalidate_organization`` + ``invalidate_user`` for instant invalidation
  on critical mutation paths (org create/delete, membership changes)
- Feature flags, billing plan changes, etc. rely on TTL — 30s max staleness
  is acceptable for admin operations
"""

from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from airweave import schemas


@runtime_checkable
class ContextCache(Protocol):
    """Cache for API context resolution (org, user, API key lookups)."""

    # --- Read ---

    async def get_organization(self, org_id: UUID) -> Optional[schemas.Organization]:
        """Return cached organization or None on miss."""
        ...

    async def get_user(self, user_email: str) -> Optional[schemas.User]:
        """Return cached user or None on miss."""
        ...

    async def get_api_key_org_id(self, api_key: str) -> Optional[UUID]:
        """Return cached org ID for an API key or None on miss."""
        ...

    # --- Write ---

    async def set_organization(self, organization: schemas.Organization) -> None:
        """Cache an organization."""
        ...

    async def set_user(self, user: schemas.User) -> None:
        """Cache a user."""
        ...

    async def set_api_key_org_id(self, api_key: str, org_id: UUID) -> None:
        """Cache an API key → org ID mapping."""
        ...

    # --- Invalidation ---

    async def invalidate_organization(self, org_id: UUID) -> None:
        """Remove cached organization entry."""
        ...

    async def invalidate_user(self, user_email: str) -> None:
        """Remove cached user entry."""
        ...

    async def invalidate_api_key(self, api_key: str) -> None:
        """Remove cached API key entry."""
        ...
