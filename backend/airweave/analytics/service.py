"""Core PostHog analytics service for Airweave."""

from typing import Any, Dict, Optional

import posthog

from airweave.core.config import settings
from airweave.core.logging import logger


class AnalyticsService:
    """Centralized analytics service for PostHog integration.

    Handles all PostHog interactions and provides a clean interface
    for tracking events throughout the Airweave application.
    """

    def __init__(self):
        """Initialize the analytics service with PostHog configuration."""
        # Enable analytics by default unless in local environment
        self.enabled = settings.ANALYTICS_ENABLED and settings.ENVIRONMENT != "local"
        self.logger = logger.with_context(component="analytics")

        if self.enabled:
            posthog.api_key = settings.POSTHOG_API_KEY
            posthog.host = settings.POSTHOG_HOST
            self.logger.info(f"PostHog analytics initialized (environment: {settings.ENVIRONMENT})")
        else:
            self.logger.info(
                f"PostHog analytics disabled (environment: {settings.ENVIRONMENT}, "
                f"enabled: {settings.ANALYTICS_ENABLED})"
            )

    def _get_deployment_type(self) -> str:
        """Determine if this is hosted platform or self-hosted deployment.

        Returns:
            str: "hosted" for app.airweave.ai, "self_hosted" for other deployments
        """
        if settings.ENVIRONMENT == "prd" and settings.APP_FULL_URL is None:
            return "hosted"  # Production Airweave hosted platform
        return "self_hosted"  # All other deployments (local, dev, test, custom)

    def _get_deployment_identifier(self) -> str:
        """Get a unique identifier for this deployment.

        Returns:
            str: Unique identifier for the deployment
        """
        if settings.ENVIRONMENT == "prd" and settings.APP_FULL_URL is None:
            return "airweave-hosted"  # Official hosted platform
        elif settings.API_FULL_URL:
            return f"custom-{settings.API_FULL_URL}"  # Custom deployment
        else:
            return f"{settings.ENVIRONMENT}-{settings.API_FULL_URL or 'default'}"

    def identify_user(self, user_id: str, properties: Dict[str, Any]) -> None:
        """Identify a user with properties.

        Args:
        ----
            user_id: Unique identifier for the user
            properties: User properties to set
        """
        if not self.enabled:
            return

        try:
            # Create a copy to avoid mutating the caller's properties dict
            user_properties = dict(properties) if properties else {}
            user_properties.update(
                {
                    "environment": settings.ENVIRONMENT,
                    "deployment_type": self._get_deployment_type(),
                    "deployment_id": self._get_deployment_identifier(),
                    "is_hosted_platform": self._get_deployment_type() == "hosted",
                    "api_url": settings.api_url,
                    "app_url": settings.app_url,
                }
            )

            posthog.capture(
                distinct_id=user_id, event="$identify", properties={"$set": user_properties}
            )
            self.logger.debug(f"User identified: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to identify user {user_id}: {e}")

    def track_event(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        *,
        ctx: Optional[Any] = None,
        distinct_id: Optional[str] = None,
        groups: Optional[Dict[str, str]] = None,
    ) -> None:
        """Track an event with optional properties and groups.

        When ``ctx`` (an ApiContext) is provided and carries a pre-configured
        contextual analytics service, the call is delegated to it so that
        headers, session info, distinct_id and groups are injected automatically.

        For non-API call sites, pass ``distinct_id`` and ``groups`` explicitly.

        Args:
            event_name: Name of the event to track.
            properties: Event properties.
            ctx: Optional ApiContext — if provided, its contextual analytics
                service handles distinct_id / groups / base-property enrichment.
            distinct_id: Unique identifier for the user/entity (required when
                no ctx is given).
            groups: Group associations (e.g., organization).
        """
        if not self.enabled:
            return

        # Delegate to the pre-configured ContextualAnalyticsService when available
        if ctx is not None and getattr(ctx, "analytics", None) is not None:
            ctx.analytics.track_event(event_name, properties)
            return

        if distinct_id is None:
            self.logger.warning(
                f"track_event({event_name!r}) called without distinct_id or ctx; event dropped"
            )
            return

        try:
            event_properties = dict(properties) if properties else {}
            event_properties.update(
                {
                    "environment": settings.ENVIRONMENT,
                    "deployment_type": self._get_deployment_type(),
                    "deployment_id": self._get_deployment_identifier(),
                    "is_hosted_platform": self._get_deployment_type() == "hosted",
                    "api_url": settings.api_url,
                    "app_url": settings.app_url,
                }
            )

            posthog.capture(
                distinct_id=distinct_id,
                event=event_name,
                properties=event_properties,
                groups=groups or {},
            )
            self.logger.debug(f"Event tracked: {event_name} for {distinct_id}")
        except Exception as e:
            self.logger.error(f"Failed to track event {event_name}: {e}")

    def set_group_properties(
        self, group_type: str, group_key: str, properties: Dict[str, Any]
    ) -> None:
        """Set properties for a group (e.g., organization).

        Args:
        ----
            group_type: Type of group (e.g., 'organization')
            group_key: Unique identifier for the group
            properties: Properties to set for the group
        """
        if not self.enabled:
            return

        try:
            # Create a copy to avoid mutating the caller's properties dict
            group_properties = dict(properties) if properties else {}
            group_properties.update(
                {
                    "environment": settings.ENVIRONMENT,
                    "deployment_type": self._get_deployment_type(),
                    "deployment_id": self._get_deployment_identifier(),
                    "is_hosted_platform": self._get_deployment_type() == "hosted",
                    "api_url": settings.api_url,
                    "app_url": settings.app_url,
                }
            )

            posthog.capture(
                distinct_id=group_key,
                event="$groupidentify",
                properties={
                    "$group_type": group_type,
                    "$group_key": group_key,
                    "$group_set": group_properties,
                },
            )
            self.logger.debug(f"Group properties set: {group_type}:{group_key}")
        except Exception as e:
            self.logger.error(f"Failed to set group properties for {group_type}:{group_key}: {e}")


# Global analytics service instance
analytics = AnalyticsService()
