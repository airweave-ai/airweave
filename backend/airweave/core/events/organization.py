"""Domain events for organization lifecycle.

Consumed by:
- WebhookEventSubscriber: external webhook delivery (Svix)
- AnalyticsEventSubscriber: PostHog tracking
"""

from typing import Optional
from uuid import UUID

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import OrganizationEventType


class OrganizationLifecycleEvent(DomainEvent):
    """Published when an organization is created, deleted, or membership changes."""

    event_type: OrganizationEventType

    organization_name: str = ""
    owner_email: str = ""
    affected_user_emails: list[str] = []
    plan: str = ""

    @classmethod
    def created(
        cls,
        organization_id: UUID,
        organization_name: str,
        owner_email: str,
        plan: str = "developer",
    ) -> "OrganizationLifecycleEvent":
        """Create an organization-created event."""
        return cls(
            event_type=OrganizationEventType.CREATED,
            organization_id=organization_id,
            organization_name=organization_name,
            owner_email=owner_email,
            plan=plan,
        )

    @classmethod
    def deleted(
        cls,
        organization_id: UUID,
        organization_name: str,
        affected_user_emails: Optional[list[str]] = None,
    ) -> "OrganizationLifecycleEvent":
        """Create an organization-deleted event."""
        return cls(
            event_type=OrganizationEventType.DELETED,
            organization_id=organization_id,
            organization_name=organization_name,
            affected_user_emails=affected_user_emails or [],
        )

    @classmethod
    def member_added(
        cls,
        organization_id: UUID,
        organization_name: str = "",
        affected_user_emails: Optional[list[str]] = None,
    ) -> "OrganizationLifecycleEvent":
        """Create a member-added event."""
        return cls(
            event_type=OrganizationEventType.MEMBER_ADDED,
            organization_id=organization_id,
            organization_name=organization_name,
            affected_user_emails=affected_user_emails or [],
        )

    @classmethod
    def member_removed(
        cls,
        organization_id: UUID,
        organization_name: str = "",
        affected_user_emails: Optional[list[str]] = None,
    ) -> "OrganizationLifecycleEvent":
        """Create a member-removed event."""
        return cls(
            event_type=OrganizationEventType.MEMBER_REMOVED,
            organization_id=organization_id,
            organization_name=organization_name,
            affected_user_emails=affected_user_emails or [],
        )
