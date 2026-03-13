"""Table-driven tests for TemporalScheduleService.

Covers _schedule_type_for_cron, _check_schedule_exists,
create_or_update_schedule, _create_schedule, _update_schedule,
_delete_schedule_by_id, _gather_schedule_data, and
delete_all_schedules_for_sync.
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from temporalio.service import RPCError, RPCStatusCode

from airweave.domains.temporal.schedule_service import TemporalScheduleService


def _rpc_error(msg: str, status: RPCStatusCode) -> RPCError:
    return RPCError(msg, status, b"")


ORG_ID = uuid4()
SYNC_ID = uuid4()
SC_ID = uuid4()
COLLECTION_ID = uuid4()
CONNECTION_ID = uuid4()


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = ORG_ID
    ctx.logger = MagicMock()
    ctx.to_serializable_dict.return_value = {"org_id": str(ORG_ID)}
    return ctx


def _build_svc(
    *,
    sync_repo=None,
    sc_repo=None,
    collection_repo=None,
    connection_repo=None,
) -> TemporalScheduleService:
    return TemporalScheduleService(
        sync_repo=sync_repo or AsyncMock(),
        sc_repo=sc_repo or AsyncMock(),
        collection_repo=collection_repo or AsyncMock(),
        connection_repo=connection_repo or AsyncMock(),
    )


def _mock_sync_model(
    sync_id: UUID = SYNC_ID,
    temporal_schedule_id: Optional[str] = None,
) -> MagicMock:
    s = MagicMock()
    s.id = sync_id
    s.name = "test-sync"
    s.temporal_schedule_id = temporal_schedule_id
    return s


def _mock_source_connection(
    connection_id: UUID = CONNECTION_ID,
    readable_collection_id: str = "test-col",
) -> MagicMock:
    sc = MagicMock()
    sc.id = SC_ID
    sc.connection_id = connection_id
    sc.readable_collection_id = readable_collection_id
    return sc


def _mock_collection() -> MagicMock:
    c = MagicMock()
    c.id = COLLECTION_ID
    c.name = "Test Col"
    return c


def _mock_connection() -> MagicMock:
    c = MagicMock()
    c.id = CONNECTION_ID
    c.name = "Test Conn"
    return c


# ---------------------------------------------------------------------------
# _schedule_type_for_cron
# ---------------------------------------------------------------------------


@dataclass
class CronTypeCase:
    name: str
    cron: str
    expected: str


CRON_TYPE_CASES = [
    CronTypeCase(name="every_minute", cron="*/1 * * * *", expected="minute"),
    CronTypeCase(name="every_5_min", cron="*/5 * * * *", expected="minute"),
    CronTypeCase(name="every_30_min", cron="*/30 * * * *", expected="minute"),
    CronTypeCase(name="specific_minute", cron="15 * * * *", expected="minute"),
    CronTypeCase(name="hourly", cron="0 * * * *", expected="minute"),
    CronTypeCase(name="daily", cron="0 0 * * *", expected="regular"),
    CronTypeCase(name="weekly", cron="0 0 * * 1", expected="regular"),
]


@pytest.mark.parametrize("case", CRON_TYPE_CASES, ids=lambda c: c.name)
def test_schedule_type_for_cron(case: CronTypeCase):
    result = TemporalScheduleService._schedule_type_for_cron(case.cron)
    assert result == case.expected


# ---------------------------------------------------------------------------
# _check_schedule_exists
# ---------------------------------------------------------------------------


@dataclass
class CheckExistsCase:
    name: str
    describe_raises: bool = False
    paused: bool = False
    expected_exists: bool = True
    expected_running: bool = True


CHECK_EXISTS_CASES = [
    CheckExistsCase(name="exists_running"),
    CheckExistsCase(name="exists_paused", paused=True, expected_running=False),
    CheckExistsCase(
        name="not_found",
        describe_raises=True,
        expected_exists=False,
        expected_running=False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CHECK_EXISTS_CASES, ids=lambda c: c.name)
async def test_check_schedule_exists(case: CheckExistsCase):
    svc = _build_svc()
    mock_client = MagicMock()

    if case.describe_raises:
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(
            side_effect=_rpc_error("schedule not found", RPCStatusCode.NOT_FOUND)
        )
        mock_client.get_schedule_handle.return_value = mock_handle
    else:
        desc = MagicMock()
        desc.schedule.state.paused = case.paused
        desc.schedule.spec.cron_expressions = ["*/5 * * * *"]
        mock_handle = AsyncMock()
        mock_handle.describe = AsyncMock(return_value=desc)
        mock_client.get_schedule_handle.return_value = mock_handle

    svc._client = mock_client

    result = await svc._check_schedule_exists("test-schedule")
    assert result["exists"] == case.expected_exists
    assert result["running"] == case.expected_running


@pytest.mark.asyncio
async def test_check_schedule_exists_propagates_non_not_found_errors():
    """Non-NOT_FOUND RPCErrors (network, auth) must propagate, not be swallowed."""
    svc = _build_svc()
    mock_client = MagicMock()
    mock_handle = AsyncMock()
    mock_handle.describe = AsyncMock(
        side_effect=_rpc_error("connection refused", RPCStatusCode.UNAVAILABLE)
    )
    mock_client.get_schedule_handle.return_value = mock_handle
    svc._client = mock_client

    with pytest.raises(RPCError):
        await svc._check_schedule_exists("test-schedule")


# ---------------------------------------------------------------------------
# _create_schedule
# ---------------------------------------------------------------------------


@dataclass
class CreateScheduleCase:
    name: str
    schedule_type: str = "regular"
    already_exists: bool = False
    force_full_sync: bool = False


CREATE_SCHEDULE_CASES = [
    CreateScheduleCase(name="regular_new"),
    CreateScheduleCase(name="minute_new", schedule_type="minute"),
    CreateScheduleCase(name="cleanup_new", schedule_type="cleanup"),
    CreateScheduleCase(name="already_exists", already_exists=True),
    CreateScheduleCase(name="force_full_sync", force_full_sync=True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CREATE_SCHEDULE_CASES, ids=lambda c: c.name)
async def test_create_schedule(case: CreateScheduleCase):
    sync_repo = AsyncMock()
    sync_repo.get_without_connections = AsyncMock(return_value=_mock_sync_model())
    sync_repo.update = AsyncMock()
    svc = _build_svc(sync_repo=sync_repo)

    mock_client = AsyncMock()
    mock_client.create_schedule = AsyncMock()
    svc._client = mock_client

    exists_status = {
        "exists": case.already_exists,
        "running": case.already_exists,
        "schedule_info": {"schedule_id": "existing"} if case.already_exists else None,
    }

    with patch.object(svc, "_check_schedule_exists", new=AsyncMock(return_value=exists_status)):
        result = await svc._create_schedule(
            sync_id=SYNC_ID,
            cron_expression="*/5 * * * *",
            sync_dict={"id": str(SYNC_ID)},
            collection_dict={"id": str(COLLECTION_ID)},
            connection_dict={"id": str(CONNECTION_ID)},
            db=AsyncMock(),
            ctx=_mock_ctx(),
            schedule_type=case.schedule_type,
            force_full_sync=case.force_full_sync,
        )

    if case.already_exists:
        mock_client.create_schedule.assert_not_called()
    else:
        mock_client.create_schedule.assert_called_once()

    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _update_schedule
# ---------------------------------------------------------------------------


@dataclass
class UpdateScheduleCase:
    name: str
    cron: str
    is_valid: bool = True
    expected_sync_type: str = "full"


UPDATE_SCHEDULE_CASES = [
    UpdateScheduleCase(name="valid_daily", cron="0 0 * * *"),
    UpdateScheduleCase(
        name="valid_minute_interval",
        cron="*/5 * * * *",
        expected_sync_type="incremental",
    ),
    UpdateScheduleCase(
        name="valid_specific_minute",
        cron="15 * * * *",
        expected_sync_type="incremental",
    ),
    UpdateScheduleCase(name="invalid_cron", cron="bad", is_valid=False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", UPDATE_SCHEDULE_CASES, ids=lambda c: c.name)
async def test_update_schedule(case: UpdateScheduleCase):
    sync_repo = AsyncMock()
    sync_model = _mock_sync_model()
    sync_repo.get_without_connections = AsyncMock(return_value=sync_model)
    sync_repo.update = AsyncMock()
    svc = _build_svc(sync_repo=sync_repo)

    mock_client = MagicMock()
    mock_handle = AsyncMock()
    mock_handle.update = AsyncMock()
    mock_client.get_schedule_handle.return_value = mock_handle
    svc._client = mock_client

    db = AsyncMock()
    uow = AsyncMock()
    ctx = _mock_ctx()

    if not case.is_valid:
        with pytest.raises(HTTPException) as exc_info:
            await svc._update_schedule("sched-1", case.cron, SYNC_ID, db, uow, ctx)
        assert exc_info.value.status_code == 422
    else:
        await svc._update_schedule("sched-1", case.cron, SYNC_ID, db, uow, ctx)
        mock_handle.update.assert_called_once()
        sync_repo.update.assert_called_once()


# ---------------------------------------------------------------------------
# _delete_schedule_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_schedule_by_id():
    sync_repo = AsyncMock()
    sync_model = _mock_sync_model()
    sync_repo.get_without_connections = AsyncMock(return_value=sync_model)
    sync_repo.update = AsyncMock()
    svc = _build_svc(sync_repo=sync_repo)

    mock_client = MagicMock()
    mock_handle = AsyncMock()
    mock_handle.delete = AsyncMock()
    mock_client.get_schedule_handle.return_value = mock_handle
    svc._client = mock_client

    await svc._delete_schedule_by_id("sched-1", SYNC_ID, AsyncMock(), _mock_ctx())

    mock_handle.delete.assert_called_once()
    sync_repo.update.assert_called_once()


# ---------------------------------------------------------------------------
# _gather_schedule_data
# ---------------------------------------------------------------------------


@dataclass
class GatherCase:
    name: str
    sc_exists: bool = True
    collection_exists: bool = True
    connection_id: Optional[UUID] = CONNECTION_ID
    connection_exists: bool = True
    expect_error: bool = False


GATHER_CASES = [
    GatherCase(name="happy_path"),
    GatherCase(name="no_source_connection", sc_exists=False, expect_error=True),
    GatherCase(name="no_collection", collection_exists=False, expect_error=True),
    GatherCase(name="no_connection_id", connection_id=None, expect_error=True),
    GatherCase(name="connection_not_found", connection_exists=False, expect_error=True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GATHER_CASES, ids=lambda c: c.name)
async def test_gather_schedule_data(case: GatherCase):
    sync_repo = AsyncMock()
    sc_repo = AsyncMock()
    collection_repo = AsyncMock()
    connection_repo = AsyncMock()

    sync_repo.get = AsyncMock(return_value=_mock_sync_model())
    sc_repo.get_by_sync_id = AsyncMock(
        return_value=(
            _mock_source_connection(connection_id=case.connection_id) if case.sc_exists else None
        ),
    )
    collection_repo.get_by_readable_id = AsyncMock(
        return_value=_mock_collection() if case.collection_exists else None
    )
    connection_repo.get = AsyncMock(
        return_value=_mock_connection() if case.connection_exists else None
    )

    svc = _build_svc(
        sync_repo=sync_repo,
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
    )

    db = AsyncMock()
    ctx = _mock_ctx()

    def _mock_validate(val):
        return MagicMock(model_dump=MagicMock(return_value=val))

    if case.expect_error:
        with pytest.raises(ValueError):
            with patch("airweave.domains.temporal.schedule_service.schemas") as ms:
                ms.Sync.model_validate.return_value = _mock_validate({})
                ms.CollectionRecord.model_validate.return_value = _mock_validate({})
                ms.Connection.model_validate.return_value = _mock_validate({})
                await svc._gather_schedule_data(SYNC_ID, db, ctx)
    else:
        with patch("airweave.domains.temporal.schedule_service.schemas") as ms:
            ms.Sync.model_validate.return_value = _mock_validate({"id": "s"})
            ms.CollectionRecord.model_validate.return_value = _mock_validate({"id": "c"})
            ms.Connection.model_validate.return_value = _mock_validate({"id": "cn"})
            s, c, cn = await svc._gather_schedule_data(SYNC_ID, db, ctx)
            assert s == {"id": "s"}
            assert c == {"id": "c"}
            assert cn == {"id": "cn"}


@pytest.mark.asyncio
async def test_gather_schedule_data_provisioning_fallback():
    sync_repo = AsyncMock()
    sc_repo = AsyncMock()
    collection_repo = AsyncMock()
    connection_repo = AsyncMock()

    sync_repo.get = AsyncMock(return_value=_mock_sync_model())
    sc_repo.get_by_sync_id = AsyncMock(return_value=None)
    collection_repo.get_by_readable_id = AsyncMock(return_value=_mock_collection())
    connection_repo.get = AsyncMock(return_value=_mock_connection())

    svc = _build_svc(
        sync_repo=sync_repo,
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
    )

    db = AsyncMock()
    ctx = _mock_ctx()

    def _mock_validate(val):
        return MagicMock(model_dump=MagicMock(return_value=val))

    with patch("airweave.domains.temporal.schedule_service.schemas") as ms:
        ms.Sync.model_validate.return_value = _mock_validate({"id": "s"})
        ms.CollectionRecord.model_validate.return_value = _mock_validate({"id": "c"})
        ms.Connection.model_validate.return_value = _mock_validate({"id": "cn"})
        s, c, cn = await svc._gather_schedule_data(
            SYNC_ID,
            db,
            ctx,
            collection_readable_id="test-col",
            connection_id=CONNECTION_ID,
        )
        assert s == {"id": "s"}
        assert c == {"id": "c"}
        assert cn == {"id": "cn"}


# ---------------------------------------------------------------------------
# create_or_update_schedule (public)
# ---------------------------------------------------------------------------


@dataclass
class CreateOrUpdateCase:
    name: str
    cron: str = "0 0 * * *"
    cron_valid: bool = True
    sync_exists: bool = True
    has_existing_schedule: bool = False
    existing_schedule_found: bool = True


CREATE_OR_UPDATE_CASES = [
    CreateOrUpdateCase(name="invalid_cron", cron="bad", cron_valid=False),
    CreateOrUpdateCase(name="sync_not_found", sync_exists=False),
    CreateOrUpdateCase(name="new_schedule"),
    CreateOrUpdateCase(name="update_existing", has_existing_schedule=True),
    CreateOrUpdateCase(
        name="stale_schedule_recreate",
        has_existing_schedule=True,
        existing_schedule_found=False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CREATE_OR_UPDATE_CASES, ids=lambda c: c.name)
async def test_create_or_update_schedule(case: CreateOrUpdateCase):
    sync_repo = AsyncMock()
    svc = _build_svc(sync_repo=sync_repo)

    sync_model = (
        _mock_sync_model(
            temporal_schedule_id="existing-sched" if case.has_existing_schedule else None
        )
        if case.sync_exists
        else None
    )
    sync_repo.get_without_connections = AsyncMock(return_value=sync_model)

    svc._check_schedule_exists = AsyncMock(
        return_value={
            "exists": case.existing_schedule_found,
            "running": case.existing_schedule_found,
            "schedule_info": None,
        }
    )
    svc._update_schedule = AsyncMock()
    svc._gather_schedule_data = AsyncMock(return_value=({}, {}, {}))
    svc._create_schedule = AsyncMock(return_value="new-sched-id")

    db = AsyncMock()
    uow = AsyncMock()
    ctx = _mock_ctx()

    with patch("airweave.domains.temporal.schedule_service.croniter") as mock_croniter:
        mock_croniter.is_valid.return_value = case.cron_valid

        if not case.cron_valid:
            with pytest.raises(HTTPException) as exc_info:
                await svc.create_or_update_schedule(SYNC_ID, case.cron, db, ctx, uow)
            assert exc_info.value.status_code == 422
            return

        if not case.sync_exists:
            with pytest.raises(ValueError):
                await svc.create_or_update_schedule(SYNC_ID, case.cron, db, ctx, uow)
            return

        result = await svc.create_or_update_schedule(SYNC_ID, case.cron, db, ctx, uow)

        if case.has_existing_schedule and case.existing_schedule_found:
            svc._update_schedule.assert_called_once()
            assert result == "existing-sched"
        else:
            svc._create_schedule.assert_called_once()
            assert result == "new-sched-id"


# ---------------------------------------------------------------------------
# delete_all_schedules_for_sync
# ---------------------------------------------------------------------------


@dataclass
class DeleteAllCase:
    name: str
    delete_raises: list  # which prefixes raise
    expected_delete_attempts: int = 3


DELETE_ALL_CASES = [
    DeleteAllCase(name="all_succeed", delete_raises=[]),
    DeleteAllCase(name="some_not_exist", delete_raises=["minute-sync-", "daily-cleanup-"]),
    DeleteAllCase(name="all_fail", delete_raises=["sync-", "minute-sync-", "daily-cleanup-"]),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", DELETE_ALL_CASES, ids=lambda c: c.name)
async def test_delete_all_schedules_for_sync(case: DeleteAllCase):
    svc = _build_svc()
    call_log = []

    async def mock_delete(schedule_id, sync_id, db, ctx):
        call_log.append(schedule_id)
        for prefix in case.delete_raises:
            if schedule_id.startswith(prefix):
                raise Exception(f"{schedule_id} not found")

    svc._delete_schedule_by_id = mock_delete

    await svc.delete_all_schedules_for_sync(SYNC_ID, AsyncMock(), _mock_ctx())
    assert len(call_log) == case.expected_delete_attempts


# ---------------------------------------------------------------------------
# _get_client caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_caches():
    svc = _build_svc()
    mock_client = MagicMock()

    with patch("airweave.domains.temporal.schedule_service.temporal_client") as mock_tc:
        mock_tc.get_client = AsyncMock(return_value=mock_client)

        c1 = await svc._get_client()
        c2 = await svc._get_client()

        assert c1 is c2
        mock_tc.get_client.assert_called_once()


# ---------------------------------------------------------------------------
# delete_schedule_handle
# ---------------------------------------------------------------------------


@dataclass
class DeleteHandleCase:
    name: str
    delete_side_effect: Optional[Exception] = None
    expect_raises: bool = False


DELETE_HANDLE_CASES = [
    DeleteHandleCase(name="success"),
    DeleteHandleCase(
        name="not_found_ignored",
        delete_side_effect=_rpc_error("not found", RPCStatusCode.NOT_FOUND),
    ),
    DeleteHandleCase(
        name="rpc_error_propagates",
        delete_side_effect=_rpc_error("unavailable", RPCStatusCode.UNAVAILABLE),
        expect_raises=True,
    ),
    DeleteHandleCase(
        name="generic_error_swallowed",
        delete_side_effect=RuntimeError("connection reset"),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", DELETE_HANDLE_CASES, ids=lambda c: c.name)
async def test_delete_schedule_handle(case: DeleteHandleCase):
    svc = _build_svc()
    mock_client = MagicMock()
    mock_handle = AsyncMock()
    mock_handle.delete = AsyncMock(side_effect=case.delete_side_effect)
    mock_client.get_schedule_handle.return_value = mock_handle
    svc._client = mock_client

    if case.expect_raises:
        with pytest.raises(RPCError):
            await svc.delete_schedule_handle("sched-123")
    else:
        await svc.delete_schedule_handle("sched-123")

    mock_client.get_schedule_handle.assert_called_once_with("sched-123")


# ---------------------------------------------------------------------------
# _ensure_singleton_schedule
# ---------------------------------------------------------------------------


@dataclass
class EnsureSingletonCase:
    name: str
    already_exists: bool = False
    describe_raises_other: bool = False
    describe_raises_generic: bool = False


ENSURE_SINGLETON_CASES = [
    EnsureSingletonCase(name="creates_when_not_found"),
    EnsureSingletonCase(name="skips_when_exists", already_exists=True),
    EnsureSingletonCase(
        name="propagates_non_not_found_rpc",
        describe_raises_other=True,
    ),
    EnsureSingletonCase(
        name="propagates_generic_describe_error",
        describe_raises_generic=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENSURE_SINGLETON_CASES, ids=lambda c: c.name)
async def test_ensure_singleton_schedule(case: EnsureSingletonCase):
    from datetime import timedelta

    svc = _build_svc()
    mock_client = MagicMock()
    mock_handle = AsyncMock()

    if case.already_exists:
        mock_handle.describe = AsyncMock(return_value=MagicMock())
    elif case.describe_raises_other:
        mock_handle.describe = AsyncMock(
            side_effect=_rpc_error("unavailable", RPCStatusCode.UNAVAILABLE)
        )
    elif case.describe_raises_generic:
        mock_handle.describe = AsyncMock(side_effect=RuntimeError("boom"))
    else:
        mock_handle.describe = AsyncMock(
            side_effect=_rpc_error("not found", RPCStatusCode.NOT_FOUND)
        )

    mock_client.get_schedule_handle.return_value = mock_handle
    mock_client.create_schedule = AsyncMock()

    mock_workflow_cls = MagicMock()
    mock_workflow_cls.run = MagicMock()

    if case.describe_raises_other:
        with pytest.raises(RPCError):
            await svc._ensure_singleton_schedule(
                client=mock_client,
                schedule_id="test-system-sched",
                workflow_cls=mock_workflow_cls,
                workflow_id="test-workflow",
                interval=timedelta(minutes=5),
                note="test note",
            )
        mock_client.create_schedule.assert_not_called()
        return

    if case.describe_raises_generic:
        with pytest.raises(RuntimeError):
            await svc._ensure_singleton_schedule(
                client=mock_client,
                schedule_id="test-system-sched",
                workflow_cls=mock_workflow_cls,
                workflow_id="test-workflow",
                interval=timedelta(minutes=5),
                note="test note",
            )
        mock_client.create_schedule.assert_not_called()
        return

    await svc._ensure_singleton_schedule(
        client=mock_client,
        schedule_id="test-system-sched",
        workflow_cls=mock_workflow_cls,
        workflow_id="test-workflow",
        interval=timedelta(minutes=5),
        note="test note",
    )

    if case.already_exists:
        mock_client.create_schedule.assert_not_called()
    else:
        mock_client.create_schedule.assert_called_once()
        call_args = mock_client.create_schedule.call_args
        assert call_args[0][0] == "test-system-sched"


# ---------------------------------------------------------------------------
# ensure_system_schedules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_system_schedules_calls_both():
    """ensure_system_schedules should create both cleanup and API key schedules."""
    svc = _build_svc()
    mock_client = MagicMock()
    svc._client = mock_client

    call_ids = []

    async def track_ensure(client, schedule_id, **kwargs):
        call_ids.append(schedule_id)

    svc._ensure_singleton_schedule = track_ensure

    await svc.ensure_system_schedules()

    assert "cleanup-stuck-sync-jobs" in call_ids
    assert "api-key-expiration-notifications" in call_ids
    assert len(call_ids) == 2
