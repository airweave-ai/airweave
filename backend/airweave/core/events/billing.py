"""Billing domain events."""

from uuid import UUID

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import BillingEventType


class BillingPeriodCreatedEvent(DomainEvent):
    """Emitted when a new billing period is created (renewal, upgrade, initial signup)."""

    event_type: BillingEventType = BillingEventType.PERIOD_CREATED
    billing_period_id: UUID
    plan: str
    status: str
    transition: str
