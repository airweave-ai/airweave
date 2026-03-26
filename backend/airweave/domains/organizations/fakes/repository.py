"""Fake organization repositories for testing."""

from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.exceptions import NotFoundException
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.organizations.protocols import ApiKeyMaintenanceProtocol
from airweave.models.api_key import APIKey
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization


class FakeOrganizationRepository:
    """In-memory fake for OrganizationRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Organization] = {}
        self._calls: list[tuple] = []

    def seed(self, organization_id: UUID, obj: Organization) -> None:
        self._store[organization_id] = obj

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx=None,
        skip_access_validation: bool = False,
        enrich: bool = False,
    ) -> Optional[schemas.Organization]:
        self._calls.append(("get", id))
        org = self._store.get(id)
        return org

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        self._calls.append(("get_by_id", organization_id))
        return self._store.get(organization_id)

    async def get_by_auth0_id(
        self,
        db: AsyncSession,
        *,
        auth0_org_id: str,
    ) -> Optional[Organization]:
        self._calls.append(("get_by_auth0_id", auth0_org_id))
        for org in self._store.values():
            if getattr(org, "auth0_org_id", None) == auth0_org_id:
                return org
        return None

    async def create_from_identity(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: str,
        auth0_org_id: str,
    ) -> Organization:
        org = Organization(id=uuid4(), name=name, description=description)
        org.auth0_org_id = auth0_org_id
        self._store[org.id] = org
        self._calls.append(("create_from_identity", auth0_org_id))
        return org

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.OrganizationCreate,
        owner_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> Organization:
        from uuid import uuid4

        org = Organization(id=uuid4(), name=obj_in.name, description=obj_in.description)
        self._store[org.id] = org
        self._calls.append(("create_with_owner", org.id, owner_user.id))
        return org

    async def delete(self, db: AsyncSession, *, organization_id: UUID) -> Organization:
        self._calls.append(("delete", organization_id))
        org = self._store.pop(organization_id, None)
        if org is None:
            raise NotFoundException(f"Organization with ID {organization_id} not found")
        return org


class FakeUserOrganizationRepository:
    """In-memory fake for UserOrganizationRepositoryProtocol."""

    def __init__(self, default_count: int = 0) -> None:
        self._counts: dict[UUID, int] = {}
        self._memberships: list[dict] = []
        self._default_count = default_count
        self._calls: list[tuple] = []

    def set_count(self, organization_id: UUID, count: int) -> None:
        self._counts[organization_id] = count

    def seed_membership(
        self, user_id: UUID, org_id: UUID, role: str = "member", is_primary: bool = False
    ) -> None:
        self._memberships.append(
            {"user_id": user_id, "org_id": org_id, "role": role, "is_primary": is_primary}
        )

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        self._calls.append(("count_members", organization_id))
        return self._counts.get(organization_id, self._default_count)

    async def get_membership(
        self, db: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> Optional[UserOrganization]:
        self._calls.append(("get_membership", org_id, user_id))
        for m in self._memberships:
            if m["user_id"] == user_id and m["org_id"] == org_id:
                uo = UserOrganization()
                uo.user_id = user_id
                uo.organization_id = org_id
                uo.role = m["role"]
                uo.is_primary = m["is_primary"]
                return uo
        return None

    async def get_members_with_users(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[tuple[User, str, bool]]:
        self._calls.append(("get_members_with_users", organization_id))
        return []

    async def get_owners(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        exclude_user_id: Optional[UUID] = None,
    ) -> list[UserOrganization]:
        self._calls.append(("get_owners", organization_id, exclude_user_id))
        results = []
        for m in self._memberships:
            if m["org_id"] == organization_id and m["role"] == "owner":
                if exclude_user_id and m["user_id"] == exclude_user_id:
                    continue
                uo = UserOrganization()
                uo.user_id = m["user_id"]
                uo.organization_id = organization_id
                uo.role = "owner"
                results.append(uo)
        return results

    async def get_user_memberships_with_orgs(
        self, db: AsyncSession, *, user_id: UUID
    ) -> list[schemas.OrganizationWithRole]:
        self._calls.append(("get_user_memberships_with_orgs", user_id))
        return []

    async def get_user_memberships_with_auth0_ids(
        self, db: AsyncSession, *, user_id: UUID
    ) -> list[tuple]:
        self._calls.append(("get_user_memberships_with_auth0_ids", user_id))
        results = []
        for m in self._memberships:
            if m["user_id"] == user_id:
                from airweave.models.user_organization import UserOrganization

                uo = UserOrganization()
                uo.user_id = m["user_id"]
                uo.organization_id = m["org_id"]
                uo.role = m.get("role", "member")
                results.append((uo, m.get("auth0_org_id")))
        return results

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        role: str,
        is_primary: bool = False,
    ) -> UserOrganization:
        self._calls.append(("create", user_id, organization_id, role))
        self._memberships.append(
            {"user_id": user_id, "org_id": organization_id, "role": role, "is_primary": is_primary}
        )
        uo = UserOrganization()
        uo.user_id = user_id
        uo.organization_id = organization_id
        uo.role = role
        uo.is_primary = is_primary
        return uo

    async def update_role(
        self, db: AsyncSession, *, user_id: UUID, organization_id: UUID, role: str
    ) -> bool:
        self._calls.append(("update_role", user_id, organization_id, role))
        for m in self._memberships:
            if m["user_id"] == user_id and m["org_id"] == organization_id:
                m["role"] = role
                return True
        return False

    async def delete_membership(
        self, db: AsyncSession, *, user_id: UUID, organization_id: UUID
    ) -> bool:
        self._calls.append(("delete_membership", user_id, organization_id))
        before = len(self._memberships)
        self._memberships = [
            m
            for m in self._memberships
            if not (m["user_id"] == user_id and m["org_id"] == organization_id)
        ]
        return len(self._memberships) < before

    async def delete_all_for_org(self, db: AsyncSession, *, organization_id: UUID) -> list[str]:
        self._calls.append(("delete_all_for_org", organization_id))
        self._memberships = [m for m in self._memberships if m["org_id"] != organization_id]
        return []

    async def set_primary(self, db: AsyncSession, *, user_id: UUID, organization_id: UUID) -> bool:
        self._calls.append(("set_primary", user_id, organization_id))
        return True

    async def count_user_orgs(self, db: AsyncSession, *, user_id: UUID) -> int:
        self._calls.append(("count_user_orgs", user_id))
        return sum(1 for m in self._memberships if m["user_id"] == user_id)


class FakeApiKeyRepository:
    """In-memory fake for ApiKeyRepositoryProtocol."""

    def __init__(self) -> None:
        self._keys: dict[str, object] = {}
        self._calls: list[tuple] = []

    def seed(self, key: str, *, organization_id: UUID, **extra) -> None:
        self._keys[key] = SimpleNamespace(
            id=uuid4(),
            organization_id=organization_id,
            created_by_email=extra.get("created_by_email", "test@test.com"),
        )

    async def get_by_key(self, db: AsyncSession, *, key: str):
        self._calls.append(("get_by_key", key))
        obj = self._keys.get(key)
        if not obj:
            raise NotFoundException("API key not found")
        return obj

    def call_count(self, method: str) -> int:
        return sum(1 for name, *_ in self._calls if name == method)


class FakeApiKeyMaintenanceRepository(ApiKeyMaintenanceProtocol):
    """In-memory fake for ApiKeyMaintenanceProtocol.

    Stores canned return values and records calls for assertion.
    Supports ``set_error()`` to simulate failures.
    """

    def __init__(self) -> None:
        self._calls: list[tuple] = []
        self._should_raise: Optional[Exception] = None
        self._revoked_keys: list[APIKey] = []
        self._expired_count: int = 0
        self._pruned_count: int = 0
        self._expiring_keys: list[APIKey] = []

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    def set_revoked_keys(self, keys: list[APIKey]) -> None:
        self._revoked_keys = keys

    def set_expired_count(self, count: int) -> None:
        self._expired_count = count

    def set_pruned_count(self, count: int) -> None:
        self._pruned_count = count

    def set_expiring_keys(self, keys: list[APIKey]) -> None:
        self._expiring_keys = keys

    def called(self, method: str) -> bool:
        return any(name == method for name, *_ in self._calls)

    def call_count(self, method: str) -> int:
        return sum(1 for name, *_ in self._calls if name == method)

    async def get_revoked_keys_older_than(
        self,
        db: AsyncSession,
        *,
        max_age_days: int = 90,
    ) -> list[APIKey]:
        self._calls.append(("get_revoked_keys_older_than", max_age_days))
        if self._should_raise:
            raise self._should_raise
        return self._revoked_keys

    async def expire_past_due_keys(self, db: AsyncSession) -> int:
        self._calls.append(("expire_past_due_keys",))
        if self._should_raise:
            raise self._should_raise
        return self._expired_count

    async def prune_usage_log(
        self,
        db: AsyncSession,
        *,
        max_age_days: int = 90,
        batch_size: int = 10_000,
    ) -> int:
        self._calls.append(("prune_usage_log", max_age_days, batch_size))
        if self._should_raise:
            raise self._should_raise
        return self._pruned_count

    async def get_keys_expiring_in_range(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
    ) -> list[APIKey]:
        self._calls.append(("get_keys_expiring_in_range", start_date, end_date))
        if self._should_raise:
            raise self._should_raise
        return self._expiring_keys
