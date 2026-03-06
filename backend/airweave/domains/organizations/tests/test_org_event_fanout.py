"""Integration test: org events fan out through the event bus.

Wires the real InMemoryEventBus with real subscribers (WebhookEventSubscriber,
AnalyticsEventSubscriber) backed by fakes. Publishes org lifecycle events and
verifies all subscribers received them.

This catches wiring bugs — e.g. if the AnalyticsEventSubscriber EVENT_PATTERNS
doesn't include ``organization.*``, these tests fail.
"""

from uuid import uuid4

import pytest

from airweave.adapters.analytics.fake import FakeAnalyticsTracker
from airweave.adapters.analytics.subscriber import AnalyticsEventSubscriber
from airweave.adapters.event_bus.in_memory import InMemoryEventBus
from airweave.adapters.webhooks.fake import FakeWebhookPublisher
from airweave.core.events.organization import OrganizationLifecycleEvent
from airweave.domains.webhooks.subscribers import WebhookEventSubscriber

ORG_ID = uuid4()


def _build_bus():
    """Wire a real event bus with real subscribers, fake infra at the edges."""
    bus = InMemoryEventBus()

    webhook_pub = FakeWebhookPublisher()
    webhook_sub = WebhookEventSubscriber(webhook_pub)
    for pattern in webhook_sub.EVENT_PATTERNS:
        bus.subscribe(pattern, webhook_sub.handle)

    tracker = FakeAnalyticsTracker()
    analytics_sub = AnalyticsEventSubscriber(tracker)
    for pattern in analytics_sub.EVENT_PATTERNS:
        bus.subscribe(pattern, analytics_sub.handle)

    return bus, webhook_pub, tracker


class TestOrgCreatedFanout:
    @pytest.mark.asyncio
    async def test_webhooks_receive_org_created(self):
        bus, webhook_pub, _ = _build_bus()

        await bus.publish(
            OrganizationLifecycleEvent.created(
                organization_id=ORG_ID,
                organization_name="Acme",
                owner_email="boss@acme.com",
                plan="pro",
            )
        )

        assert webhook_pub.has_event("organization.created")

    @pytest.mark.asyncio
    async def test_analytics_receive_org_created(self):
        bus, _, tracker = _build_bus()

        await bus.publish(
            OrganizationLifecycleEvent.created(
                organization_id=ORG_ID,
                organization_name="Acme",
                owner_email="boss@acme.com",
            )
        )

        assert tracker.has("organization_created")
        assert tracker.has("$group_identify:organization")


class TestOrgDeletedFanout:
    @pytest.mark.asyncio
    async def test_webhooks_receive_org_deleted(self):
        bus, webhook_pub, _ = _build_bus()

        await bus.publish(
            OrganizationLifecycleEvent.deleted(
                organization_id=ORG_ID,
                organization_name="Acme",
                affected_user_emails=["a@acme.com"],
            )
        )

        assert webhook_pub.has_event("organization.deleted")

    @pytest.mark.asyncio
    async def test_analytics_receive_org_deleted(self):
        bus, _, tracker = _build_bus()

        await bus.publish(
            OrganizationLifecycleEvent.deleted(
                organization_id=ORG_ID,
                organization_name="Acme",
                affected_user_emails=["a@acme.com", "b@acme.com"],
            )
        )

        assert tracker.has("organization_deleted")
        event = tracker.get("organization_deleted")
        assert event.properties["affected_users"] == 2
