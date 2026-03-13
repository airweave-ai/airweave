"""Fake access broker for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


class FakeAccessBroker:
    """In-memory fake for AccessBrokerProtocol.

    Returns a simple access context with just the user principal.
    Override `_access_context` to customize resolution behavior in tests.
    """

    def __init__(self) -> None:
        self._access_context: Optional[AccessContext] = None

    async def resolve_access_context(
        self,
        db: AsyncSession,
        user_principal: str,
        organization_id: UUID,
    ) -> AccessContext:
        if self._access_context is not None:
            return self._access_context
        return AccessContext(
            user_principal=user_principal,
            user_principals=[f"user:{user_principal}"],
            group_principals=[],
        )

    async def resolve_access_context_for_collection(
        self,
        db: AsyncSession,
        user_principal: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> Optional[AccessContext]:
        if self._access_context is not None:
            return self._access_context
        return None

    def check_entity_access(
        self,
        entity_access: Optional[AccessControl],
        access_context: Optional[AccessContext],
    ) -> bool:
        if entity_access is None:
            return True
        if entity_access.is_public:
            return True
        if access_context is None:
            return True
        if not entity_access.viewers:
            return True
        return bool(access_context.all_principals & set(entity_access.viewers))
