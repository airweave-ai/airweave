"""Context-aware analytics service for dependency injection."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from airweave.analytics.service import AnalyticsService


class RequestHeaders(BaseModel):
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

    # Fern-specific headers
    fern_language: Optional[str] = None
    fern_runtime: Optional[str] = None
    fern_runtime_version: Optional[str] = None

    # Agent framework headers
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None

    # Request tracking
    request_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for PostHog properties, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class AnalyticsContext(BaseModel):
    """Minimal context for analytics - no circular imports!

    Contains only the specific fields needed for analytics tracking.
    """

    auth_method: str
    organization_id: str
    organization_name: str
    request_id: str
    user_id: Optional[str] = None


class ContextualAnalyticsService:
    """Context-aware analytics service that automatically includes user/org/header info."""

    def __init__(
        self,
        base_service: AnalyticsService,
        context: AnalyticsContext,
        headers: Optional[RequestHeaders] = None,
    ):
        """Initialize the contextual analytics service.

        Args:
            base_service: The base analytics service for PostHog operations
            context: Analytics context with user/org information
            headers: Request headers for enhanced tracking (optional)
        """
        self.base_service = base_service
        self.context = context
        self.headers = headers or RequestHeaders()

    def _build_base_properties(self) -> Dict[str, Any]:
        """Build base properties with context and headers."""
        properties = {
            "auth_method": self.context.auth_method,
            "organization_name": self.context.organization_name,
            "request_id": self.context.request_id,
        }

        # Add header information
        header_dict = self.headers.to_dict()
        properties.update(header_dict)

        # Add session_id as $session_id for PostHog session replay linking
        # PostHog requires the special $session_id property to link backend
        # events to session replays
        if self.headers.session_id:
            properties["$session_id"] = self.headers.session_id

        return properties

    def _get_distinct_id(self) -> str:
        """Get distinct ID for PostHog tracking."""
        if self.context.user_id:
            return self.context.user_id
        else:
            return f"api_key_{self.context.organization_id}"

    def _get_groups(self) -> Dict[str, str]:
        """Get groups for PostHog tracking."""
        return {"organization": self.context.organization_id}

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

        self.base_service.track_event(
            event_name,
            event_properties,
            distinct_id=self._get_distinct_id(),
            groups=self._get_groups(),
        )

    # Delegate other methods to base service for completeness
    def identify_user(self, properties: Optional[Dict[str, Any]] = None) -> None:
        """Identify user with enhanced context."""
        if not self.context.user_id:
            return  # Can't identify without user context

        # Build user properties without transient request_id
        user_properties = {
            "auth_method": self.context.auth_method,
            "organization_name": self.context.organization_name,
            "client_name": self.headers.client_name,
            "sdk_name": self.headers.sdk_name,
            "session_id": self.headers.session_id,
        }
        if properties:
            user_properties.update(properties)

        self.base_service.identify_user(self.context.user_id, user_properties)

    def set_group_properties(
        self, group_type: str, group_key: str, properties: Dict[str, Any]
    ) -> None:
        """Set group properties with enhanced context."""
        return self.base_service.set_group_properties(group_type, group_key, properties)
