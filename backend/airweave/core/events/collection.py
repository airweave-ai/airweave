"""Collection domain events.

These events are published during collection lifecycle transitions
and consumed by webhooks, analytics, realtime, etc.
"""

from uuid import UUID

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import CollectionEventType


class CollectionLifecycleEvent(DomainEvent):
    """Event published during collection lifecycle transitions.

    Published when a collection is:
    - CREATED: New collection created
    - UPDATED: Collection properties changed (name, config)
    - DELETED: Collection and associated data removed
    """

    event_type: CollectionEventType

    # Identifiers
    collection_id: UUID
    collection_name: str
    collection_readable_id: str

    @classmethod
    def created(
        cls,
        organization_id: UUID,
        collection_id: UUID,
        collection_name: str,
        collection_readable_id: str,
    ) -> "CollectionLifecycleEvent":
        """Create a CREATED event (new collection)."""
        return cls(
            event_type=CollectionEventType.CREATED,
            organization_id=organization_id,
            collection_id=collection_id,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )

    @classmethod
    def updated(
        cls,
        organization_id: UUID,
        collection_id: UUID,
        collection_name: str,
        collection_readable_id: str,
    ) -> "CollectionLifecycleEvent":
        """Create an UPDATED event (properties changed)."""
        return cls(
            event_type=CollectionEventType.UPDATED,
            organization_id=organization_id,
            collection_id=collection_id,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )

    @classmethod
    def deleted(
        cls,
        organization_id: UUID,
        collection_id: UUID,
        collection_name: str,
        collection_readable_id: str,
    ) -> "CollectionLifecycleEvent":
        """Create a DELETED event (collection removed)."""
        return cls(
            event_type=CollectionEventType.DELETED,
            organization_id=organization_id,
            collection_id=collection_id,
            collection_name=collection_name,
            collection_readable_id=collection_readable_id,
        )
