"""Fake user repository for testing."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.exceptions import NotFoundException


class FakeUserRepository:
    """In-memory fake for UserRepositoryProtocol."""

    def __init__(self) -> None:
        self._users: dict[str, Any] = {}
        self._calls: list[tuple] = []

    def seed(self, email: str, user: Any) -> None:
        self._users[email] = user

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Any:
        self._calls.append(("get_by_email", email))
        user = self._users.get(email)
        if not user:
            raise NotFoundException(f"User with email {email} not found")
        return user

    async def update_user_no_auth(
        self, db: AsyncSession, *, id: UUID, obj_in: schemas.UserUpdate
    ) -> Any:
        self._calls.append(("update_user_no_auth", id))
        for user in self._users.values():
            if getattr(user, "id", None) == id:
                for field, value in obj_in.model_dump(exclude_unset=True).items():
                    setattr(user, field, value)
                return user
        raise NotFoundException(f"User with ID {id} not found")

    def call_count(self, method: str) -> int:
        return sum(1 for name, *_ in self._calls if name == method)
