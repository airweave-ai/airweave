"""Infrastructure context builder."""

from uuid import UUID

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.logging import LoggerConfigurator
from airweave.platform.contexts.infra import InfraContext


class InfraContextBuilder:
    """Builds infrastructure context."""

    @classmethod
    def build(
        cls,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> InfraContext:
        """Build infrastructure context for sync operations.

        Args:
            sync: Sync configuration
            sync_job: The sync job being executed
            collection: Target collection
            source_connection_id: Source connection ID for logging dimensions
            ctx: API context

        Returns:
            InfraContext containing ctx and logger.
        """
        contextual_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(ctx.organization.id),
                "source_connection_id": str(source_connection_id),
                "collection_readable_id": str(collection.readable_id),
                "organization_name": ctx.organization.name,
                "scheduled": str(sync_job.scheduled),
            },
        )

        return InfraContext(ctx=ctx, logger=contextual_logger)

    @classmethod
    def build_minimal(
        cls,
        ctx: ApiContext,
        operation: str,
        sync_id: UUID,
        collection_id: UUID,
    ) -> InfraContext:
        """Build minimal infrastructure for non-sync operations.

        Use this for cleanup, webhooks, and other operations that don't
        have a full sync context.

        Args:
            ctx: API context
            operation: Operation name for logging (e.g., "cleanup", "webhook")
            sync_id: Sync ID for logging
            collection_id: Collection ID for logging

        Returns:
            InfraContext with minimal logger.
        """
        contextual_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.cleanup",
            dimensions={
                "operation": operation,
                "sync_id": str(sync_id),
                "collection_id": str(collection_id),
                "organization_id": str(ctx.organization.id),
            },
        )

        return InfraContext(ctx=ctx, logger=contextual_logger)
