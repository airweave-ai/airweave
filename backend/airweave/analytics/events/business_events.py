"""High-level business metrics tracking."""

from typing import Any, Dict, Optional
from uuid import UUID

from airweave.analytics.service import analytics


class BusinessEventTracker:
    """Tracks high-level business metrics and organizational events."""

    @staticmethod
    def track_organization_created(
        organization_id: UUID, user_id: UUID, properties: Optional[Dict[str, Any]] = None
    ):
        """Track when a new organization is created.

        Args:
        ----
            organization_id: ID of the created organization
            user_id: ID of the user who created it
            properties: Additional properties
        """
        event_properties = {
            **(properties or {}),
            "organization_id": str(organization_id),  # Ensure this can't be overridden
        }

        analytics.track_event(
            event_name="organization_created",
            distinct_id=str(user_id),
            properties=event_properties,
            groups={"organization": str(organization_id)},
        )

    @staticmethod
    def track_collection_created(ctx, collection_id: UUID, collection_name: str):
        """Track when a new collection is created.

        Args:
        ----
            ctx: API context containing user and organization info
            collection_id: ID of the created collection
            collection_name: Name of the collection
        """
        properties = {
            "collection_id": str(collection_id),
            "collection_name": collection_name,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="collection_created",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_source_connection_created(ctx, connection_id: UUID, source_short_name: str):
        """Track when a new source connection is created.

        Args:
        ----
            ctx: API context containing user and organization info
            connection_id: ID of the created connection
            source_short_name: Short name of the source (e.g., 'slack', 'notion')
        """
        properties = {
            "connection_id": str(connection_id),
            "source_type": source_short_name,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="source_connection_created",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_first_sync_completed(ctx, sync_id: UUID, entities_processed: int):
        """Track when an organization completes their first sync.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_id: ID of the sync operation
            entities_processed: Number of entities processed
        """
        properties = {
            "sync_id": str(sync_id),
            "entities_processed": entities_processed,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="first_sync_completed",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_started(ctx, sync_id: UUID, source_type: str, collection_id: UUID):
        """Track when a sync operation starts.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_id: ID of the sync operation
            source_type: Type of source being synced
            collection_id: ID of the collection being synced
        """
        properties = {
            "sync_id": str(sync_id),
            "source_type": source_type,
            "collection_id": str(collection_id),
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="sync_started",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_completed(
        ctx,
        sync_id: UUID,
        entities_processed: int,
        entities_synced: int,
        stats,
        duration_ms: int,
    ):
        """Track when a sync operation completes successfully.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_id: ID of the sync operation
            entities_processed: Total operations (includes kept/skipped)
            entities_synced: Actual entities synced (inserted + updated) - for billing
            stats: Full sync statistics breakdown (SyncProgressUpdate)
            duration_ms: Duration of sync in milliseconds
        """
        properties = {
            "sync_id": str(sync_id),
            # Operational metrics
            "entities_processed": entities_processed,
            # Billing metrics (NEW - use this for billing dashboards)
            "entities_synced": entities_synced,
            # Detailed breakdown (NEW)
            "entities_inserted": stats.inserted if stats else 0,
            "entities_updated": stats.updated if stats else 0,
            "entities_deleted": stats.deleted if stats else 0,
            "entities_kept": stats.kept if stats else 0,
            "entities_skipped": stats.skipped if stats else 0,
            # Other
            "duration_ms": duration_ms,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="sync_completed",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_failed(ctx, sync_id: UUID, error: str, duration_ms: int):
        """Track when a sync operation fails.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_id: ID of the sync operation
            error: Error message
            duration_ms: Duration before failure in milliseconds
        """
        properties = {
            "sync_id": str(sync_id),
            "error": error,
            "duration_ms": duration_ms,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="sync_failed",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_cancelled(
        ctx, source_short_name: str, source_connection_id: UUID, duration_ms: int
    ):
        """Track when a sync operation is cancelled.

        Args:
        ----
            ctx: API context containing user and organization info
            source_short_name: Short name of the source (e.g., 'slack', 'notion')
            source_connection_id: ID of the source connection
            duration_ms: Duration before cancellation in milliseconds
        """
        properties = {
            "source_short_name": source_short_name,
            "source_connection_id": str(source_connection_id),
            "organization_name": getattr(ctx.organization, "name", "unknown"),
            "duration_ms": duration_ms,
        }

        analytics.track_event(
            event_name="sync_cancelled",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )


# Global instance
business_events = BusinessEventTracker()
