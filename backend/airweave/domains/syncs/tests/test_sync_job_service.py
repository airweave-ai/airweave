"""Table-driven tests for SyncJobService.

Covers _build_stats_update, _build_timestamp_update, and update_status
(via mocked DB context).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.sync_job_service import SyncJobService
from airweave.domains.syncs.types import StatsUpdate, TimestampUpdate
from airweave.platform.sync.pipeline.entity_tracker import SyncStats

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_svc(mock_repo=None):
    """Create a SyncJobService with a mock repo."""
    if mock_repo is None:
        mock_repo = MagicMock()
        mock_repo.get = AsyncMock(return_value=None)
        mock_repo.update = AsyncMock()
    return SyncJobService(sync_job_repo=mock_repo), mock_repo


# ---------------------------------------------------------------------------
# _build_stats_update
# ---------------------------------------------------------------------------


@dataclass
class StatsCase:
    name: str
    stats: SyncStats
    expected: StatsUpdate


STATS_CASES = [
    StatsCase(
        name="all_zeros",
        stats=SyncStats(),
        expected=StatsUpdate(),
    ),
    StatsCase(
        name="mixed_values",
        stats=SyncStats(
            inserted=5, updated=3, deleted=1, kept=10, skipped=2,
            entities_encountered={"Document": 15, "Image": 6},
        ),
        expected=StatsUpdate(
            entities_inserted=5,
            entities_updated=3,
            entities_deleted=1,
            entities_kept=10,
            entities_skipped=2,
            entities_encountered={"Document": 15, "Image": 6},
        ),
    ),
]


@pytest.mark.parametrize("case", STATS_CASES, ids=lambda c: c.name)
def test_build_stats_update(case: StatsCase):
    result = SyncJobService._build_stats_update(case.stats)
    assert result == case.expected


# ---------------------------------------------------------------------------
# _build_timestamp_update
# ---------------------------------------------------------------------------


@dataclass
class TimestampCase:
    name: str
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error: Optional[str] = None
    expected: Optional[TimestampUpdate] = None

    def __post_init__(self):
        if self.expected is None:
            self.expected = TimestampUpdate()


TIMESTAMP_CASES = [
    TimestampCase(
        name="running_with_started_at",
        status=SyncJobStatus.RUNNING,
        started_at=NOW,
        expected=TimestampUpdate(started_at=NOW),
    ),
    TimestampCase(
        name="completed_with_completed_at",
        status=SyncJobStatus.COMPLETED,
        completed_at=NOW,
        expected=TimestampUpdate(completed_at=NOW),
    ),
    TimestampCase(
        name="completed_without_completed_at",
        status=SyncJobStatus.COMPLETED,
    ),
    TimestampCase(
        name="failed_with_error",
        status=SyncJobStatus.FAILED,
        failed_at=NOW,
        error="Connection refused",
        expected=TimestampUpdate(failed_at=NOW, error="Connection refused"),
    ),
    TimestampCase(
        name="failed_without_error",
        status=SyncJobStatus.FAILED,
        failed_at=NOW,
        expected=TimestampUpdate(failed_at=NOW),
    ),
    TimestampCase(
        name="pending_no_fields",
        status=SyncJobStatus.PENDING,
    ),
    TimestampCase(
        name="running_no_started_at",
        status=SyncJobStatus.RUNNING,
    ),
]


@pytest.mark.parametrize("case", TIMESTAMP_CASES, ids=lambda c: c.name)
def test_build_timestamp_update(case: TimestampCase):
    result = SyncJobService._build_timestamp_update(
        case.status, case.started_at, case.completed_at, case.failed_at, case.error
    )
    assert result == case.expected


# ---------------------------------------------------------------------------
# update_status (mocked DB)
# ---------------------------------------------------------------------------


@dataclass
class UpdateStatusCase:
    name: str
    status: SyncJobStatus
    job_exists: bool = True
    stats: Optional[SyncStats] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    expect_sql_execute: bool = True
    expect_orm_update: bool = False
    expect_commit: bool = True


UPDATE_STATUS_CASES = [
    UpdateStatusCase(
        name="job_not_found",
        status=SyncJobStatus.RUNNING,
        job_exists=False,
        expect_sql_execute=False,
        expect_commit=False,
    ),
    UpdateStatusCase(
        name="status_only",
        status=SyncJobStatus.RUNNING,
        expect_orm_update=False,
    ),
    UpdateStatusCase(
        name="with_stats",
        status=SyncJobStatus.RUNNING,
        stats=SyncStats(inserted=5),
        expect_orm_update=True,
    ),
    UpdateStatusCase(
        name="completed_with_timestamp",
        status=SyncJobStatus.COMPLETED,
        completed_at=NOW,
        expect_orm_update=True,
    ),
    UpdateStatusCase(
        name="failed_with_error",
        status=SyncJobStatus.FAILED,
        failed_at=NOW,
        error="Boom",
        expect_orm_update=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", UPDATE_STATUS_CASES, ids=lambda c: c.name)
async def test_update_status(case: UpdateStatusCase):
    mock_repo = MagicMock()
    mock_job = MagicMock() if case.job_exists else None
    mock_repo.get = AsyncMock(return_value=mock_job)
    mock_repo.update = AsyncMock()

    svc = SyncJobService(sync_job_repo=mock_repo)
    job_id = uuid4()

    mock_db = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.organization = MagicMock()
    mock_ctx.organization.id = uuid4()

    with patch(
        "airweave.domains.syncs.sync_job_service.get_db_context"
    ) as mock_ctx_mgr:
        mock_ctx_mgr.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx_mgr.return_value.__aexit__ = AsyncMock(return_value=False)

        await svc.update_status(
            sync_job_id=job_id,
            status=case.status,
            ctx=mock_ctx,
            stats=case.stats,
            error=case.error,
            started_at=case.started_at,
            completed_at=case.completed_at,
            failed_at=case.failed_at,
        )

        if case.expect_sql_execute:
            mock_db.execute.assert_called_once()
        else:
            mock_db.execute.assert_not_called()

        if case.expect_orm_update:
            mock_repo.update.assert_called_once()
        else:
            mock_repo.update.assert_not_called()

        if case.expect_commit:
            mock_db.commit.assert_called_once()
        else:
            mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_status_exception_swallowed():
    """update_status swallows exceptions and logs them."""
    mock_repo = MagicMock()
    svc = SyncJobService(sync_job_repo=mock_repo)

    with patch(
        "airweave.domains.syncs.sync_job_service.get_db_context",
        side_effect=RuntimeError("DB down"),
    ):
        await svc.update_status(
            sync_job_id=uuid4(),
            status=SyncJobStatus.RUNNING,
            ctx=MagicMock(),
        )
