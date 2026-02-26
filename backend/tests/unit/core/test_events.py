"""Unit tests for domain events.

Tests:
- BaseDomainEvent frozen immutability and serialization
- SyncLifecycleEvent (Pydantic) classmethods and serialization
- SourceConnectionLifecycleEvent classmethods and serialization
- CollectionLifecycleEvent classmethods and serialization
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from airweave.core.events.base import DomainEvent
from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.events.enums import (
    CollectionEventType,
    SourceConnectionEventType,
    SyncEventType,
)
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ORG_ID = uuid4()
SYNC_ID = uuid4()
SYNC_JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SOURCE_CONNECTION_ID = uuid4()


# ---------------------------------------------------------------------------
# BaseDomainEvent
# ---------------------------------------------------------------------------


class TestDomainEvent:
    """Tests for DomainEvent base class."""

    def test_frozen(self):
        class MyEvent(DomainEvent):
            foo: str = "bar"

        event = MyEvent(event_type=SyncEventType.PENDING, organization_id=ORG_ID)
        with pytest.raises(Exception):
            event.foo = "baz"

    def test_model_dump_json_safe(self):
        class MyEvent(DomainEvent):
            some_id: UUID
            count: int = 42

        event = MyEvent(
            event_type=SyncEventType.COMPLETED,
            organization_id=ORG_ID,
            some_id=SYNC_ID,
        )
        dumped = event.model_dump(mode="json")

        assert dumped["event_type"] == "sync.completed"
        assert dumped["organization_id"] == str(ORG_ID)
        assert dumped["some_id"] == str(SYNC_ID)
        assert dumped["count"] == 42
        # Must be JSON-serializable
        json.dumps(dumped)

    def test_timestamp_auto_generated(self):
        class MyEvent(DomainEvent):
            pass

        event = MyEvent(event_type=CollectionEventType.CREATED, organization_id=ORG_ID)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_rejects_arbitrary_string(self):
        """EventType constraint rejects arbitrary strings."""
        with pytest.raises(Exception):
            DomainEvent(event_type="banana", organization_id=ORG_ID)


# ---------------------------------------------------------------------------
# SyncLifecycleEvent
# ---------------------------------------------------------------------------


class TestSyncLifecycleEvent:
    """Tests for SyncLifecycleEvent (migrated from frozen dataclass to Pydantic)."""

    def _make_completed(self, **overrides):
        defaults = dict(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_name="My Collection",
            collection_readable_id="my-collection-abc12",
            entities_inserted=10,
            entities_updated=5,
        )
        defaults.update(overrides)
        return SyncLifecycleEvent.completed(**defaults)

    def test_classmethod_pending(self):
        event = SyncLifecycleEvent.pending(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="notion",
            collection_name="Notes",
            collection_readable_id="notes-xyz",
        )
        assert event.event_type == SyncEventType.PENDING
        assert event.organization_id == ORG_ID
        assert event.sync_id == SYNC_ID

    def test_classmethod_running(self):
        event = SyncLifecycleEvent.running(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_name="Slack Messages",
            collection_readable_id="slack-abc",
        )
        assert event.event_type == SyncEventType.RUNNING

    def test_classmethod_completed_with_metrics(self):
        event = self._make_completed()
        assert event.event_type == SyncEventType.COMPLETED
        assert event.entities_inserted == 10
        assert event.entities_updated == 5

    def test_classmethod_failed(self):
        event = SyncLifecycleEvent.failed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="hubspot",
            collection_name="CRM",
            collection_readable_id="crm-123",
            error="Auth failed",
        )
        assert event.event_type == SyncEventType.FAILED
        assert event.error == "Auth failed"

    def test_classmethod_cancelled(self):
        event = SyncLifecycleEvent.cancelled(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=SYNC_JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="notion",
            collection_name="Docs",
            collection_readable_id="docs-456",
        )
        assert event.event_type == SyncEventType.CANCELLED

    def test_frozen(self):
        event = self._make_completed()
        with pytest.raises(Exception):
            event.sync_id = uuid4()

    def test_model_dump_contains_all_fields(self):
        event = self._make_completed(entities_inserted=42, entities_deleted=3)
        dumped = event.model_dump(mode="json")
        assert dumped["event_type"] == "sync.completed"
        assert dumped["organization_id"] == str(ORG_ID)
        assert dumped["sync_id"] == str(SYNC_ID)
        assert dumped["sync_job_id"] == str(SYNC_JOB_ID)
        assert dumped["source_type"] == "slack"
        assert dumped["entities_inserted"] == 42
        assert dumped["entities_deleted"] == 3

    def test_model_dump_is_json_serializable(self):
        event = self._make_completed()
        json.dumps(event.model_dump(mode="json"))

    def test_event_type_fnmatch(self):
        """SyncEventType is a str enum; fnmatch should work for bus matching."""
        import fnmatch

        event = self._make_completed()
        assert fnmatch.fnmatch(event.event_type, "sync.*")
        assert fnmatch.fnmatch(event.event_type, "sync.completed")
        assert not fnmatch.fnmatch(event.event_type, "collection.*")


# ---------------------------------------------------------------------------
# SourceConnectionLifecycleEvent
# ---------------------------------------------------------------------------


class TestSourceConnectionLifecycleEvent:
    """Tests for SourceConnectionLifecycleEvent."""

    def test_created(self):
        event = SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_readable_id="slack-abc",
            is_authenticated=False,
        )
        assert event.event_type == SourceConnectionEventType.CREATED
        assert event.is_authenticated is False

    def test_auth_completed(self):
        event = SourceConnectionLifecycleEvent.auth_completed(
            organization_id=ORG_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_readable_id="slack-abc",
        )
        assert event.event_type == SourceConnectionEventType.AUTH_COMPLETED
        assert event.is_authenticated is True

    def test_deleted(self):
        event = SourceConnectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="notion",
            collection_readable_id="notion-xyz",
        )
        assert event.event_type == SourceConnectionEventType.DELETED

    def test_model_dump(self):
        event = SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SOURCE_CONNECTION_ID,
            source_type="slack",
            collection_readable_id="slack-abc",
        )
        dumped = event.model_dump(mode="json")
        assert dumped["event_type"] == "source_connection.created"
        assert dumped["source_connection_id"] == str(SOURCE_CONNECTION_ID)
        assert dumped["source_type"] == "slack"


# ---------------------------------------------------------------------------
# CollectionLifecycleEvent
# ---------------------------------------------------------------------------


class TestCollectionLifecycleEvent:
    """Tests for CollectionLifecycleEvent."""

    def test_created(self):
        event = CollectionLifecycleEvent.created(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="My Collection",
            collection_readable_id="my-col-123",
        )
        assert event.event_type == CollectionEventType.CREATED

    def test_updated(self):
        event = CollectionLifecycleEvent.updated(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="Renamed",
            collection_readable_id="my-col-123",
        )
        assert event.event_type == CollectionEventType.UPDATED

    def test_deleted(self):
        event = CollectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="Deleted",
            collection_readable_id="my-col-123",
        )
        assert event.event_type == CollectionEventType.DELETED

    def test_model_dump(self):
        event = CollectionLifecycleEvent.created(
            organization_id=ORG_ID,
            collection_id=COLLECTION_ID,
            collection_name="Finance Data",
            collection_readable_id="finance-abc",
        )
        dumped = event.model_dump(mode="json")
        assert dumped["event_type"] == "collection.created"
        assert dumped["collection_id"] == str(COLLECTION_ID)
        assert dumped["collection_name"] == "Finance Data"
