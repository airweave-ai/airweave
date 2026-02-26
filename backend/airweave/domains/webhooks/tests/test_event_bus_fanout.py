"""Integration test: EventBus -> WebhookEventSubscriber -> FakeWebhookPublisher.

Tests the full in-process event flow: a domain event is published to
the real InMemoryEventBus, which fans out to the WebhookEventSubscriber,
which forwards it to the FakeWebhookPublisher.

This validates the wiring that happens in container/factory.py without
needing any real infrastructure.
"""

from uuid import uuid4

import pytest

from airweave.adapters.event_bus.in_memory import InMemoryEventBus
from airweave.adapters.webhooks.fake import FakeWebhookPublisher
from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.domains.webhooks.subscribers import WebhookEventSubscriber

ORG_ID = uuid4()
SYNC_ID = uuid4()
SYNC_JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SOURCE_CONNECTION_ID = uuid4()


@pytest.fixture
def wired_bus():
    """Real InMemoryEventBus with WebhookEventSubscriber wired to a FakeWebhookPublisher.

    Mirrors the wiring in core/container/factory.py._create_event_bus().
    """
    publisher = FakeWebhookPublisher()
    bus = InMemoryEventBus()
    subscriber = WebhookEventSubscriber(publisher=publisher)

    for pattern in subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, subscriber.handle)

    return bus, publisher


class TestEventBusFanout:
    """Integration tests for event bus -> subscriber -> publisher flow."""

    @pytest.mark.asyncio
    async def test_sync_event_reaches_publisher(self, wired_bus):
        bus, publisher = wired_bus

        event = SyncLifecycleEvent.completed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_name="Test",
            collection_readable_id="test-abc",
        )
        await bus.publish(event)

        assert publisher.has_event("sync.completed")
        assert publisher.events[0] is event

    @pytest.mark.asyncio
    async def test_collection_event_reaches_publisher(self, wired_bus):
        bus, publisher = wired_bus

        event = CollectionLifecycleEvent.created(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="New Data",
            collection_readable_id="new-abc",
        )
        await bus.publish(event)

        assert publisher.has_event("collection.created")

    @pytest.mark.asyncio
    async def test_multiple_events_all_reach_publisher(self, wired_bus):
        bus, publisher = wired_bus

        events = [
            SyncLifecycleEvent.pending(
                organization_id=ORG_ID,
                sync_id=SYNC_ID,
                sync_job_id=SYNC_JOB_ID,
                collection_id=COLLECTION_ID,
                source_connection_id=SOURCE_CONNECTION_ID,
                source_type="notion",
                collection_name="Docs",
                collection_readable_id="docs-xyz",
            ),
            SyncLifecycleEvent.running(
                organization_id=ORG_ID,
                sync_id=SYNC_ID,
                sync_job_id=SYNC_JOB_ID,
                collection_id=COLLECTION_ID,
                source_connection_id=SOURCE_CONNECTION_ID,
                source_type="notion",
                collection_name="Docs",
                collection_readable_id="docs-xyz",
            ),
            SyncLifecycleEvent.completed(
                organization_id=ORG_ID,
                sync_id=SYNC_ID,
                sync_job_id=SYNC_JOB_ID,
                collection_id=COLLECTION_ID,
                source_connection_id=SOURCE_CONNECTION_ID,
                source_type="notion",
                collection_name="Docs",
                collection_readable_id="docs-xyz",
            ),
        ]

        for event in events:
            await bus.publish(event)

        assert len(publisher.events) == 3
        assert publisher.has_event("sync.pending")
        assert publisher.has_event("sync.running")
        assert publisher.has_event("sync.completed")

    @pytest.mark.asyncio
    async def test_subscriber_failure_does_not_crash_bus(self, wired_bus):
        """If one subscriber fails, the bus should not raise."""
        bus, publisher = wired_bus

        # Add a deliberately failing subscriber
        async def failing_handler(event):
            raise RuntimeError("Boom!")

        bus.subscribe("sync.*", failing_handler)

        event = SyncLifecycleEvent.completed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_name="Test",
            collection_readable_id="test-abc",
        )

        # Should not raise despite one subscriber failing
        await bus.publish(event)

        # The webhook subscriber still received the event
        assert publisher.has_event("sync.completed")
