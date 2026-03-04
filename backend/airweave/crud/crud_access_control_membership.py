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

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get all memberships for a specific source connection.

        Used for orphan detection during ACL sync - compares memberships
        in the database against memberships encountered during sync.

        Args:
            db: Database session
            source_connection_id: Source connection ID to filter by
            organization_id: Organization ID for multi-tenant isolation

        Returns:
            List of AccessControlMembership objects for this source connection
        """
        stmt = select(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.source_connection_id == source_connection_id,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: List[UUID],
    ) -> int:
        """Delete memberships by their database IDs.

        Used for orphan cleanup - removes memberships that exist in the
        database but were not encountered during the latest sync
        (i.e., permissions that were revoked at the source).

        Args:
            db: Database session
            ids: List of membership database IDs to delete

        Returns:
            Number of memberships deleted
        """
        from sqlalchemy import delete

        if not ids:
            return 0

        stmt = delete(AccessControlMembership).where(AccessControlMembership.id.in_(ids))
        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a source connection.

        Used when a source connection is deleted or for full ACL reset.

        Args:
            db: Database session
            source_connection_id: Source connection ID
            organization_id: Organization ID for multi-tenant isolation

        Returns:
            Number of memberships deleted
        """
        from sqlalchemy import delete

        stmt = delete(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.source_connection_id == source_connection_id,
        )
        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount

    # -------------------------------------------------------------------------
    # Incremental ACL sync methods
    # -------------------------------------------------------------------------

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
        """Upsert a single membership for incremental ACL adds.

        Uses PostgreSQL INSERT ON CONFLICT to insert or update a single
        membership record. Used during incremental DirSync to apply
        individual ADD changes.

        Args:
            db: Database session
            member_id: Member identifier
            member_type: "user" or "group"
            group_id: Group identifier
            group_name: Human-readable group name
            organization_id: Organization ID
            source_connection_id: Source connection ID
            source_name: Source short name
        """
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(AccessControlMembership).values(
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_name=source_name,
            member_id=member_id,
            member_type=member_type,
            group_id=group_id,
            group_name=group_name,
        )
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
        """Delete a specific membership by its composite natural key.

        Used during incremental DirSync to apply individual REMOVE changes.

        Args:
            db: Database session
            member_id: Member identifier
            member_type: "user" or "group"
            group_id: Group identifier
            source_connection_id: Source connection ID
            organization_id: Organization ID

        Returns:
            Number of rows deleted (0 or 1)
        """
        from sqlalchemy import delete

        stmt = delete(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.source_connection_id == source_connection_id,
            AccessControlMembership.member_id == member_id,
            AccessControlMembership.member_type == member_type,
            AccessControlMembership.group_id == group_id,
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def delete_by_group(
        self,
        db: AsyncSession,
        *,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a group that was deleted from AD.

        When DirSync reports a group deletion, all its membership records
        must be removed.

        Args:
            db: Database session
            group_id: Group identifier (e.g. "ad:engineering")
            source_connection_id: Source connection ID
            organization_id: Organization ID

        Returns:
            Number of rows deleted
        """
        from sqlalchemy import delete

        stmt = delete(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.source_connection_id == source_connection_id,
            AccessControlMembership.group_id == group_id,
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def get_memberships_by_groups(
        self,
        db: AsyncSession,
        *,
        group_ids: List[str],
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a set of groups.

        Used during incremental ACL sync to verify the current state of
        groups that DirSync reports as modified.

        Args:
            db: Database session
            group_ids: List of group identifiers to query
            source_connection_id: Source connection ID
            organization_id: Organization ID

        Returns:
            List of membership records for the specified groups
        """
        if not group_ids:
            return []

        stmt = select(AccessControlMembership).where(
            AccessControlMembership.organization_id == organization_id,
            AccessControlMembership.source_connection_id == source_connection_id,
            AccessControlMembership.group_id.in_(group_ids),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# Singleton instance
access_control_membership = CRUDAccessControlMembership(AccessControlMembership)
