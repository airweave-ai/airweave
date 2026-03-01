"""In-memory fake context cache for testing."""

from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.core.protocols.cache import ContextCache


class FakeContextCache(ContextCache):
    """Dict-backed fake. Records all calls for test assertions."""

    def __init__(self) -> None:
        self._orgs: dict[UUID, schemas.Organization] = {}
        self._users: dict[str, schemas.User] = {}
        self._api_keys: dict[str, UUID] = {}
        self._invalidations: list[tuple[str, str]] = []

    # --- Read ---

    async def get_organization(self, org_id: UUID) -> Optional[schemas.Organization]:
        return self._orgs.get(org_id)

    async def get_user(self, user_email: str) -> Optional[schemas.User]:
        return self._users.get(user_email)

    async def get_api_key_org_id(self, api_key: str) -> Optional[UUID]:
        return self._api_keys.get(api_key)

    # --- Write ---

    async def set_organization(self, organization: schemas.Organization) -> None:
        self._orgs[organization.id] = organization

    async def set_user(self, user: schemas.User) -> None:
        self._users[user.email] = user

    async def set_api_key_org_id(self, api_key: str, org_id: UUID) -> None:
        self._api_keys[api_key] = org_id

    # --- Invalidation ---

    async def invalidate_organization(self, org_id: UUID) -> None:
        self._orgs.pop(org_id, None)
        self._invalidations.append(("org", str(org_id)))

    async def invalidate_user(self, user_email: str) -> None:
        self._users.pop(user_email, None)
        self._invalidations.append(("user", user_email))

    async def invalidate_api_key(self, api_key: str) -> None:
        self._api_keys.pop(api_key, None)
        self._invalidations.append(("api_key", api_key))

    # --- Test helpers ---

    def assert_invalidated(self, entity_type: str, key: str) -> None:
        for t, k in self._invalidations:
            if t == entity_type and k == key:
                return
        raise AssertionError(
            f"Expected invalidation ({entity_type}, {key}) not found. "
            f"Invalidations: {self._invalidations}"
        )
