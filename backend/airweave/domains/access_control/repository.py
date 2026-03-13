"""Access control membership repository wrapping crud.access_control_membership."""

from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.models.access_control_membership import AccessControlMembership


class AccessControlMembershipRepository:
    """Delegates to the crud.access_control_membership singleton."""

    async def bulk_create(
        self,
        db: AsyncSession,
        memberships: List,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> int:
        """Bulk-insert membership rows."""
        return await crud.access_control_membership.bulk_create(
            db, memberships, organization_id, source_connection_id, source_name
        )

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
        """Insert or update a single membership."""
        return await crud.access_control_membership.upsert(
            db,
            member_id=member_id,
            member_type=member_type,
            group_id=group_id,
            group_name=group_name,
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_name=source_name,
        )

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
        """Delete a membership by its composite key."""
        return await crud.access_control_membership.delete_by_key(
            db,
            member_id=member_id,
            member_type=member_type,
            group_id=group_id,
            source_connection_id=source_connection_id,
            organization_id=organization_id,
        )

    async def delete_by_group(
        self,
        db: AsyncSession,
        *,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a group."""
        return await crud.access_control_membership.delete_by_group(
            db,
            group_id=group_id,
            source_connection_id=source_connection_id,
            organization_id=organization_id,
        )

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get all memberships for a source connection."""
        return await crud.access_control_membership.get_by_source_connection(
            db, source_connection_id, organization_id
        )

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: List[UUID],
    ) -> int:
        """Bulk-delete memberships by ID."""
        return await crud.access_control_membership.bulk_delete(db, ids)

    async def get_by_member(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a specific member."""
        return await crud.access_control_membership.get_by_member(
            db, member_id, member_type, organization_id
        )

    async def get_by_member_and_collection(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships scoped to a collection."""
        return await crud.access_control_membership.get_by_member_and_collection(
            db, member_id, member_type, readable_collection_id, organization_id
        )

    async def get_memberships_by_groups(
        self,
        db: AsyncSession,
        *,
        group_ids: List[str],
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a set of group IDs."""
        return await crud.access_control_membership.get_memberships_by_groups(
            db,
            group_ids=group_ids,
            source_connection_id=source_connection_id,
            organization_id=organization_id,
        )

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a source connection."""
        return await crud.access_control_membership.delete_by_source_connection(
            db, source_connection_id, organization_id
        )
