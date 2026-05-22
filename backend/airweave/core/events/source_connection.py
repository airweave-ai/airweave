"""Source connection domain events.

These events are published during source connection lifecycle transitions
and consumed by webhooks, analytics, realtime, etc.
"""

from typing import Optional
from uuid import UUID

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import SourceConnectionEventType


class SourceConnectionLifecycleEvent(DomainEvent):
    """Event published during source connection lifecycle transitions.

    Published when a source connection:
    - CREATED: Connection record created (may or may not be authenticated)
    - AUTH_COMPLETED: OAuth flow completed, connection is now authenticated
    - AUTH_INVALIDATED: Credentials were observed to be invalid at runtime
      (e.g. expired token, revoked OAuth grant). Customers typically wire
      this to a re-auth flow.
    - DELETED: Connection and associated data removed
    """

    event_type: SourceConnectionEventType

    # Identifiers
    source_connection_id: UUID
    collection_readable_id: str

    # Context
    source_type: str = ""  # short_name, e.g. "slack", "notion"
    is_authenticated: bool = False

    # AUTH_INVALIDATED-only: short machine-readable reason ("invalid_auth",
    # "token_expired", etc.). Never includes the token itself.
    error_reason: Optional[str] = None

    @classmethod
    def created(
        cls,
        organization_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_readable_id: str,
        is_authenticated: bool = False,
    ) -> "SourceConnectionLifecycleEvent":
        """Create a CREATED event (connection record created)."""
        return cls(
            event_type=SourceConnectionEventType.CREATED,
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_readable_id=collection_readable_id,
            is_authenticated=is_authenticated,
        )

    @classmethod
    def auth_completed(
        cls,
        organization_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_readable_id: str,
    ) -> "SourceConnectionLifecycleEvent":
        """Create an AUTH_COMPLETED event (OAuth flow finished)."""
        return cls(
            event_type=SourceConnectionEventType.AUTH_COMPLETED,
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_readable_id=collection_readable_id,
            is_authenticated=True,
        )

    @classmethod
    def auth_invalidated(
        cls,
        organization_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_readable_id: str,
        error_reason: Optional[str] = None,
    ) -> "SourceConnectionLifecycleEvent":
        """Create an AUTH_INVALIDATED event (credentials observed to be invalid).

        Emitted when a runtime auth failure is detected (e.g. federated search
        receives invalid_auth from Slack, or OAuth refresh returns
        invalid_grant). Customers typically subscribe to this to trigger a
        re-authentication flow.
        """
        return cls(
            event_type=SourceConnectionEventType.AUTH_INVALIDATED,
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_readable_id=collection_readable_id,
            is_authenticated=False,
            error_reason=error_reason,
        )

    @classmethod
    def deleted(
        cls,
        organization_id: UUID,
        source_connection_id: UUID,
        source_type: str,
        collection_readable_id: str,
    ) -> "SourceConnectionLifecycleEvent":
        """Create a DELETED event (connection removed)."""
        return cls(
            event_type=SourceConnectionEventType.DELETED,
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            source_type=source_type,
            collection_readable_id=collection_readable_id,
        )
