"""Table-driven tests for SyncService.

Covers the happy path (factory → orchestrator → run) and the error path
(factory raises → job marked FAILED → re-raised).
"""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.service import SyncService


def _mock_ctx():
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.logger = MagicMock()
    ctx.logger.error = MagicMock()
    return ctx


def _mock_sync(sync_id=None):
    s = MagicMock()
    s.id = sync_id or uuid4()
    return s


def _mock_sync_job(job_id=None):
    j = MagicMock()
    j.id = job_id or uuid4()
    return j


# ---------------------------------------------------------------------------
# run() — table-driven
# ---------------------------------------------------------------------------


@dataclass
class RunCase:
    name: str
    factory_error: Optional[Exception] = None
    orchestrator_result: Optional[MagicMock] = field(default=None)
    expect_job_failed: bool = False
    expect_raises: bool = False

    def __post_init__(self):
        """Default orchestrator_result to a MagicMock when no factory error."""
        if self.orchestrator_result is None and self.factory_error is None:
            self.orchestrator_result = MagicMock()


RUN_CASES = [
    RunCase(
        name="happy_path",
    ),
    RunCase(
        name="factory_raises_marks_job_failed",
        factory_error=RuntimeError("bad config"),
        expect_job_failed=True,
        expect_raises=True,
    ),
    RunCase(
        name="factory_value_error",
        factory_error=ValueError("missing field"),
        expect_job_failed=True,
        expect_raises=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", RUN_CASES, ids=lambda c: c.name)
async def test_run(case: RunCase):
    fake_state_machine = AsyncMock()
    fake_factory = MagicMock()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=case.orchestrator_result)

    if case.factory_error:
        fake_factory.create_orchestrator = AsyncMock(
            side_effect=case.factory_error,
        )
    else:
        fake_factory.create_orchestrator = AsyncMock(
            return_value=mock_orchestrator,
        )

    svc = SyncService(
        sync_repo=MagicMock(),
        sync_job_repo=MagicMock(),
        sync_cursor_repo=MagicMock(),
        state_machine=MagicMock(),
        job_state_machine=fake_state_machine,
        temporal_workflow_service=MagicMock(),
        temporal_schedule_service=MagicMock(),
        sync_factory=fake_factory,
    )

    sync = _mock_sync()
    sync_job = _mock_sync_job()
    collection = MagicMock()
    source_connection = MagicMock()
    ctx = _mock_ctx()

    mock_db = AsyncMock()

    with patch(
        "airweave.domains.syncs.service.get_db_context",
    ) as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        if case.expect_raises:
            with pytest.raises(type(case.factory_error)):
                await svc.run(
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    source_connection=source_connection,
                    ctx=ctx,
                )
        else:
            result = await svc.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=source_connection,
                ctx=ctx,
            )
            assert result is case.orchestrator_result
            mock_orchestrator.run.assert_awaited_once()

    if case.expect_job_failed:
        fake_state_machine.transition.assert_awaited_once()
        call_kwargs = fake_state_machine.transition.call_args.kwargs
        assert call_kwargs["sync_job_id"] == sync_job.id
        assert call_kwargs["target"] == SyncJobStatus.FAILED
        assert call_kwargs["error"] == str(case.factory_error)
    else:
        fake_state_machine.transition.assert_not_awaited()


