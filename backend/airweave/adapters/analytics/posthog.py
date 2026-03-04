"""PostHog analytics tracker adapter."""

import logging
from typing import Any, Dict, Optional

import posthog

from airweave.core.config import Settings

logger = logging.getLogger(__name__)


class PostHogTracker:
    """Wraps the PostHog SDK behind AnalyticsTrackerProtocol.

    Enriches every event with deployment metadata (environment,
    deployment type, URLs) so dashboards can segment hosted vs
    self-hosted without callers needing to know.
    """

    def __init__(self, settings: Settings) -> None:
        """Configure PostHog SDK from application settings."""
        self._enabled = settings.ANALYTICS_ENABLED and settings.ENVIRONMENT != "local"
        self._environment = settings.ENVIRONMENT
        self._api_url = settings.api_url
        self._app_url = settings.app_url
        self._app_full_url = settings.APP_FULL_URL

        if self._enabled:
            posthog.api_key = settings.POSTHOG_API_KEY
            posthog.host = settings.POSTHOG_HOST
            logger.info("PostHog analytics tracker initialized (env=%s)", self._environment)
        else:
            logger.info("PostHog analytics tracker disabled (env=%s)", self._environment)

    def _deployment_type(self) -> str:
        if self._environment == "prd" and self._app_full_url is None:
            return "hosted"
        return "self_hosted"

    def _base_properties(self) -> Dict[str, Any]:
        return {
            "environment": self._environment,
            "deployment_type": self._deployment_type(),
            "is_hosted_platform": self._deployment_type() == "hosted",
            "api_url": self._api_url,
            "app_url": self._app_url,
        }

    def track(
        self,
        event_name: str,
        distinct_id: str,
        properties: Optional[Dict[str, Any]] = None,
        groups: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send event to PostHog, enriched with deployment metadata."""
        if not self._enabled:
            return

        try:
            merged = {**self._base_properties(), **(properties or {})}
            posthog.capture(
                distinct_id=distinct_id,
                event=event_name,
                properties=merged,
                groups=groups or {},
            )
        except Exception as e:
            logger.error("Failed to track analytics event '%s': %s", event_name, e)
