"""CRUD operations for access control memberships."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.access_control_membership import AccessControlMembership
from airweave.schemas.access_control import AccessControlMembershipCreate


class CRUDAccessControlMembership(
    CRUDBaseOrganization[
        AccessControlMembership, AccessControlMembershipCreate, AccessControlMembershipCreate
    ]
):
    """CRUD operations for access control memberships."""

    async def get_by_member(
        self, db: AsyncSession, member_id: str, member_type: str, organization_id: UUID
    ) -> List[AccessControlMembership]:
        """Get all group memberships for a member (user or group).

        Args:
            db: Database session
            member_id: Member identifier (email for users, ID for groups)
            member_type: "user" or "group"
            organization_id: Organization ID for multi-tenant isolation

        Returns:
            List of AccessControlMembership objects
        """
        stmt = select(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.member_id == member_id,
            AccessControlMembership.member_type == member_type,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_member_and_collection(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a user scoped to a specific collection's source connections.

        This method only returns memberships from source connections that belong to the
        specified collection, enabling collection-scoped access control.

        Args:
            db: Database session
            member_id: Member identifier (email for users, ID for groups)
            member_type: "user" or "group"
            readable_collection_id: Collection readable_id (string) to scope the query
            organization_id: Organization ID for multi-tenant isolation

        Returns:
            List of AccessControlMembership objects scoped to the collection
        """
        from airweave.models.source_connection import SourceConnection

        # Join AccessControlMembership with SourceConnection to filter by collection
        stmt = (
            select(AccessControlMembership)
            .join(
                SourceConnection,
                AccessControlMembership.source_connection_id == SourceConnection.id,
            )
            .where(
                AccessControlMembership.organization_id == organization_id,
                AccessControlMembership.member_id == member_id,
                AccessControlMembership.member_type == member_type,
                SourceConnection.readable_collection_id == readable_collection_id,
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(
        self,
        db: AsyncSession,
        memberships: List,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> int:
        """Bulk upsert memberships using PostgreSQL ON CONFLICT.

        Uses the unique constraint (org, member_id, member_type, group_id, source_connection_id)
        to gracefully handle duplicates. If duplicate exists, updates group_name.

        Args:
            db: Database session
            memberships: List of AccessControlMembership Pydantic objects
            organization_id: Organization ID
            source_connection_id: Source connection ID
            source_name: Source short name (e.g., "sharepoint")

        Returns:
            Number of memberships processed
        """
        from sqlalchemy.dialects.postgresql import insert

        if not memberships:
            return 0

        # Build list of membership dicts for bulk insert
        membership_data = [
            {
                "organization_id": organization_id,
                "source_connection_id": source_connection_id,
                "source_name": source_name,
                "member_id": m.member_id,
                "member_type": m.member_type,
                "group_id": m.group_id,
                "group_name": m.group_name,
            }
            for m in memberships
        ]

        # Use PostgreSQL INSERT ... ON CONFLICT for upsert
        stmt = insert(AccessControlMembership).values(membership_data)

        # On conflict (duplicate), update the group_name if changed
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "organization_id",
                "member_id",
                "member_type",
                "group_id",
                "source_connection_id",
            ],
            set_={"group_name": stmt.excluded.group_name},
        )

        await db.execute(stmt)
        await db.commit()

        return len(memberships)


# Singleton instance
access_control_membership = CRUDAccessControlMembership(AccessControlMembership)
