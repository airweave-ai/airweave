"""Access broker for resolving user access context."""

from typing import List, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.platform.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


class AccessBroker:
    """Resolves user access context by expanding group memberships.

    Source-agnostic: works for SharePoint, Google Drive, etc.
    Handles both direct user-group and nested group-group relationships.
    """

    async def resolve_access_context(
        self, db: AsyncSession, user_email: str, organization_id: UUID
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
            user_email: User's email address
            organization_id: Organization ID

        Returns:
            AccessContext with fully expanded principals
        """
        # Query direct user-group memberships (member_type="user")
        memberships = await crud.access_control_membership.get_by_member(
            db=db, member_id=user_email, member_type="user", organization_id=organization_id
        )

        # Build principals
        user_principals = [f"user:{user_email}"]

        # Recursively expand group-to-group relationships (if any exist)
        # For SharePoint: no group-group tuples exist (uses /transitivemembers)
        # For other sources: this handles nested group expansion
        all_groups = await self._expand_group_memberships(
            db=db, group_ids=[m.group_id for m in memberships], organization_id=organization_id
        )

        return AccessContext(
            user_email=user_email,
            user_principals=user_principals,
            group_principals=[f"group:{g}" for g in all_groups],
        )

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
        self, entity_access: AccessControl, access_context: AccessContext
    ) -> bool:
        """Check if user can access entity based on access control.

        Args:
            entity_access: Entity's AccessControl field (entity.access)
            access_context: User's AccessContext (from resolve_access_context)

        Returns:
            True if any of user's principals match entity.access.viewers
        """
        if not entity_access or not entity_access.viewers:
            # No access control = public (for MVP)
            # TODO: Make configurable (default allow vs default deny)
            return True

        # Check if any principal matches
        return bool(access_context.all_principals & set(entity_access.viewers))