# ---------------------------------------------------------------------------
# run() — optional kwargs forwarded to factory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_optional_kwargs():
    """force_full_sync, execution_config reach the factory."""
    fake_state_machine = AsyncMock()
    fake_factory = MagicMock()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=_mock_sync())
    fake_factory.create_orchestrator = AsyncMock(
        return_value=mock_orchestrator,
    )

    svc = SyncService(
        sync_repo=MagicMock(),
        sync_job_repo=MagicMock(),
        sync_cursor_repo=MagicMock(),
        state_machine=MagicMock(),
        job_state_machine=fake_state_machine,
        temporal_workflow_service=MagicMock(),
        temporal_schedule_service=MagicMock(),
        sync_factory=fake_factory,
    )

    mock_db = AsyncMock()
    exec_config = MagicMock()

    with patch(
        "airweave.domains.syncs.service.get_db_context",
    ) as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await svc.run(
            sync=_mock_sync(),
            sync_job=_mock_sync_job(),
            collection=MagicMock(),
            source_connection=MagicMock(),
            ctx=_mock_ctx(),
            force_full_sync=True,
            execution_config=exec_config,
        )

        _, kwargs = fake_factory.create_orchestrator.call_args
        assert kwargs["force_full_sync"] is True
        assert kwargs["execution_config"] is exec_config


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credential_error_propagates_error_category():
    """Factory raising a credential error -> error_category set on state machine transition."""
    from airweave.core.shared_models import SourceConnectionErrorCategory
    from airweave.domains.sources.exceptions import SourceValidationError
    from airweave.domains.sources.token_providers.exceptions import TokenExpiredError
    from airweave.domains.sources.token_providers.protocol import AuthProviderKind

    cause = TokenExpiredError(
        "JWT expired", source_short_name="github", provider_kind=AuthProviderKind.OAUTH
    )
    wrapper = SourceValidationError(short_name="github", reason="credential validation failed")
    wrapper.__cause__ = cause

    fake_sm = AsyncMock()
    fake_factory = MagicMock()
    fake_factory.create_orchestrator = AsyncMock(side_effect=wrapper)

    svc = SyncService(
        sync_repo=MagicMock(),
        sync_job_repo=MagicMock(),
        sync_cursor_repo=MagicMock(),
        state_machine=AsyncMock(),
        job_state_machine=fake_sm,
        temporal_workflow_service=MagicMock(),
        temporal_schedule_service=MagicMock(),
        sync_factory=fake_factory,
    )

    with patch("airweave.domains.syncs.service.get_db_context") as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(SourceValidationError):
            await svc.run(
                sync=_mock_sync(),
                sync_job=_mock_sync_job(),
                collection=MagicMock(),
                source_connection=MagicMock(),
                ctx=_mock_ctx(),
            )

    fake_sm.transition.assert_awaited_once()
    call_kwargs = fake_sm.transition.call_args.kwargs
    assert call_kwargs["target"] == SyncJobStatus.FAILED
    assert call_kwargs["error_category"] == SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED


@pytest.mark.asyncio
async def test_non_credential_error_has_no_error_category():
    """Non-auth factory error -> error_category=None on state machine transition."""
    fake_sm = AsyncMock()
    fake_factory = MagicMock()
    fake_factory.create_orchestrator = AsyncMock(side_effect=RuntimeError("bad config"))

    svc = SyncService(
        sync_repo=MagicMock(),
        sync_job_repo=MagicMock(),
        sync_cursor_repo=MagicMock(),
        state_machine=AsyncMock(),
        job_state_machine=fake_sm,
        temporal_workflow_service=MagicMock(),
        temporal_schedule_service=MagicMock(),
        sync_factory=fake_factory,
    )

    with patch("airweave.domains.syncs.service.get_db_context") as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError):
            await svc.run(
                sync=_mock_sync(),
                sync_job=_mock_sync_job(),
                collection=MagicMock(),
                source_connection=MagicMock(),
                ctx=_mock_ctx(),
            )

    call_kwargs = fake_sm.transition.call_args.kwargs
    assert call_kwargs["error_category"] is None


def test_stores_injected_deps():
    fake_sm = MagicMock()
    fake_factory = MagicMock()
    svc = SyncService(
        sync_repo=MagicMock(),
        sync_job_repo=MagicMock(),
        sync_cursor_repo=MagicMock(),
        state_machine=fake_sm,
        job_state_machine=MagicMock(),
        temporal_workflow_service=MagicMock(),
        temporal_schedule_service=MagicMock(),
        sync_factory=fake_factory,
    )
    assert svc._state_machine is fake_sm
    assert svc._sync_factory is fake_factory


