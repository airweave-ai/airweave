"""Scope context builder."""

from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.platform.contexts.scope import ScopeContext


class ScopeContextBuilder:
    """Builds scope context for operations."""

    @classmethod
    def build(
        cls,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: ApiContext,
        job_id: Optional[UUID] = None,
    ) -> ScopeContext:
        """Build scope context.

        Args:
            sync: Sync configuration
            collection: Target collection
            ctx: API context
            job_id: Optional job ID (for sync jobs)

        Returns:
            ScopeContext with all scope identifiers.
        """
        return ScopeContext(
            sync_id=sync.id,
            collection_id=collection.id,
            organization_id=ctx.organization.id,
            job_id=job_id,
        )

    @classmethod
    def build_minimal(
        cls,
        sync_id: UUID,
        collection_id: UUID,
        organization_id: UUID,
        job_id: Optional[UUID] = None,
    ) -> ScopeContext:
        """Build scope context from raw IDs.

        Use for cleanup and other non-sync operations.

        Args:
            sync_id: Sync ID
            collection_id: Collection ID
            organization_id: Organization ID
            job_id: Optional job ID

        Returns:
            ScopeContext with provided identifiers.
        """
        return ScopeContext(
            sync_id=sync_id,
            collection_id=collection_id,
            organization_id=organization_id,
            job_id=job_id,
        )
