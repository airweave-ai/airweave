"""Unit tests for WebhookEventSubscriber.

Tests that the subscriber correctly forwards domain events to the
webhook publisher using the fake from the adapter layer.

Fixtures used:
- fake_webhook_publisher: from root conftest (FakeWebhookPublisher)
- subscriber: from domain conftest (WebhookEventSubscriber wired to fake)
"""

from uuid import uuid4

import pytest

from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent

ORG_ID = uuid4()
SYNC_ID = uuid4()
SYNC_JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SOURCE_CONNECTION_ID = uuid4()


class TestWebhookEventSubscriber:
    """Tests for WebhookEventSubscriber."""

    @pytest.mark.asyncio
    async def test_forwards_sync_event(self, fake_webhook_publisher, subscriber):
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
        await subscriber.handle(event)

        assert len(fake_webhook_publisher.events) == 1
        assert fake_webhook_publisher.events[0] is event

    @pytest.mark.asyncio
    async def test_forwards_source_connection_event(self, fake_webhook_publisher, subscriber):
        event = SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="notion",
            collection_readable_id="notes-xyz",
        )
        await subscriber.handle(event)

        assert fake_webhook_publisher.has_event("source_connection.created")

    @pytest.mark.asyncio
    async def test_forwards_collection_event(self, fake_webhook_publisher, subscriber):
        event = CollectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="Old Data",
            collection_readable_id="old-123",
        )
        await subscriber.handle(event)

        assert fake_webhook_publisher.has_event("collection.deleted")

    @pytest.mark.asyncio
    async def test_multiple_events(self, fake_webhook_publisher, subscriber):
        events = [
            SyncLifecycleEvent.running(
                organization_id=ORG_ID,
                sync_id=SYNC_ID,
                sync_job_id=SYNC_JOB_ID,
                collection_id=COLLECTION_ID,
                source_connection_id=SOURCE_CONNECTION_ID,
                source_type="slack",
                collection_name="Test",
                collection_readable_id="test-abc",
            ),
            SyncLifecycleEvent.completed(
                organization_id=ORG_ID,
                sync_id=SYNC_ID,
                sync_job_id=SYNC_JOB_ID,
                collection_id=COLLECTION_ID,
                source_connection_id=SOURCE_CONNECTION_ID,
                source_type="slack",
                collection_name="Test",
                collection_readable_id="test-abc",
            ),
        ]
        for event in events:
            await subscriber.handle(event)

        assert len(fake_webhook_publisher.events) == 2
        assert fake_webhook_publisher.has_event("sync.running")
        assert fake_webhook_publisher.has_event("sync.completed")
