"""Access broker for resolving user access context."""

from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.platform.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


class AccessBroker:
    """Resolves user access context by expanding group memberships.

    Source-agnostic: works for SharePoint, Google Drive, etc.
    Handles both direct user-group and nested group-group relationships.

    Access control is only applied when at least one source in the collection
    has supports_access_control=True. For collections with only non-AC sources,
    no filtering is applied (all entities visible to everyone).
    """

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

        Args:
            db: Database session
            user_principal: User principal (username or identifier)
            organization_id: Organization ID

        Returns:
            AccessContext with fully expanded principals
        """
        # Query direct user-group memberships (member_type="user")
        memberships = await crud.access_control_membership.get_by_member(
            db=db, member_id=user_principal, member_type="user", organization_id=organization_id
        )

        # Build principals
        user_principals = [f"user:{user_principal}"]

        # Recursively expand group-to-group relationships (if any exist)
        # For SharePoint: no group-group tuples exist (uses /transitivemembers)
        # For other sources: this handles nested group expansion
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

        This method only considers group memberships from source connections that belong
        to the specified collection, enabling collection-scoped access control.

        IMPORTANT: Returns None if the collection has no sources with access control
        support. This allows the search layer to skip filtering entirely for collections
        that only contain sources like Slack, Asana, etc.

        Steps:
        1. Check if collection has any sources with access control
        2. If no AC sources, return None (no filtering needed)
        3. Query database for user's group memberships within the collection
        4. Recursively expand group-to-group relationships (if any)
        5. Build AccessContext with user + all expanded group principals

        Args:
            db: Database session
            user_principal: User principal (username or identifier)
            readable_collection_id: Collection readable_id (string) to scope the access context
            organization_id: Organization ID

        Returns:
            AccessContext with fully expanded principals scoped to collection,
            or None if collection has no access-control-enabled sources
        """
        # Check if collection has any sources with access control
        has_ac_sources = await self._collection_has_ac_sources(
            db=db,
            readable_collection_id=readable_collection_id,
            organization_id=organization_id,
        )

        if not has_ac_sources:
            # No access control sources in collection → skip filtering
            return None

        # Query user-group memberships scoped to collection (member_type="user")
        memberships = await crud.access_control_membership.get_by_member_and_collection(
            db=db,
            member_id=user_principal,
            member_type="user",
            readable_collection_id=readable_collection_id,
            organization_id=organization_id,
        )

        # Build principals
        user_principals = [f"user:{user_principal}"]

        # Recursively expand group-to-group relationships (if any exist)
        # Note: Group expansion is still organization-wide, not collection-scoped
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
        """Check if a collection has any sources with access control enabled.

        This queries the access_control_membership table to see if there are
        any memberships for this collection. If there are memberships, at least
        one source in the collection supports access control.

        Args:
            db: Database session
            readable_collection_id: Collection readable_id
            organization_id: Organization ID

        Returns:
            True if collection has at least one AC-enabled source
        """
        from sqlalchemy import exists, select

        from airweave.models.access_control_membership import AccessControlMembership
        from airweave.models.source_connection import SourceConnection

        # Check if any memberships exist for source connections in this collection
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

        For sources that store group-to-group relationships (e.g., Google Drive),
        this recursively expands nested groups via CRUD layer. For SharePoint,
        /transitivemembers handles this server-side, so no group-group tuples exist.

        Args:
            db: Database session
            group_ids: List of initial group IDs
            organization_id: Organization ID

        Returns:
            Set of all group IDs (direct + transitive)
        """
        all_groups = set(group_ids)
        to_process = set(group_ids)
        visited = set()

        # Recursively expand (max depth: 10 to prevent infinite loops)
        max_depth = 10
        depth = 0

        while to_process and depth < max_depth:
            current_group = to_process.pop()
            if current_group in visited:
                continue
            visited.add(current_group)

            # Query for group-to-group memberships via CRUD layer (member_type="group")
            nested_memberships = await crud.access_control_membership.get_by_member(
                db=db, member_id=current_group, member_type="group", organization_id=organization_id
            )

            # Add parent groups and queue for processing
            for m in nested_memberships:
                if m.group_id not in all_groups:
                    all_groups.add(m.group_id)
                    to_process.add(m.group_id)

            depth += 1

        return all_groups

    def check_entity_access(
        self, entity_access: Optional[AccessControl], access_context: Optional[AccessContext]
    ) -> bool:
        """Check if user can access entity based on access control.

        Args:
            entity_access: Entity's AccessControl field (entity.access), may be None
            access_context: User's AccessContext (from resolve_access_context), may be None

        Returns:
            True if user has access to the entity:
            - True if entity_access is None (no AC = public for non-AC sources)
            - True if entity_access.is_public is True
            - True if access_context is None (no AC context = no filtering)
            - True if any of user's principals match entity.access.viewers
            - False otherwise
        """
        # No access control on entity = visible to everyone (non-AC source)
        if entity_access is None:
            return True

        # Public entity = visible to everyone
        if entity_access.is_public:
            return True

        # No access context = no filtering (collection has no AC sources)
        if access_context is None:
            return True

        # No viewers specified = visible to everyone (legacy behavior)
        if not entity_access.viewers:
            return True

        # Check if any principal matches
        return bool(access_context.all_principals & set(entity_access.viewers))


# Singleton shared instance
access_broker = AccessBroker()