# ---------------------------------------------------------------------------
# Helper: build a SyncService with configurable mocks
# ---------------------------------------------------------------------------


def _build_svc(
    sync_repo=None,
    sync_job_repo=None,
    sync_cursor_repo=None,
    state_machine=None,
    job_state_machine=None,
    temporal_workflow_service=None,
    temporal_schedule_service=None,
    sync_factory=None,
):
    return SyncService(
        sync_repo=sync_repo or AsyncMock(),
        sync_job_repo=sync_job_repo or AsyncMock(),
        sync_cursor_repo=sync_cursor_repo or AsyncMock(),
        state_machine=state_machine or AsyncMock(),
        job_state_machine=job_state_machine or AsyncMock(),
        temporal_workflow_service=temporal_workflow_service or AsyncMock(),
        temporal_schedule_service=temporal_schedule_service or AsyncMock(),
        sync_factory=sync_factory or MagicMock(),
    )


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_sync():
    repo = AsyncMock()
    expected = MagicMock()
    repo.get.return_value = expected

    svc = _build_svc(sync_repo=repo)
    result = await svc.get(AsyncMock(), sync_id=uuid4(), ctx=_mock_ctx())
    assert result is expected


@pytest.mark.asyncio
async def test_get_raises_when_not_found():
    repo = AsyncMock()
    repo.get.return_value = None

    svc = _build_svc(sync_repo=repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.get(AsyncMock(), sync_id=uuid4(), ctx=_mock_ctx())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# pause() / resume()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_delegates_to_state_machine():
    from airweave.core.shared_models import SyncStatus

    sm = AsyncMock()
    expected = MagicMock()
    sm.transition.return_value = expected

    svc = _build_svc(state_machine=sm)
    sid = uuid4()
    result = await svc.pause(sid, _mock_ctx(), reason="maintenance")

    assert result is expected
    call_kw = sm.transition.call_args.kwargs
    assert call_kw["sync_id"] == sid
    assert call_kw["target"] == SyncStatus.PAUSED
    assert call_kw["reason"] == "maintenance"


@pytest.mark.asyncio
async def test_resume_delegates_to_state_machine():
    from airweave.core.shared_models import SyncStatus

    sm = AsyncMock()
    expected = MagicMock()
    sm.transition.return_value = expected

    svc = _build_svc(state_machine=sm)
    sid = uuid4()
    result = await svc.resume(sid, _mock_ctx())

    assert result is expected
    assert sm.transition.call_args.kwargs["target"] == SyncStatus.ACTIVE


# ---------------------------------------------------------------------------
# resolve_destination_ids()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_destination_ids_returns_vespa():
    from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID

    svc = _build_svc()
    result = await svc.resolve_destination_ids(AsyncMock(), _mock_ctx())
    assert result == [NATIVE_VESPA_UUID]


# ---------------------------------------------------------------------------
# get_jobs()
# ---------------------------------------------------------------------------


def _orm_sync_job(job_id=None, sync_id=None, status=SyncJobStatus.COMPLETED):
    """Create a MagicMock that passes schemas.SyncJob.model_validate()."""
    m = MagicMock()
    m.id = job_id or uuid4()
    m.sync_id = sync_id or uuid4()
    m.organization_id = uuid4()
    m.status = status
    m.scheduled = False
    m.entities_inserted = 0
    m.entities_updated = 0
    m.entities_deleted = 0
    m.entities_kept = 0
    m.entities_skipped = 0
    m.entities_encountered = {}
    m.started_at = None
    m.completed_at = None
    m.failed_at = None
    m.error = None
    m.error_category = None
    m.access_token = None
    m.sync_config = None
    m.sync_metadata = None
    m.created_by_email = None
    m.modified_by_email = None
    m.created_at = None
    m.modified_at = None
    m.sync_name = None
    return m


@pytest.mark.asyncio
async def test_get_jobs_returns_validated_schemas():
    job_repo = AsyncMock()
    mock_job = _orm_sync_job()
    job_repo.get_all_by_sync_id.return_value = [mock_job]

    svc = _build_svc(sync_job_repo=job_repo)
    jobs = await svc.get_jobs(AsyncMock(), sync_id=uuid4(), ctx=_mock_ctx())
    assert len(jobs) == 1
    assert jobs[0].id == mock_job.id


# ---------------------------------------------------------------------------
# validate_force_full_sync()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_force_full_sync_no_cursor():
    cursor_repo = AsyncMock()
    cursor_repo.get_by_sync_id.return_value = None

    svc = _build_svc(sync_cursor_repo=cursor_repo)
    ctx = _mock_ctx()
    await svc.validate_force_full_sync(AsyncMock(), uuid4(), ctx)
    ctx.logger.info.assert_called_once()
    assert "no cursor data" in ctx.logger.info.call_args[0][0]


@pytest.mark.asyncio
async def test_validate_force_full_sync_with_cursor():
    cursor_repo = AsyncMock()
    cursor = MagicMock()
    cursor.cursor_data = {"some": "data"}
    cursor_repo.get_by_sync_id.return_value = cursor

    svc = _build_svc(sync_cursor_repo=cursor_repo)
    ctx = _mock_ctx()
    await svc.validate_force_full_sync(AsyncMock(), uuid4(), ctx)
    ctx.logger.info.assert_called_once()
    assert "Force full sync" in ctx.logger.info.call_args[0][0]


# ---------------------------------------------------------------------------
# cancel_job()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_job_not_found():
    job_repo = AsyncMock()
    job_repo.get.return_value = None

    svc = _build_svc(sync_job_repo=job_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.cancel_job(AsyncMock(), job_id=uuid4(), ctx=_mock_ctx())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job_wrong_status():
    job_repo = AsyncMock()
    job = MagicMock()
    job.status = SyncJobStatus.COMPLETED
    job_repo.get.return_value = job

    svc = _build_svc(sync_job_repo=job_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.cancel_job(AsyncMock(), job_id=uuid4(), ctx=_mock_ctx())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_cancel_job_success():
    job_id = uuid4()
    job_repo = AsyncMock()
    job = _orm_sync_job(job_id=job_id, status=SyncJobStatus.RUNNING)
    job_repo.get.return_value = job

    temporal = AsyncMock()
    temporal.cancel_sync_job_workflow.return_value = {
        "success": True,
        "workflow_found": True,
    }

    job_sm = AsyncMock()
    db = AsyncMock()

    svc = _build_svc(
        sync_job_repo=job_repo,
        temporal_workflow_service=temporal,
        job_state_machine=job_sm,
    )
    result = await svc.cancel_job(db, job_id=job_id, ctx=_mock_ctx())

    job_sm.transition.assert_awaited_once()
    assert job_sm.transition.call_args.kwargs["target"] == SyncJobStatus.CANCELLING
    temporal.cancel_sync_job_workflow.assert_awaited_once()
    assert result is not None


@pytest.mark.asyncio
async def test_cancel_job_workflow_not_found_marks_cancelled():
    job_id = uuid4()
    job_repo = AsyncMock()
    job = _orm_sync_job(job_id=job_id, status=SyncJobStatus.PENDING)
    job_repo.get.return_value = job

    temporal = AsyncMock()
    temporal.cancel_sync_job_workflow.return_value = {
        "success": True,
        "workflow_found": False,
    }

    job_sm = AsyncMock()
    db = AsyncMock()

    svc = _build_svc(
        sync_job_repo=job_repo,
        temporal_workflow_service=temporal,
        job_state_machine=job_sm,
    )
    await svc.cancel_job(db, job_id=job_id, ctx=_mock_ctx())

    assert job_sm.transition.await_count == 2
    second_call = job_sm.transition.call_args_list[1].kwargs
    assert second_call["target"] == SyncJobStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_job_temporal_failure():
    job_id = uuid4()
    job_repo = AsyncMock()
    job = MagicMock()
    job.id = job_id
    job.status = SyncJobStatus.RUNNING
    job_repo.get.return_value = job

    temporal = AsyncMock()
    temporal.cancel_sync_job_workflow.return_value = {
        "success": False,
        "workflow_found": True,
    }

    svc = _build_svc(sync_job_repo=job_repo, temporal_workflow_service=temporal)
    with pytest.raises(HTTPException) as exc_info:
        await svc.cancel_job(AsyncMock(), job_id=job_id, ctx=_mock_ctx())
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# _resolve_cron() / _validate_cron_for_source()
# ---------------------------------------------------------------------------


def _mock_source_entry(*, short_name="github", continuous=False, federated=False):
    entry = MagicMock()
    entry.short_name = short_name
    entry.supports_continuous = continuous
    entry.federated_search = federated
    return entry


def test_resolve_cron_explicit():
    from airweave.schemas.source_connection import ScheduleConfig

    svc = _build_svc()
    result = svc._resolve_cron(
        ScheduleConfig(cron="0 6 * * *"),
        _mock_source_entry(),
        _mock_ctx(),
    )
    assert result == "0 6 * * *"


def test_resolve_cron_explicit_null():
    from airweave.schemas.source_connection import ScheduleConfig

    svc = _build_svc()
    result = svc._resolve_cron(
        ScheduleConfig(cron=None),
        _mock_source_entry(),
        _mock_ctx(),
    )
    assert result is None


def test_resolve_cron_continuous_default():
    from airweave.domains.syncs.types import CONTINUOUS_SOURCE_DEFAULT_CRON

    svc = _build_svc()
    result = svc._resolve_cron(None, _mock_source_entry(continuous=True), _mock_ctx())
    assert result == CONTINUOUS_SOURCE_DEFAULT_CRON


def test_resolve_cron_daily_default():
    svc = _build_svc()
    result = svc._resolve_cron(None, _mock_source_entry(), _mock_ctx())
    assert result is not None
    parts = result.split()
    assert len(parts) == 5
    assert parts[2:] == ["*", "*", "*"]


def test_validate_cron_allows_continuous():
    svc = _build_svc()
    svc._validate_cron_for_source("* * * * *", _mock_source_entry(continuous=True))


def test_validate_cron_rejects_every_minute():
    svc = _build_svc()
    with pytest.raises(HTTPException) as exc_info:
        svc._validate_cron_for_source("* * * * *", _mock_source_entry())
    assert exc_info.value.status_code == 400


def test_validate_cron_rejects_sub_hourly():
    svc = _build_svc()
    with pytest.raises(HTTPException) as exc_info:
        svc._validate_cron_for_source("*/5 * * * *", _mock_source_entry())
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# create() — federated / no-schedule / happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_skips_federated():
    svc = _build_svc()
    with pytest.raises(ValueError, match="federated"):
        await svc.create(
            AsyncMock(),
            name="test",
            source_connection_id=uuid4(),
            destination_connection_ids=[uuid4()],
            collection_id=uuid4(),
            collection_readable_id="col-x",
            source_entry=_mock_source_entry(federated=True),
            schedule_config=None,
            run_immediately=False,
            ctx=_mock_ctx(),
            uow=MagicMock(),
        )


@pytest.mark.asyncio
async def test_create_no_cron_no_run_immediately():
    from airweave.schemas.source_connection import ScheduleConfig

    svc = _build_svc()
    with pytest.raises(ValueError, match="no schedule"):
        await svc.create(
            AsyncMock(),
            name="test",
            source_connection_id=uuid4(),
            destination_connection_ids=[uuid4()],
            collection_id=uuid4(),
            collection_readable_id="col-x",
            source_entry=_mock_source_entry(),
            schedule_config=ScheduleConfig(cron=None),
            run_immediately=False,
            ctx=_mock_ctx(),
            uow=MagicMock(),
        )


@pytest.mark.asyncio
async def test_create_with_cron_calls_temporal_schedule():
    from airweave.schemas.source_connection import ScheduleConfig

    sync_repo = AsyncMock()
    mock_sync = MagicMock()
    mock_sync.id = uuid4()
    sync_repo.create.return_value = mock_sync

    job_repo = AsyncMock()
    temporal_sched = AsyncMock()

    uow = MagicMock()
    uow.session = AsyncMock()
    uow.commit = AsyncMock()

    svc = _build_svc(
        sync_repo=sync_repo,
        sync_job_repo=job_repo,
        temporal_schedule_service=temporal_sched,
    )

    result = await svc.create(
        AsyncMock(),
        name="test",
        source_connection_id=uuid4(),
        destination_connection_ids=[uuid4()],
        collection_id=uuid4(),
        collection_readable_id="col-x",
        source_entry=_mock_source_entry(),
        schedule_config=ScheduleConfig(cron="0 6 * * *"),
        run_immediately=False,
        ctx=_mock_ctx(),
        uow=uow,
    )
    assert result is not None
    assert result.sync_id == mock_sync.id
    temporal_sched.create_or_update_schedule.assert_awaited_once()


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_delegates():
    svc = _build_svc()
    svc._cancel_active_sync = AsyncMock(return_value=True)
    svc._wait_for_terminal = AsyncMock()
    svc._schedule_cleanup = AsyncMock()

    await svc.delete(
        AsyncMock(),
        sync_id=uuid4(),
        collection_id=uuid4(),
        organization_id=uuid4(),
        ctx=_mock_ctx(),
    )
    svc._cancel_active_sync.assert_awaited_once()
    svc._wait_for_terminal.assert_awaited_once()
    svc._schedule_cleanup.assert_awaited_once()


# ---------------------------------------------------------------------------
# _cancel_active_sync()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_active_sync_cancels_running_job():
    sync_id = uuid4()
    job = MagicMock()
    job.id = uuid4()
    job.status = SyncJobStatus.RUNNING

    job_repo = AsyncMock()
    job_repo.get_latest_by_sync_id.return_value = job

    temporal = AsyncMock()
    svc = _build_svc(sync_job_repo=job_repo, temporal_workflow_service=temporal)

    result = await svc._cancel_active_sync(AsyncMock(), sync_id, _mock_ctx())
    assert result is True
    temporal.cancel_sync_job_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_active_sync_skips_terminal():
    job = MagicMock()
    job.status = SyncJobStatus.COMPLETED

    job_repo = AsyncMock()
    job_repo.get_latest_by_sync_id.return_value = job

    svc = _build_svc(sync_job_repo=job_repo)
    result = await svc._cancel_active_sync(AsyncMock(), uuid4(), _mock_ctx())
    assert result is False


# ---------------------------------------------------------------------------
# _wait_for_terminal()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_terminal_returns_when_no_job():
    job_repo = AsyncMock()
    job_repo.get_latest_by_sync_id.return_value = None
    svc = _build_svc(sync_job_repo=job_repo)
    db = MagicMock()
    with patch("airweave.domains.syncs.service.asyncio.sleep", new_callable=AsyncMock):
        await svc._wait_for_terminal(db, uuid4(), 5, _mock_ctx())
    job_repo.get_latest_by_sync_id.assert_awaited()


# ---------------------------------------------------------------------------
# _schedule_cleanup()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_cleanup_calls_temporal():
    temporal = AsyncMock()
    svc = _build_svc(temporal_workflow_service=temporal)
    await svc._schedule_cleanup(uuid4(), uuid4(), uuid4(), _mock_ctx())
    temporal.start_cleanup_sync_data_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_schedule_cleanup_handles_error():
    temporal = AsyncMock()
    temporal.start_cleanup_sync_data_workflow.side_effect = RuntimeError("boom")

    svc = _build_svc(temporal_workflow_service=temporal)
    ctx = _mock_ctx()
    await svc._schedule_cleanup(uuid4(), uuid4(), uuid4(), ctx)
    ctx.logger.error.assert_called_once()
