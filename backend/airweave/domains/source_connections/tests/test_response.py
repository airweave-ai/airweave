"""Unit tests for ResponseBuilder.

Tests the pure methods (build_list_item, map_sync_job) directly.
build_response has DB dependencies and is tested at the integration level.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pytest

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.domains.collections.fake import FakeCollectionRepository
from airweave.domains.connections.fake import FakeConnectionRepository
from airweave.domains.credentials.fake_repository import FakeIntegrationCredentialRepository
from airweave.domains.entity_counts.fake import FakeEntityCountRepository
from airweave.domains.source_connections.fake_repository import FakeSourceConnectionRepository
from airweave.domains.source_connections.response import ResponseBuilder
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.syncs.fake_service import FakeSyncService
from airweave.schemas.source_connection import AuthenticationMethod

NOW = datetime.now(timezone.utc)


def _make_builder() -> ResponseBuilder:
    """Build a ResponseBuilder with fakes."""
    return ResponseBuilder(
        sc_repo=FakeSourceConnectionRepository(),
        connection_repo=FakeConnectionRepository(),
        credential_repo=FakeIntegrationCredentialRepository(),
        source_registry=FakeSourceRegistry(),
        entity_count_repo=FakeEntityCountRepository(),
        sync_service=FakeSyncService(),
    )


# ---------------------------------------------------------------------------
# build_list_item
# ---------------------------------------------------------------------------


@dataclass
class ListItemCase:
    desc: str
    data: dict
    expect_status: SourceConnectionStatus


LIST_ITEM_CASES = [
    ListItemCase(
        desc="authenticated active connection",
        data={
            "id": uuid4(),
            "name": "Stripe",
            "short_name": "stripe",
            "readable_collection_id": "col-123",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": True,
            "last_job": {"status": SyncJobStatus.COMPLETED, "completed_at": None},
            "entity_count": 42,
        },
        expect_status=SourceConnectionStatus.ACTIVE,
    ),
    ListItemCase(
        desc="unauthenticated connection is pending_auth",
        data={
            "id": uuid4(),
            "name": "Slack",
            "short_name": "slack",
            "readable_collection_id": "col-123",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": False,
            "is_active": True,
            "last_job": None,
            "entity_count": 0,
        },
        expect_status=SourceConnectionStatus.PENDING_AUTH,
    ),
    ListItemCase(
        desc="running job shows syncing",
        data={
            "id": uuid4(),
            "name": "GitHub",
            "short_name": "github",
            "readable_collection_id": "col-456",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": True,
            "last_job": {"status": SyncJobStatus.RUNNING, "completed_at": None},
            "entity_count": 10,
        },
        expect_status=SourceConnectionStatus.SYNCING,
    ),
    ListItemCase(
        desc="cancelling job shows syncing",
        data={
            "id": uuid4(),
            "name": "Notion",
            "short_name": "notion",
            "readable_collection_id": "col-789",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": True,
            "last_job": {"status": SyncJobStatus.CANCELLING, "completed_at": None},
            "entity_count": 0,
        },
        expect_status=SourceConnectionStatus.SYNCING,
    ),
    ListItemCase(
        desc="failed job shows error",
        data={
            "id": uuid4(),
            "name": "Notion",
            "short_name": "notion",
            "readable_collection_id": "col-789",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": True,
            "last_job": {"status": SyncJobStatus.FAILED, "completed_at": None},
            "entity_count": 0,
        },
        expect_status=SourceConnectionStatus.ERROR,
    ),
    ListItemCase(
        desc="inactive shows inactive",
        data={
            "id": uuid4(),
            "name": "Disabled",
            "short_name": "disabled",
            "readable_collection_id": "col-dis",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": False,
            "last_job": None,
            "entity_count": 0,
        },
        expect_status=SourceConnectionStatus.INACTIVE,
    ),
    ListItemCase(
        desc="no last job shows active",
        data={
            "id": uuid4(),
            "name": "Todoist",
            "short_name": "todoist",
            "readable_collection_id": "col-abc",
            "created_at": NOW,
            "modified_at": NOW,
            "is_authenticated": True,
            "is_active": True,
            "last_job": None,
            "entity_count": 0,
        },
        expect_status=SourceConnectionStatus.ACTIVE,
    ),
]


@pytest.mark.parametrize("case", LIST_ITEM_CASES, ids=lambda c: c.desc)
def test_build_list_item(case: ListItemCase):
    builder = _make_builder()
    item = builder.build_list_item(case.data)
    assert item.status == case.expect_status
    assert item.short_name == case.data["short_name"]
    assert item.entity_count == case.data["entity_count"]


def test_build_list_item_preserves_all_fields():
    """All fields from the stats dict are mapped correctly."""
    data = {
        "id": uuid4(),
        "name": "Full Test",
        "short_name": "full",
        "readable_collection_id": "col-full",
        "created_at": NOW,
        "modified_at": NOW,
        "is_authenticated": True,
        "is_active": True,
        "authentication_method": "direct",
        "last_job": {"status": SyncJobStatus.COMPLETED, "completed_at": NOW},
        "entity_count": 99,
    }
    builder = _make_builder()
    item = builder.build_list_item(data)
    assert item.id == data["id"]
    assert item.name == "Full Test"
    assert item.readable_collection_id == "col-full"
    assert item.created_at == NOW
    assert item.entity_count == 99
    assert item.status == SourceConnectionStatus.ACTIVE
    assert item.auth_method == AuthenticationMethod.DIRECT


# ---------------------------------------------------------------------------
# map_sync_job
# ---------------------------------------------------------------------------


@dataclass
class MapJobCase:
    desc: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    expect_duration: Optional[float]


now = datetime.now(timezone.utc)
MAP_JOB_CASES = [
    MapJobCase(
        desc="completed job has duration",
        started_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2024, 1, 1, 0, 0, 30, tzinfo=timezone.utc),
        expect_duration=30.0,
    ),
    MapJobCase(
        desc="running job has no duration",
        started_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        completed_at=None,
        expect_duration=None,
    ),
    MapJobCase(
        desc="pending job has no duration",
        started_at=None,
        completed_at=None,
        expect_duration=None,
    ),
]


@pytest.mark.parametrize("case", MAP_JOB_CASES, ids=lambda c: c.desc)
def test_map_sync_job(case: MapJobCase):
    sc_id = uuid4()
    job = type("FakeJob", (), {
        "id": uuid4(),
        "status": SyncJobStatus.COMPLETED,
        "started_at": case.started_at,
        "completed_at": case.completed_at,
        "entities_inserted": 10,
        "entities_updated": 5,
        "entities_deleted": 2,
        "entities_failed": 1,
        "error": None,
    })()

    builder = _make_builder()
    result = builder.map_sync_job(job, sc_id)

    assert result.source_connection_id == sc_id
    assert result.duration_seconds == case.expect_duration
    assert result.entities_inserted == 10
    assert result.entities_updated == 5
