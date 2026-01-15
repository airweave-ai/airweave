"""Unit tests for webhook schemas.

Tests the Pydantic schemas for webhook event payloads.
"""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from airweave.core.shared_models import SyncJobStatus
from airweave.webhooks.constants.event_types import EventType
from airweave.webhooks.schemas import SyncEventPayload


class TestSyncEventPayload:
    """Tests for SyncEventPayload schema."""

    @pytest.fixture
    def valid_payload_data(self):
        """Create valid payload data for tests."""
        return {
            "event_type": EventType.SYNC_COMPLETED,
            "job_id": uuid.uuid4(),
            "collection_readable_id": "test-collection-abc123",
            "collection_name": "Test Collection",
            "source_type": "slack",
            "status": SyncJobStatus.COMPLETED,
            "timestamp": datetime.utcnow(),
        }

    def test_sync_event_payload_minimal(self, valid_payload_data):
        """Test creating payload with minimal required fields."""
        payload = SyncEventPayload(**valid_payload_data)

        assert payload.event_type == EventType.SYNC_COMPLETED
        assert payload.collection_readable_id == "test-collection-abc123"
        assert payload.source_type == "slack"
        assert payload.status == SyncJobStatus.COMPLETED
        assert payload.error is None
        assert payload.source_connection_id is None

    def test_sync_event_payload_with_source_connection_id(self, valid_payload_data):
        """Test payload with source_connection_id."""
        source_conn_id = uuid.uuid4()
        valid_payload_data["source_connection_id"] = source_conn_id

        payload = SyncEventPayload(**valid_payload_data)

        assert payload.source_connection_id == source_conn_id

    def test_sync_event_payload_with_error(self, valid_payload_data):
        """Test payload with error message."""
        valid_payload_data["event_type"] = EventType.SYNC_FAILED
        valid_payload_data["status"] = SyncJobStatus.FAILED
        valid_payload_data["error"] = "Authentication token expired"

        payload = SyncEventPayload(**valid_payload_data)

        assert payload.error == "Authentication token expired"

    def test_sync_event_payload_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SyncEventPayload(
                event_type=EventType.SYNC_COMPLETED,
                # Missing job_id, collection_readable_id, etc.
            )

        errors = exc_info.value.errors()
        missing_fields = [e["loc"][0] for e in errors]
        assert "job_id" in missing_fields
        assert "collection_readable_id" in missing_fields

    def test_sync_event_payload_serialization(self, valid_payload_data):
        """Test JSON serialization with mode='json'."""
        payload = SyncEventPayload(**valid_payload_data)
        data = payload.model_dump(mode="json")

        # UUIDs should be serialized as strings
        assert isinstance(data["job_id"], str)
        # Enums should be serialized as their values
        assert data["event_type"] == "sync.completed"
        assert data["status"] == "completed"

    def test_sync_event_payload_all_event_types(self, valid_payload_data):
        """Test that all event types can be used."""
        for event_type in EventType:
            valid_payload_data["event_type"] = event_type
            # Map event type to matching status
            status_map = {
                EventType.SYNC_PENDING: SyncJobStatus.PENDING,
                EventType.SYNC_RUNNING: SyncJobStatus.RUNNING,
                EventType.SYNC_COMPLETED: SyncJobStatus.COMPLETED,
                EventType.SYNC_FAILED: SyncJobStatus.FAILED,
                EventType.SYNC_CANCELLED: SyncJobStatus.CANCELLED,
            }
            valid_payload_data["status"] = status_map[event_type]

            payload = SyncEventPayload(**valid_payload_data)
            assert payload.event_type == event_type

    def test_sync_event_payload_from_attributes(self, valid_payload_data):
        """Test creating payload from ORM-like object."""
        # Create a mock object with attributes
        class MockSyncEvent:
            event_type = EventType.SYNC_COMPLETED
            job_id = uuid.uuid4()
            collection_readable_id = "test-collection"
            collection_name = "Test"
            source_type = "github"
            status = SyncJobStatus.COMPLETED
            timestamp = datetime.utcnow()
            source_connection_id = None
            error = None

        mock_obj = MockSyncEvent()
        payload = SyncEventPayload.model_validate(mock_obj, from_attributes=True)

        assert payload.event_type == EventType.SYNC_COMPLETED
        assert payload.source_type == "github"

    def test_sync_event_payload_timestamp_required(self, valid_payload_data):
        """Test that timestamp is required."""
        del valid_payload_data["timestamp"]

        with pytest.raises(ValidationError) as exc_info:
            SyncEventPayload(**valid_payload_data)

        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "timestamp" for e in errors)

    def test_sync_event_payload_complete_example(self):
        """Test creating a complete payload with all fields."""
        payload = SyncEventPayload(
            event_type=EventType.SYNC_COMPLETED,
            job_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            collection_readable_id="finance-data-ab123",
            collection_name="Finance Data",
            source_connection_id=uuid.UUID("880e8400-e29b-41d4-a716-446655440003"),
            source_type="slack",
            status=SyncJobStatus.COMPLETED,
            timestamp=datetime(2024, 1, 15, 14, 22, 15),
        )

        data = payload.model_dump(mode="json")

        assert data["event_type"] == "sync.completed"
        assert data["job_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["collection_readable_id"] == "finance-data-ab123"

    def test_sync_event_payload_failed_example(self):
        """Test creating a failed sync payload."""
        payload = SyncEventPayload(
            event_type=EventType.SYNC_FAILED,
            job_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            collection_readable_id="finance-data-ab123",
            collection_name="Finance Data",
            source_type="notion",
            status=SyncJobStatus.FAILED,
            timestamp=datetime(2024, 1, 15, 14, 22, 15),
            error="Authentication token expired",
        )

        data = payload.model_dump(mode="json")

        assert data["event_type"] == "sync.failed"
        assert data["error"] == "Authentication token expired"
