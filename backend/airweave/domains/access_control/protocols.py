"""Protocols for the access control domain."""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.access_control.actions import (
    ACActionBatch,
    ACDeleteAction,
    ACInsertAction,
    ACUpdateAction,
    ACUpsertAction,
)
from airweave.domains.access_control.schemas import AccessContext, MembershipTuple
from airweave.domains.sync_pipeline.contexts import SyncContext
from airweave.models.access_control_membership import AccessControlMembership
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


class ACActionResolverProtocol(Protocol):
    """Resolves membership tuples to action objects."""

    async def resolve(
        self,
        memberships: List[MembershipTuple],
        sync_context: SyncContext,
    ) -> ACActionBatch:
        """Resolve memberships to actions."""
        ...


class ACActionDispatcherProtocol(Protocol):
    """Dispatches resolved AC membership actions to handlers."""

    async def dispatch(
        self,
        batch: ACActionBatch,
        sync_context: SyncContext,
    ) -> int:
        """Dispatch action batch to all handlers."""
        ...


@runtime_checkable
class ACActionHandler(Protocol):
    """Protocol for access control membership action handlers.

    Handlers receive resolved AC actions and persist them to their destination.

    Contract:
    - Handlers MUST be idempotent (safe to retry on failure)
    - Handlers MUST raise SyncFailureError for non-recoverable errors
    """

    @property
    def name(self) -> str:
        """Handler name for logging and debugging."""
        ...

    async def handle_batch(
        self,
        batch: "ACActionBatch",
        sync_context: "SyncContext",
    ) -> int:
        """Handle a full action batch (main entry point)."""
        ...

    async def handle_upserts(
        self,
        actions: List["ACUpsertAction"],
        sync_context: "SyncContext",
    ) -> int:
        """Handle upsert actions."""
        ...

    async def handle_inserts(
        self,
        actions: List["ACInsertAction"],
        sync_context: "SyncContext",
    ) -> int:
        """Handle insert actions."""
        ...

    async def handle_updates(
        self,
        actions: List["ACUpdateAction"],
        sync_context: "SyncContext",
    ) -> int:
        """Handle update actions."""
        ...

    async def handle_deletes(
        self,
        actions: List["ACDeleteAction"],
        sync_context: "SyncContext",
    ) -> int:
        """Handle delete actions."""
        ...
