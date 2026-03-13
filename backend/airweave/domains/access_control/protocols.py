"""Protocols for the access control domain."""

from typing import List, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.access_control_membership import AccessControlMembership


class AccessControlMembershipRepositoryProtocol(Protocol):
    """Data access for access control memberships."""

    async def bulk_create(
        self,
        db: AsyncSession,
        memberships: List,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> int: ...

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
    ) -> None: ...

    async def delete_by_key(
        self,
        db: AsyncSession,
        *,
        member_id: str,
        member_type: str,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int: ...

    async def delete_by_group(
        self,
        db: AsyncSession,
        *,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int: ...

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]: ...

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: List[UUID],
    ) -> int: ...

    async def get_by_member(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]: ...

    async def get_by_member_and_collection(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]: ...

    async def get_memberships_by_groups(
        self,
        db: AsyncSession,
        *,
        group_ids: List[str],
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]: ...

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int: ...
