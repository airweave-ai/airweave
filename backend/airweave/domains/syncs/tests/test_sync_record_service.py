"""Table-driven tests for SyncRecordService.

Covers trigger_sync_run (happy, active-job, not-found).
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID
from airweave.domains.syncs.sync_record_service import SyncRecordService

ORG_ID = uuid4()
SYNC_ID = uuid4()


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = ORG_ID
    ctx.logger = MagicMock()
    ctx.has_feature = MagicMock(return_value=False)
    return ctx


def _mock_sync_model(sync_id: UUID = SYNC_ID, status: str = "active") -> MagicMock:
    sync = MagicMock()
    sync.id = sync_id
    sync.name = "test-sync"
    sync.status = status
    return sync


def _mock_sync_job_model(sync_id: UUID = SYNC_ID, status: str = "PENDING") -> MagicMock:
    job = MagicMock()
    job.id = uuid4()
    job.sync_id = sync_id
    job.status = status
    job.organization_id = ORG_ID
    return job


# ---------------------------------------------------------------------------
# trigger_sync_run
# ---------------------------------------------------------------------------


@dataclass
class TriggerCase:
    """Parameters for a single trigger_sync_run scenario."""

    name: str
    active_jobs: list
    sync_exists: bool = True
    sync_status: str = "active"
    expect_error: Optional[type] = None
    error_status: Optional[int] = None


TRIGGER_CASES = [
    TriggerCase(
        name="happy_path",
        active_jobs=[],
        sync_exists=True,
    ),
    TriggerCase(
        name="active_job_blocks",
        active_jobs=[_mock_sync_job_model(status="running")],
        expect_error=HTTPException,
        error_status=400,
    ),
    TriggerCase(
        name="sync_not_found",
        active_jobs=[],
        sync_exists=False,
        expect_error=ValueError,
    ),
    TriggerCase(
        name="non_active_sync_rejected",
        active_jobs=[],
        sync_exists=True,
        sync_status="paused",
        expect_error=HTTPException,
        error_status=409,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TRIGGER_CASES, ids=lambda c: c.name)
async def test_trigger_sync_run(case: TriggerCase) -> None:
    """Verify trigger_sync_run behaviour for each scenario."""
    sync_repo = AsyncMock()
    sync_job_repo = AsyncMock()
    connection_repo = AsyncMock()

    sync_job_repo.get_active_for_sync = AsyncMock(return_value=case.active_jobs)
    sync_repo.get = AsyncMock(
        return_value=_mock_sync_model(status=case.sync_status) if case.sync_exists else None
    )

    created_job = _mock_sync_job_model()
    sync_job_repo.create = AsyncMock(return_value=created_job)

    svc = SyncRecordService(
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        connection_repo=connection_repo,
    )
    db = AsyncMock()
    ctx = _mock_ctx()

    if case.expect_error:
        with pytest.raises(case.expect_error) as exc_info:
            with patch("airweave.domains.syncs.sync_record_service.UnitOfWork") as mock_uow_cls:
                mock_uow = AsyncMock()
                mock_uow.session = AsyncMock()
                mock_uow.commit = AsyncMock()
                mock_uow.session.refresh = AsyncMock()
                mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
                mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await svc.trigger_sync_run(db, SYNC_ID, ctx)
        if case.error_status and isinstance(exc_info.value, HTTPException):
            assert exc_info.value.status_code == case.error_status
    else:
        with patch("airweave.domains.syncs.sync_record_service.UnitOfWork") as mock_uow_cls:
            mock_uow = AsyncMock()
            mock_uow.session = AsyncMock()
            mock_uow.commit = AsyncMock()
            mock_uow.session.refresh = AsyncMock()
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("airweave.domains.syncs.sync_record_service.schemas") as mock_schemas:
                mock_sync_schema = MagicMock()
                mock_job_schema = MagicMock()
                mock_schemas.Sync.model_validate.return_value = mock_sync_schema
                mock_schemas.SyncJob.model_validate.return_value = mock_job_schema
                mock_schemas.SyncJobCreate = MagicMock()

                result = await svc.trigger_sync_run(db, SYNC_ID, ctx)
                assert result == (mock_sync_schema, mock_job_schema)

                sync_job_repo.create.assert_called_once()
                mock_uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# resolve_destination_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sync_flushes_and_refreshes_job_before_validation() -> None:
    """Verify create_sync flushes twice and refreshes the job before validation."""
    sync_repo = AsyncMock()
    sync_job_repo = AsyncMock()
    connection_repo = AsyncMock()
    svc = SyncRecordService(
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        connection_repo=connection_repo,
    )

    sync_schema = MagicMock(id=SYNC_ID)
    sync_repo.create = AsyncMock(return_value=sync_schema)
    created_job = MagicMock()
    sync_job_repo.create = AsyncMock(return_value=created_job)

    uow = MagicMock()
    uow.session = AsyncMock()
    uow.session.flush = AsyncMock()
    uow.session.refresh = AsyncMock()
    ctx = _mock_ctx()

    with patch("airweave.domains.syncs.sync_record_service.schemas") as mock_schemas:
        validated_job_schema = MagicMock()
        mock_schemas.SyncJob.model_validate.return_value = validated_job_schema
        mock_schemas.SyncJobCreate = MagicMock()

        sync, sync_job = await svc.create_sync(
            AsyncMock(),
            name="Test Sync",
            source_connection_id=uuid4(),
            destination_connection_ids=[NATIVE_VESPA_UUID],
            cron_schedule=None,
            run_immediately=True,
            ctx=ctx,
            uow=uow,
        )

        assert sync is sync_schema
        assert sync_job is validated_job_schema
        assert uow.session.flush.await_count == 2
        uow.session.refresh.assert_awaited_once_with(created_job)


@pytest.mark.asyncio
async def test_create_sync_flushes_sync_even_without_immediate_job() -> None:
    """Verify create_sync flushes once and skips job when run_immediately=False."""
    sync_repo = AsyncMock()
    sync_job_repo = AsyncMock()
    connection_repo = AsyncMock()
    svc = SyncRecordService(
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        connection_repo=connection_repo,
    )

    sync_schema = MagicMock(id=SYNC_ID)
    sync_repo.create = AsyncMock(return_value=sync_schema)

    uow = MagicMock()
    uow.session = AsyncMock()
    uow.session.flush = AsyncMock()
    uow.session.refresh = AsyncMock()
    ctx = _mock_ctx()

    sync, sync_job = await svc.create_sync(
        AsyncMock(),
        name="Test Sync",
        source_connection_id=uuid4(),
        destination_connection_ids=[NATIVE_VESPA_UUID],
        cron_schedule="0 * * * *",
        run_immediately=False,
        ctx=ctx,
        uow=uow,
    )

    assert sync is sync_schema
    assert sync_job is None
    uow.session.flush.assert_awaited_once()
    uow.session.refresh.assert_not_awaited()
    sync_job_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_destination_ids_returns_native_only() -> None:
    """Verify resolve_destination_ids returns only native Vespa UUID."""
    svc = SyncRecordService(
        sync_repo=AsyncMock(),
        sync_job_repo=AsyncMock(),
        connection_repo=AsyncMock(),
    )
    db = AsyncMock()
    ctx = _mock_ctx()

    destination_ids = await svc.resolve_destination_ids(db, ctx)

    assert destination_ids == [NATIVE_VESPA_UUID]
