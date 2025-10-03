"""Context-aware analytics service for dependency injection."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from airweave.analytics.service import AnalyticsService
from airweave.api.context import ApiContext


@dataclass
class RequestHeaders:
    """Structured representation of tracking-relevant headers.

    Easily extensible - just add new fields here when introducing new headers.
    """

    # Standard headers
    user_agent: Optional[str] = None

    # Client/Frontend headers
    client_name: Optional[str] = None
    client_version: Optional[str] = None
    session_id: Optional[str] = None

    # SDK headers
    sdk_name: Optional[str] = None
    sdk_version: Optional[str] = None

    # Agent framework headers (langchain, pydantic-ai, vercel, etc.)
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None

    # Request tracking
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for PostHog properties, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class ContextualAnalyticsService:
    """Context-aware analytics service that automatically includes user/org/header info."""

    def __init__(
        self,
        base_service: AnalyticsService,
        context: ApiContext,
        headers: Optional[RequestHeaders] = None,
    ):
        self.base_service = base_service
        self.context = context
        self.headers = headers or RequestHeaders()

    def _build_base_properties(self) -> Dict[str, Any]:
        """Build base properties with context and headers."""
        properties = {
            "auth_method": self.context.auth_method,
            "organization_name": self.context.organization.name,
            "request_id": self.context.request_id,
        }

        # Add header information
        properties.update(self.headers.to_dict())

        return properties

    def _get_distinct_id(self) -> str:
        """Get distinct ID for PostHog tracking."""
        if self.context.user:
            return str(self.context.user.id)
        else:
            return f"api_key_{self.context.organization.id}"

    def _get_groups(self) -> Dict[str, str]:
        """Get groups for PostHog tracking."""
        return {"organization": str(self.context.organization.id)}

    def track_event(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an event with automatic context and header injection."""
        # Merge properties
        event_properties = self._build_base_properties()
        if properties:
            event_properties.update(properties)

        # Delegate to base service
        self.base_service.track_event(
            event_name=event_name,
            distinct_id=self._get_distinct_id(),
            properties=event_properties,
            groups=self._get_groups(),
        )

    def track_api_call(
        self,
        endpoint: str,
        duration_ms: Optional[float] = None,
        status_code: int = 200,
        error: Optional[str] = None,
    ) -> None:
        """Track an API call with standardized properties."""
        properties = {
            "endpoint": endpoint,
            "status_code": status_code,
        }

        if duration_ms is not None:
            properties["duration_ms"] = duration_ms

        if error:
            properties["error"] = error

        event_suffix = "_error" if error else ""
        self.track_event(f"api_call{event_suffix}", properties)

    def track_search_query(
        self,
        query: str,
        collection_slug: str,
        duration_ms: float,
        search_type: str = "regular",
        results_count: Optional[int] = None,
        status: str = "success",
    ) -> None:
        """Track a search query with standardized properties."""
        properties = {
            "query_length": len(query),
            "collection_slug": collection_slug,
            "duration_ms": duration_ms,
            "search_type": search_type,
            "status": status,
        }

        if results_count is not None:
            properties["results_count"] = results_count

        self.track_event("search_query", properties)

    # Delegate other methods to base service for completeness
    def identify_user(self, properties: Optional[Dict[str, Any]] = None) -> None:
        """Identify user with enhanced context."""
        if not self.context.user:
            return  # Can't identify without user context

        user_properties = self._build_base_properties()
        if properties:
            user_properties.update(properties)

        self.base_service.identify_user(str(self.context.user.id), user_properties)

    def set_group_properties(
        self, group_type: str, group_key: str, properties: Dict[str, Any]
    ) -> None:
        """Set group properties with enhanced context."""
        return self.base_service.set_group_properties(group_type, group_key, properties)
