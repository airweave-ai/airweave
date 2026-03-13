"""Access broker for resolving user access context."""

from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.access_control.protocols import AccessControlMembershipRepositoryProtocol
from airweave.platform.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


class AccessBroker:
    """Resolves user access context by expanding group memberships."""

    def __init__(self, acl_repo: AccessControlMembershipRepositoryProtocol) -> None:
        """Initialize with ACL membership repository."""
        self._acl_repo = acl_repo

    async def resolve_access_context(
        self, db: AsyncSession, user_principal: str, organization_id: UUID
    ) -> AccessContext:
        """Resolve user's access context by expanding group memberships.

        Steps:
        1. Query database for user's direct group memberships
        2. Recursively expand group-to-group relationships (if any)
        3. Build AccessContext with user + all expanded group principals

        Note: SharePoint uses /transitivemembers so group expansion happens
        server-side. Other sources may store group-group tuples that need
        recursive expansion here.
        """
        memberships = await self._acl_repo.get_by_member(
            db=db, member_id=user_principal, member_type="user", organization_id=organization_id
        )

        user_principals = [f"user:{user_principal}"]

        all_groups = await self._expand_group_memberships(
            db=db, group_ids=[m.group_id for m in memberships], organization_id=organization_id
        )

        return AccessContext(
            user_principal=user_principal,
            user_principals=user_principals,
            group_principals=[f"group:{g}" for g in all_groups],
        )

    async def resolve_access_context_for_collection(
        self,
        db: AsyncSession,
        user_principal: str,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> Optional[AccessContext]:
        """Resolve user's access context scoped to a collection's source connections.

        Returns None if the collection has no sources with access control
        support, allowing the search layer to skip filtering entirely.
        """
        has_ac_sources = await self._collection_has_ac_sources(
            db=db,
            readable_collection_id=readable_collection_id,
            organization_id=organization_id,
        )

        if not has_ac_sources:
            return None

        memberships = await self._acl_repo.get_by_member_and_collection(
            db=db,
            member_id=user_principal,
            member_type="user",
            readable_collection_id=readable_collection_id,
            organization_id=organization_id,
        )

        user_principals = [f"user:{user_principal}"]

        all_groups = await self._expand_group_memberships(
            db=db, group_ids=[m.group_id for m in memberships], organization_id=organization_id
        )

        return AccessContext(
            user_principal=user_principal,
            user_principals=user_principals,
            group_principals=[f"group:{g}" for g in all_groups],
        )

    async def _collection_has_ac_sources(
        self,
        db: AsyncSession,
        readable_collection_id: str,
        organization_id: UUID,
    ) -> bool:
        """Check if a collection has any sources with access control enabled."""
        from sqlalchemy import exists, select

        from airweave.models.access_control_membership import AccessControlMembership
        from airweave.models.source_connection import SourceConnection

        stmt = select(
            exists(
                select(AccessControlMembership.id)
                .join(
                    SourceConnection,
                    AccessControlMembership.source_connection_id == SourceConnection.id,
                )
                .where(
                    AccessControlMembership.organization_id == organization_id,
                    SourceConnection.readable_collection_id == readable_collection_id,
                )
            )
        )

        result = await db.execute(stmt)
        return result.scalar() or False

    async def _expand_group_memberships(
        self, db: AsyncSession, group_ids: List[str], organization_id: UUID
    ) -> Set[str]:
        """Recursively expand group memberships to handle nested groups.

        Max depth of 10 to prevent infinite loops from circular group references.
        """
        all_groups = set(group_ids)
        to_process = set(group_ids)
        visited = set()

        max_depth = 10
        depth = 0

        while to_process and depth < max_depth:
            current_group = to_process.pop()
            if current_group in visited:
                continue
            visited.add(current_group)

            nested_memberships = await self._acl_repo.get_by_member(
                db=db, member_id=current_group, member_type="group", organization_id=organization_id
            )

            for m in nested_memberships:
                if m.group_id not in all_groups:
                    all_groups.add(m.group_id)
                    to_process.add(m.group_id)

            depth += 1

        return all_groups

    def check_entity_access(
        self, entity_access: Optional[AccessControl], access_context: Optional[AccessContext]
    ) -> bool:
        """Check if user can access entity based on access control."""
        if entity_access is None:
            return True

        if entity_access.is_public:
            return True

        if access_context is None:
            return True

        if not entity_access.viewers:
            return True

        return bool(access_context.all_principals & set(entity_access.viewers))
