"""High-level business metrics tracking."""

from typing import List, Optional
from uuid import UUID

from airweave.analytics.service import analytics
from airweave.core.context import BaseContext


class BusinessEventTracker:
    """Tracks high-level business metrics and organizational events."""

    # =========================================================================
    # Webhook Events - Track user behavior around webhook feature usage
    # =========================================================================

    @staticmethod
    def track_webhook_subscription_created(
        ctx: BaseContext, endpoint_id: str, url: str, event_types: List[str]
    ):
        """Track when a user creates a webhook subscription.

        Args:
        ----
            ctx: API context containing user and organization info
            endpoint_id: ID of the created webhook endpoint
            url: The webhook URL (domain only for privacy)
            event_types: List of event types subscribed to
        """
        # Extract domain from URL for privacy
        try:
            from urllib.parse import urlparse

            domain = urlparse(url).netloc
        except Exception:
            domain = "unknown"

        properties = {
            "endpoint_id": endpoint_id,
            "webhook_domain": domain,
            "event_types": event_types,
            "event_types_count": len(event_types),
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="webhook_subscription_created",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_webhook_subscription_updated(
        ctx: BaseContext,
        endpoint_id: str,
        url_changed: bool,
        event_types_changed: bool,
        new_event_types: Optional[List[str]] = None,
    ):
        """Track when a user updates a webhook subscription.

        Args:
        ----
            ctx: API context containing user and organization info
            endpoint_id: ID of the updated webhook endpoint
            url_changed: Whether the URL was changed
            event_types_changed: Whether event types were changed
            new_event_types: New list of event types if changed
        """
        properties = {
            "endpoint_id": endpoint_id,
            "url_changed": url_changed,
            "event_types_changed": event_types_changed,
            "organization_name": ctx.organization.name,
        }

        if new_event_types is not None:
            properties["new_event_types"] = new_event_types
            properties["new_event_types_count"] = len(new_event_types)

        analytics.track_event(
            event_name="webhook_subscription_updated",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_webhook_subscription_deleted(ctx: BaseContext, endpoint_id: str):
        """Track when a user deletes a webhook subscription.

        Args:
        ----
            ctx: API context containing user and organization info
            endpoint_id: ID of the deleted webhook endpoint
        """
        properties = {
            "endpoint_id": endpoint_id,
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="webhook_subscription_deleted",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_webhook_secret_viewed(ctx: BaseContext, endpoint_id: str):
        """Track when a user views their webhook signing secret.

        This is useful for security auditing - knowing when secrets are accessed.

        Args:
        ----
            ctx: API context containing user and organization info
            endpoint_id: ID of the webhook endpoint whose secret was viewed
        """
        properties = {
            "endpoint_id": endpoint_id,
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="webhook_secret_viewed",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    # =========================================================================
    # Source Connection Events
    # =========================================================================

    @staticmethod
    def track_source_connection_created(
        ctx: BaseContext, connection_id: UUID, source_short_name: str
    ):
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
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="source_connection_created",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_completed(
        ctx: BaseContext,
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
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="sync_completed",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_failed(ctx: BaseContext, sync_id: UUID, error: str, duration_ms: int):
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
            "organization_name": ctx.organization.name,
        }

        analytics.track_event(
            event_name="sync_failed",
            distinct_id=str(ctx.organization.id),
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    @staticmethod
    def track_sync_cancelled(
        ctx: BaseContext, source_short_name: str, source_connection_id: UUID, duration_ms: int
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
            "organization_name": ctx.organization.name,
            "duration_ms": duration_ms,
        }

        analytics.track_event(
            event_name="sync_cancelled",
            distinct_id=str(ctx.organization.id),
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
        # Add standard organization metadata (ensure organization_id cannot be overridden)
        org_properties = {**properties, "organization_id": str(organization_id)}

        analytics.set_group_properties(
            group_type="organization", group_key=str(organization_id), properties=org_properties
        )

    @staticmethod
    def track_user_created(
        user_id: UUID, email: str, full_name: str, auth0_id: str, signup_source: str = "auth0"
    ):
        """Track when a new user is created during signup.

        Args:
        ----
            user_id: ID of the created user
            email: User's email address
            full_name: User's full name
            auth0_id: Auth0 user ID
            signup_source: Source of the signup (default: "auth0")
        """
        properties = {
            "user_id": str(user_id),
            "email": email,
            "full_name": full_name,
            "auth0_id": auth0_id,
            "signup_source": signup_source,
            "auth_method": "auth0",
        }

        analytics.track_event(
            event_name="user_created",
            distinct_id=str(user_id),
            properties=properties,
            groups=None,  # No organization context yet
        )


# Global instance
business_events = BusinessEventTracker()
