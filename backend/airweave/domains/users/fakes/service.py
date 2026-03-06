"""Fake user service for testing."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.domains.users.logic import CreateOrUpdateResult
from airweave.domains.users.protocols import UserServiceProtocol


class FakeUserService(UserServiceProtocol):
    """In-memory fake that records calls and returns canned responses."""

    def __init__(self) -> None:
        self._calls: list[tuple[str, ...]] = []

    async def create_or_update(
        self,
        db: AsyncSession,
        user_data: schemas.UserCreate,
        auth0_user: Any,
    ) -> CreateOrUpdateResult:
        """Return a canned CreateOrUpdateResult."""
        self._calls.append(("create_or_update", user_data.email))
        now = datetime.utcnow()
        user = schemas.User(
            id=uuid4(),
            email=user_data.email,
            full_name=user_data.full_name,
            auth0_id=getattr(auth0_user, "id", None),
            created_at=now,
            modified_at=now,
        )
        return CreateOrUpdateResult(user=user, is_new=True)

    async def get_user_organizations(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> list[schemas.OrganizationWithRole]:
        """Return empty organization list."""
        self._calls.append(("get_user_organizations", str(user_id)))
        return []

    def call_count(self, method: str) -> int:
        """Return call count for a method name."""
        return sum(1 for name, *_ in self._calls if name == method)
