"""Tests for CleanupSyncDataActivity."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.domains.arf.fakes.service import FakeArfService
from airweave.domains.temporal.activities.cleanup_sync_data import (
    CleanupSyncDataActivity,
)
from airweave.domains.temporal.fakes.schedule_service import FakeTemporalScheduleService

SYNC_ID = "00000000-0000-0000-0000-000000000010"
COLLECTION_ID = "00000000-0000-0000-0000-000000000030"
ORG_ID = "00000000-0000-0000-0000-000000000001"

MODULE = "airweave.domains.temporal.activities.cleanup_sync_data"


@pytest.fixture
def schedule_service():
    return FakeTemporalScheduleService()


@pytest.fixture
def arf_service():
    return FakeArfService()


@pytest.fixture
def activity(schedule_service, arf_service):
    return CleanupSyncDataActivity(
        temporal_schedule_service=schedule_service,
        arf_service=arf_service,
    )


@pytest.mark.unit
async def test_cleanup_deletes_schedules(activity, schedule_service):
    with patch(f"{MODULE}.VespaDestination") as mock_vespa_cls:
        mock_vespa_cls.create = AsyncMock(return_value=None)
        mock_vespa_cls.create.side_effect = RuntimeError("No Vespa")

        result = await activity.run(
            sync_ids=[SYNC_ID],
            collection_id=COLLECTION_ID,
            organization_id=ORG_ID,
        )

    delete_calls = [c for c in schedule_service._calls if c[0] == "delete_schedule_handle"]
    assert len(delete_calls) == 3
    assert result["schedules_deleted"] == 3
    assert result["syncs_processed"] == 1


@pytest.mark.unit
async def test_cleanup_deletes_schedules_with_errors(activity, schedule_service):
    schedule_service.set_error(RuntimeError("schedule not found"))

    with patch(f"{MODULE}.VespaDestination") as mock_vespa_cls:
        mock_vespa_cls.create = AsyncMock(return_value=None)
        mock_vespa_cls.create.side_effect = RuntimeError("No Vespa")

        result = await activity.run(
            sync_ids=[SYNC_ID],
            collection_id=COLLECTION_ID,
            organization_id=ORG_ID,
        )

    assert result["schedules_deleted"] == 0


@pytest.mark.unit
async def test_cleanup_vespa_and_arf(activity, arf_service):
    arf_service.seed(SYNC_ID, "entity-1", {"data": "test"})

    mock_vespa = AsyncMock()
    mock_vespa.delete_by_sync_id = AsyncMock()

    with patch(f"{MODULE}.VespaDestination") as mock_vespa_cls:
        mock_vespa_cls.create = AsyncMock(return_value=mock_vespa)

        result = await activity.run(
            sync_ids=[SYNC_ID],
            collection_id=COLLECTION_ID,
            organization_id=ORG_ID,
        )

    assert result["destinations_cleaned"] == 1
    assert result["arf_deleted"] == 1


@pytest.mark.unit
async def test_cleanup_vespa_delete_error(activity):
    mock_vespa = AsyncMock()
    mock_vespa.delete_by_sync_id = AsyncMock(side_effect=RuntimeError("vespa error"))

    with patch(f"{MODULE}.VespaDestination") as mock_vespa_cls:
        mock_vespa_cls.create = AsyncMock(return_value=mock_vespa)

        result = await activity.run(
            sync_ids=[SYNC_ID],
            collection_id=COLLECTION_ID,
            organization_id=ORG_ID,
        )

    assert result["destinations_cleaned"] == 0
    assert len(result["errors"]) >= 1


@pytest.mark.unit
async def test_cleanup_arf_error(activity, arf_service):
    arf_service.set_error(RuntimeError("arf broken"))

    with patch(f"{MODULE}.VespaDestination") as mock_vespa_cls:
        mock_vespa_cls.create = AsyncMock(return_value=None)
        mock_vespa_cls.create.side_effect = RuntimeError("No Vespa")

        result = await activity.run(
            sync_ids=[SYNC_ID],
            collection_id=COLLECTION_ID,
            organization_id=ORG_ID,
        )

    assert len(result["errors"]) >= 1
