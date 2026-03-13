"""Fake access control membership repository for testing."""

from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.access_control_membership import AccessControlMembership


class FakeAccessControlMembershipRepository:
    """In-memory fake for AccessControlMembershipRepositoryProtocol."""

    def __init__(self) -> None:
        self._memberships: List[AccessControlMembership] = []

    async def bulk_create(
        self,
        db: AsyncSession,
        memberships: List,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> int:
        return len(memberships)

    async def upsert(
        self,
        db: AsyncSession,
        *,
        member_id: str,
        member_type: str,
        group_id: str,
        group_name: str,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> None:
        pass

    async def delete_by_key(
        self,
        db: AsyncSession,
        *,
        member_id: str,
        member_type: str,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        return 0

    async def delete_by_group(
        self,
        db: AsyncSession,
        *,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        return 0

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        return [
            m
            for m in self._memberships
            if m.source_connection_id == source_connection_id
            and m.organization_id == organization_id
        ]

    async def bulk_delete(self, db: AsyncSession, ids: List[UUID]) -> int:
        before = len(self._memberships)
        self._memberships = [m for m in self._memberships if m.id not in ids]
        return before - len(self._memberships)

    async def get_by_member(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        return [
            m
            for m in self._memberships
            if m.member_id == member_id
            and m.member_type == member_type
            and m.organization_id == organization_id
        ]

    async def get_by_member_and_collection(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        return []

    async def get_memberships_by_groups(
        self,
        db: AsyncSession,
        *,
        group_ids: List[str],
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        return [
            m
            for m in self._memberships
            if m.group_id in group_ids
            and m.source_connection_id == source_connection_id
            and m.organization_id == organization_id
        ]

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        before = len(self._memberships)
        self._memberships = [
            m
            for m in self._memberships
            if not (
                m.source_connection_id == source_connection_id
                and m.organization_id == organization_id
            )
        ]
        return before - len(self._memberships)
