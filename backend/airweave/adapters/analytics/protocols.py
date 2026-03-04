"""Protocol for analytics tracking adapters."""

from typing import Any, Dict, Optional, Protocol


class AnalyticsTrackerProtocol(Protocol):
    """Fire-and-forget analytics tracking.

    Adapter boundary between domain event handling and the analytics
    provider (PostHog today, could be Segment/Amplitude/etc. later).
    """

    def track(
        self,
        event_name: str,
        distinct_id: str,
        properties: Optional[Dict[str, Any]] = None,
        groups: Optional[Dict[str, str]] = None,
    ) -> None:
        """Track a single analytics event.

        Implementations must be safe to call in fire-and-forget style —
        errors are logged, never raised.
        """
        ...
