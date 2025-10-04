"""High-level business metrics tracking."""

from uuid import UUID

from airweave.analytics.service import analytics


class BusinessEventTracker:
    """Tracks high-level business metrics and organizational events."""

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
    def track_sync_completed(ctx, sync_id: UUID, entities_processed: int, duration_ms: int):
        """Track when a sync operation completes successfully.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_id: ID of the sync operation
            entities_processed: Number of entities processed
            duration_ms: Duration of sync in milliseconds
        """
        properties = {
            "sync_id": str(sync_id),
            "entities_processed": entities_processed,
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

    @staticmethod
    def set_organization_properties(organization_id: UUID, properties: dict):
        """Set properties for an organization group in PostHog.

        Args:
        ----
            organization_id: ID of the organization
            properties: Properties to set for the organization
        """
        # Add standard organization metadata
        org_properties = {"organization_id": str(organization_id), **properties}

        analytics.set_group_properties(
            group_type="organization", group_key=str(organization_id), properties=org_properties
        )

    @staticmethod
    def track_search_query(
        ctx, query: str, collection_slug: str, duration_ms: float, search_type: str = "regular"
    ):
        """Track search query execution.

        Args:
        ----
            ctx: API context containing user and organization info
            query: Search query text
            collection_slug: Collection identifier
            duration_ms: Search duration in milliseconds
            search_type: Type of search (regular/streaming)
        """
        properties = {
            "query_length": len(query),
            "collection_slug": collection_slug,
            "duration_ms": duration_ms,
            "search_type": search_type,
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        analytics.track_event(
            event_name="search_query",
            distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_entity_counts(ctx, sync_job_id: UUID, sync_id: UUID, entity_counts: dict):
        """Track detailed entity counts for sync completion.

        Args:
        ----
            ctx: API context containing user and organization info
            sync_job_id: ID of the sync job
            sync_id: ID of the sync operation
            entity_counts: Dictionary of entity type to count
        """
        for entity_type, entity_count in entity_counts.items():
            if entity_count > 0:
                properties = {
                    "sync_job_id": str(sync_job_id),
                    "sync_id": str(sync_id),
                    "entity_type": entity_type,
                    "entity_count": entity_count,
                    "organization_name": getattr(ctx.organization, "name", "unknown"),
                }

                analytics.track_event(
                    event_name="entities_synced_by_type",
                    distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
                    properties=properties,
                    groups={"organization": str(ctx.organization.id)},
                )


# Global instance
business_events = BusinessEventTracker()
