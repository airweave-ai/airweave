"""Protocols for the access control domain."""

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.access_control_membership import AccessControlMembership
from airweave.platform.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


class AccessControlMembershipRepositoryProtocol(Protocol):
    """Data access for access control memberships."""

    async def bulk_create(
        self,
        db: AsyncSession,
        memberships: List,
        organization_id: UUID,
        source_connection_id: UUID,
        source_name: str,
    ) -> int:
        """Bulk-insert membership rows."""
        ...

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
        ...

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
        ...

    async def delete_by_group(
        self,
        db: AsyncSession,
        *,
        group_id: str,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a group."""
        ...

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get all memberships for a source connection."""
        ...

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: List[UUID],
    ) -> int:
        """Bulk-delete memberships by ID."""
        ...

    async def get_by_member(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a specific member."""
        ...

    async def get_by_member_and_collection(
        self,
        db: AsyncSession,
        member_id: str,
        member_type: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships scoped to a collection."""
        ...

    async def get_memberships_by_groups(
        self,
        db: AsyncSession,
        *,
        group_ids: List[str],
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[AccessControlMembership]:
        """Get memberships for a set of group IDs."""
        ...

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Delete all memberships for a source connection."""
        ...


class AccessBrokerProtocol(Protocol):
    """Resolves user access context by expanding group memberships."""

    async def resolve_access_context(
        self,
        db: AsyncSession,
        user_principal: str,
        organization_id: UUID,
    ) -> AccessContext:
        """Resolve user's access context by expanding group memberships."""
        ...

    async def resolve_access_context_for_collection(
        self,
        db: AsyncSession,
        user_principal: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> Optional[AccessContext]:
        """Resolve user's access context scoped to a collection."""
        ...

    def check_entity_access(
        self,
        entity_access: Optional[AccessControl],
        access_context: Optional[AccessContext],
    ) -> bool:
        """Check if user can access entity based on access control."""
        ...
