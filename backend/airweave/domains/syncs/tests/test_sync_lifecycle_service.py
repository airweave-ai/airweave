"""Table-driven unit tests for SyncLifecycleService.

Covers provision_sync(), run(), get_jobs(), and cancel_job() with
happy paths and error edge cases.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SyncJobStatus, SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields
from airweave.domains.syncs.fakes.sync_cursor_repository import FakeSyncCursorRepository
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.fakes.sync_job_service import FakeSyncJobService
from airweave.domains.syncs.fakes.sync_record_service import FakeSyncRecordService
from airweave.domains.syncs.sync_lifecycle_service import SyncLifecycleService
from airweave.domains.syncs.types import CONTINUOUS_SOURCE_DEFAULT_CRON, SyncProvisionResult
from airweave.domains.temporal.fakes.schedule_service import FakeTemporalScheduleService
from airweave.domains.temporal.fakes.service import FakeTemporalWorkflowService
from airweave.models.collection import Collection  # spec only
from airweave.models.connection import Connection  # spec only
from airweave.models.source_connection import SourceConnection  # spec only
from airweave.models.sync_cursor import SyncCursor  # spec only
from airweave.models.sync_job import SyncJob  # spec only
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import ScheduleConfig

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
SC_ID = uuid4()
SYNC_ID = uuid4()
JOB_ID = uuid4()
COLLECTION_ID = uuid4()
CONNECTION_ID = uuid4()
DEST_CONN_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _source_connection(
    id: UUID = SC_ID,
    sync_id: Optional[UUID] = SYNC_ID,
    connection_id: UUID = CONNECTION_ID,
) -> MagicMock:
    sc = MagicMock(spec=SourceConnection)
    sc.id = id
    sc.sync_id = sync_id
    sc.connection_id = connection_id
    sc.readable_collection_id = "test-collection"
    sc.organization_id = ORG_ID
    return sc


def _collection() -> MagicMock:
    col = MagicMock(spec=Collection)
    col.id = COLLECTION_ID
    col.name = "Test Collection"
    col.readable_id = "test-collection"
    col.organization_id = ORG_ID
    col.vector_db_deployment_metadata_id = uuid4()
    col.sync_config = None
    col.created_by_email = None
    col.modified_by_email = None
    return col


def _connection() -> MagicMock:
    conn = MagicMock(spec=Connection)
    conn.id = CONNECTION_ID
    conn.name = "Test Connection"
    conn.short_name = "github"
    conn.organization_id = ORG_ID
    return conn


def _sync_job(
    id: UUID = JOB_ID,
    sync_id: UUID = SYNC_ID,
    status: SyncJobStatus = SyncJobStatus.PENDING,
) -> MagicMock:
    job = MagicMock(spec=SyncJob)
    job.id = id
    job.sync_id = sync_id
    job.status = status
    job.organization_id = ORG_ID
    job.created_at = NOW
    job.modified_at = NOW
    job.created_by_email = "test@example.com"
    job.modified_by_email = "test@example.com"
    return job


class _FakeEventBus:
    """Minimal fake for EventBus.publish."""

    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _build_service(
    sc_repo=None,
    collection_repo=None,
    connection_repo=None,
    sync_cursor_repo=None,
    sync_service=None,
    sync_job_service=None,
    sync_job_repo=None,
    temporal_workflow_service=None,
    temporal_schedule_service=None,
    response_builder=None,
    event_bus=None,
) -> SyncLifecycleService:
    return SyncLifecycleService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        sync_cursor_repo=sync_cursor_repo or FakeSyncCursorRepository(),
        sync_service=sync_service or FakeSyncRecordService(),
        sync_job_service=sync_job_service or FakeSyncJobService(),
        sync_job_repo=sync_job_repo or FakeSyncJobRepository(),
        temporal_workflow_service=temporal_workflow_service or FakeTemporalWorkflowService(),
        temporal_schedule_service=temporal_schedule_service or FakeTemporalScheduleService(),
        response_builder=response_builder or FakeResponseBuilder(),
        event_bus=event_bus or _FakeEventBus(),
    )


# ---------------------------------------------------------------------------
# Source entry helper
# ---------------------------------------------------------------------------


def _source_entry(
    short_name: str = "github",
    supports_continuous: bool = False,
    federated_search: bool = False,
) -> SourceRegistryEntry:
    """Create a minimal SourceRegistryEntry for testing."""
    empty_fields = Fields(fields=[])
    return SourceRegistryEntry(
        name="Test Source",
        short_name=short_name,
        description="Test source for unit tests",
        class_name="FakeSource",
        source_class_ref=type("FakeSource", (), {}),
        config_ref=None,
        auth_config_ref=None,
        auth_fields=empty_fields,
        config_fields=empty_fields,
        supported_auth_providers=[],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=None,
        oauth_type=None,
        requires_byoc=False,
        supports_continuous=supports_continuous,
        federated_search=federated_search,
        supports_temporal_relevance=False,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


def _sync_schema(id: UUID = SYNC_ID) -> schemas.Sync:
    """Create a minimal Sync schema for testing."""
    return schemas.Sync(
        id=id,
        name="Sync for Test",
        source_connection_id=SC_ID,
        destination_connection_ids=[DEST_CONN_ID],
        status=SyncStatus.ACTIVE,
        organization_id=ORG_ID,
        created_at=NOW,
        modified_at=NOW,
    )


def _sync_job_schema(id: UUID = JOB_ID, sync_id: UUID = SYNC_ID) -> schemas.SyncJob:
    """Create a minimal SyncJob schema for testing."""
    return schemas.SyncJob(
        id=id,
        sync_id=sync_id,
        status=SyncJobStatus.PENDING,
        organization_id=ORG_ID,
        created_at=NOW,
        modified_at=NOW,
    )


class _FakeUoW:
    """Minimal UoW fake — just exposes .session."""

    def __init__(self, session=None):
        self.session = session or AsyncMock()


# ---------------------------------------------------------------------------
# run() tests
# ---------------------------------------------------------------------------


@dataclass
class RunCase:
    """Table-driven case for run()."""

    name: str
    sc: Optional[SourceConnection] = None
    collection: Optional[Collection] = None
    connection: Optional[Connection] = None
    force_full_sync: bool = False
    cursor: Optional[SyncCursor] = None
    trigger_result: Optional[tuple] = None
    expected_error: Optional[str] = None
    expected_status: Optional[int] = None


_SYNC_SCHEMA = MagicMock()
_SYNC_SCHEMA.model_dump.return_value = {}
_SYNC_JOB_SCHEMA = MagicMock()
_SYNC_JOB_SCHEMA.id = JOB_ID
_SYNC_JOB_SCHEMA.to_source_connection_job.return_value = MagicMock()


RUN_CASES = [
    RunCase(
        name="missing_source_connection",
        expected_error="Source connection not found",
        expected_status=404,
    ),
    RunCase(
        name="no_sync_id",
        sc=_source_connection(sync_id=None),
        expected_error="Source connection has no associated sync",
        expected_status=400,
    ),
    RunCase(
        name="force_full_sync_no_cursor",
        sc=_source_connection(),
        collection=_collection(),
        connection=_connection(),
        force_full_sync=True,
        expected_error="force_full_sync can only be used with continuous syncs",
        expected_status=400,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", RUN_CASES, ids=lambda c: c.name)
async def test_run_errors(case: RunCase):
    """Test run() error paths."""
    sc_repo = FakeSourceConnectionRepository()
    collection_repo = FakeCollectionRepository()
    connection_repo = FakeConnectionRepository()
    sync_cursor_repo = FakeSyncCursorRepository()

    if case.sc:
        sc_repo.seed(case.sc.id, case.sc)
    if case.collection:
        collection_repo.seed(case.collection.id, case.collection)
    if case.connection:
        connection_repo.seed(case.connection.id, case.connection)
    if case.cursor:
        sync_cursor_repo.seed(SYNC_ID, case.cursor)

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
        sync_cursor_repo=sync_cursor_repo,
    )

    with pytest.raises(HTTPException) as exc_info:
        await svc.run(
            AsyncMock(),
            id=case.sc.id if case.sc else uuid4(),
            ctx=_ctx(),
            force_full_sync=case.force_full_sync,
        )

    assert exc_info.value.status_code == case.expected_status
    assert case.expected_error in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_run_force_full_sync_happy_path():
    """Test run() with force_full_sync=True and valid cursor data."""

    sc_repo = FakeSourceConnectionRepository()
    collection_repo = FakeCollectionRepository()
    connection_repo = FakeConnectionRepository()
    sync_cursor_repo = FakeSyncCursorRepository()
    sync_service = FakeSyncRecordService()
    temporal_workflow_service = FakeTemporalWorkflowService()
    event_bus = _FakeEventBus()

    sc = _source_connection()
    sc_repo.seed(SC_ID, sc)
    collection_repo.seed_readable("test-collection", _collection())
    connection_repo.seed(CONNECTION_ID, _connection())

    cursor = MagicMock(spec=SyncCursor)
    cursor.cursor_data = {"last_modified": "2024-01-01"}
    sync_cursor_repo.seed(SYNC_ID, cursor)

    mock_sync = MagicMock()
    mock_sync_job = MagicMock()
    sync_service.set_trigger_result(mock_sync, mock_sync_job)

    mock_collection_schema = MagicMock()
    mock_collection_schema.id = COLLECTION_ID
    mock_collection_schema.name = "Test Collection"
    mock_collection_schema.readable_id = "test-collection"

    mock_connection_schema = MagicMock()
    mock_connection_schema.short_name = "github"

    expected_sc_job = MagicMock()
    mock_sj_schema = MagicMock()
    mock_sj_schema.id = JOB_ID
    mock_sj_schema.to_source_connection_job.return_value = expected_sc_job

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
        sync_cursor_repo=sync_cursor_repo,
        sync_service=sync_service,
        temporal_workflow_service=temporal_workflow_service,
        event_bus=event_bus,
    )

    _mod = "airweave.domains.syncs.sync_lifecycle_service.schemas"
    with (
        patch(f"{_mod}.Collection.model_validate", return_value=mock_collection_schema),
        patch(f"{_mod}.Connection.model_validate", return_value=mock_connection_schema),
        patch(f"{_mod}.SyncJob.model_validate", return_value=mock_sj_schema),
    ):
        result = await svc.run(AsyncMock(), id=SC_ID, ctx=_ctx(), force_full_sync=True)

    assert result == expected_sc_job
    assert len(event_bus.events) == 1
    assert len(temporal_workflow_service._calls) == 1
    wf_call = temporal_workflow_service._calls[0]
    assert wf_call[0] == "run_source_connection_workflow"
    assert wf_call[7] is True  # force_full_sync arg


@pytest.mark.asyncio
async def test_run_happy_path():
    """Test run() happy path: triggers workflow and publishes event."""

    sc_repo = FakeSourceConnectionRepository()
    collection_repo = FakeCollectionRepository()
    connection_repo = FakeConnectionRepository()
    sync_service = FakeSyncRecordService()
    temporal_workflow_service = FakeTemporalWorkflowService()
    event_bus = _FakeEventBus()

    sc = _source_connection()
    sc_repo.seed(SC_ID, sc)
    collection_repo.seed_readable("test-collection", _collection())
    connection_repo.seed(CONNECTION_ID, _connection())

    mock_sync = MagicMock()
    mock_sync_job = MagicMock()
    sync_service.set_trigger_result(mock_sync, mock_sync_job)

    mock_collection_schema = MagicMock()
    mock_collection_schema.id = COLLECTION_ID
    mock_collection_schema.name = "Test Collection"
    mock_collection_schema.readable_id = "test-collection"

    mock_connection_schema = MagicMock()
    mock_connection_schema.short_name = "github"

    expected_sc_job = MagicMock()
    mock_sj_schema = MagicMock()
    mock_sj_schema.id = JOB_ID
    mock_sj_schema.to_source_connection_job.return_value = expected_sc_job

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
        sync_service=sync_service,
        temporal_workflow_service=temporal_workflow_service,
        event_bus=event_bus,
    )

    _mod = "airweave.domains.syncs.sync_lifecycle_service.schemas"
    with (
        patch(f"{_mod}.Collection.model_validate", return_value=mock_collection_schema),
        patch(f"{_mod}.Connection.model_validate", return_value=mock_connection_schema),
        patch(f"{_mod}.SyncJob.model_validate", return_value=mock_sj_schema),
    ):
        result = await svc.run(AsyncMock(), id=SC_ID, ctx=_ctx())

    assert result == expected_sc_job
    assert len(event_bus.events) == 1
    assert len(temporal_workflow_service._calls) == 1
    assert temporal_workflow_service._calls[0][0] == "run_source_connection_workflow"


# ---------------------------------------------------------------------------
# get_jobs() tests
# ---------------------------------------------------------------------------


@dataclass
class GetJobsCase:
    """Table-driven case for get_jobs()."""

    name: str
    sc: Optional[SourceConnection] = None
    jobs: list = field(default_factory=list)
    expected_count: int = 0
    expected_error: Optional[str] = None
    expected_status: Optional[int] = None


GET_JOBS_CASES = [
    GetJobsCase(
        name="missing_source_connection",
        expected_error="Source connection not found",
        expected_status=404,
    ),
    GetJobsCase(
        name="no_sync_id_returns_empty",
        sc=_source_connection(sync_id=None),
        expected_count=0,
    ),
    GetJobsCase(
        name="empty_jobs",
        sc=_source_connection(),
        expected_count=0,
    ),
    GetJobsCase(
        name="with_seeded_jobs",
        sc=_source_connection(),
        jobs=[_sync_job(id=uuid4()), _sync_job(id=uuid4())],
        expected_count=2,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GET_JOBS_CASES, ids=lambda c: c.name)
async def test_get_jobs(case: GetJobsCase):
    """Test get_jobs() with table-driven cases."""
    sc_repo = FakeSourceConnectionRepository()
    sync_job_repo = FakeSyncJobRepository()

    if case.sc:
        sc_repo.seed(case.sc.id, case.sc)
    if case.jobs and case.sc and case.sc.sync_id:
        sync_job_repo.seed_jobs_for_sync(case.sc.sync_id, case.jobs)

    svc = _build_service(sc_repo=sc_repo, sync_job_repo=sync_job_repo)

    if case.expected_error:
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_jobs(AsyncMock(), id=case.sc.id if case.sc else uuid4(), ctx=_ctx())
        assert exc_info.value.status_code == case.expected_status
    else:
        result = await svc.get_jobs(AsyncMock(), id=case.sc.id, ctx=_ctx())
        assert len(result) == case.expected_count


# ---------------------------------------------------------------------------
# cancel_job() tests
# ---------------------------------------------------------------------------


@dataclass
class CancelCase:
    """Table-driven case for cancel_job()."""

    name: str
    sc: Optional[SourceConnection] = None
    job: Optional[SyncJob] = None
    cancel_success: bool = True
    workflow_found: bool = True
    expected_error: Optional[str] = None
    expected_status: Optional[int] = None


CANCEL_CASES = [
    CancelCase(
        name="missing_source_connection",
        expected_error="Source connection not found",
        expected_status=404,
    ),
    CancelCase(
        name="no_sync_id",
        sc=_source_connection(sync_id=None),
        expected_error="Source connection has no associated sync",
        expected_status=400,
    ),
    CancelCase(
        name="job_not_found",
        sc=_source_connection(),
        expected_error="Sync job not found",
        expected_status=404,
    ),
    CancelCase(
        name="wrong_sync",
        sc=_source_connection(),
        job=_sync_job(sync_id=uuid4()),
        expected_error="Sync job does not belong to this source connection",
        expected_status=400,
    ),
    CancelCase(
        name="non_cancellable_state",
        sc=_source_connection(),
        job=_sync_job(status=SyncJobStatus.COMPLETED),
        expected_error="Cannot cancel job in",
        expected_status=400,
    ),
    CancelCase(
        name="temporal_failure",
        sc=_source_connection(),
        job=_sync_job(status=SyncJobStatus.RUNNING),
        cancel_success=False,
        expected_error="Failed to request cancellation from Temporal",
        expected_status=502,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CANCEL_CASES, ids=lambda c: c.name)
async def test_cancel_job_errors(case: CancelCase):
    """Test cancel_job() error paths."""
    sc_repo = FakeSourceConnectionRepository()
    sync_job_repo = FakeSyncJobRepository()
    sync_job_service = FakeSyncJobService()
    temporal_workflow_service = FakeTemporalWorkflowService()

    if case.sc:
        sc_repo.seed(case.sc.id, case.sc)
    if case.job:
        sync_job_repo.seed(case.job.id, case.job)

    temporal_workflow_service.set_cancel_result(
        {"success": case.cancel_success, "workflow_found": case.workflow_found}
    )

    svc = _build_service(
        sc_repo=sc_repo,
        sync_job_repo=sync_job_repo,
        sync_job_service=sync_job_service,
        temporal_workflow_service=temporal_workflow_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        await svc.cancel_job(
            AsyncMock(),
            source_connection_id=case.sc.id if case.sc else uuid4(),
            job_id=case.job.id if case.job else JOB_ID,
            ctx=_ctx(),
        )

    assert exc_info.value.status_code == case.expected_status
    assert case.expected_error in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_cancel_job_happy_path():
    """Successful cancel: workflow found, job transitions to CANCELLING."""

    sc_repo = FakeSourceConnectionRepository()
    sync_job_repo = FakeSyncJobRepository()
    sync_job_service = FakeSyncJobService()
    temporal_workflow_service = FakeTemporalWorkflowService()

    sc = _source_connection()
    sc_repo.seed(SC_ID, sc)

    job = _sync_job(status=SyncJobStatus.RUNNING)
    sync_job_repo.seed(JOB_ID, job)

    temporal_workflow_service.set_cancel_result({"success": True, "workflow_found": True})

    db_mock = AsyncMock()

    svc = _build_service(
        sc_repo=sc_repo,
        sync_job_repo=sync_job_repo,
        sync_job_service=sync_job_service,
        temporal_workflow_service=temporal_workflow_service,
    )

    mock_sj_schema = MagicMock()
    expected_result = MagicMock()
    mock_sj_schema.to_source_connection_job.return_value = expected_result

    _mod = "airweave.domains.syncs.sync_lifecycle_service.schemas"
    with patch(f"{_mod}.SyncJob.model_validate", return_value=mock_sj_schema):
        result = await svc.cancel_job(
            db_mock, source_connection_id=SC_ID, job_id=JOB_ID, ctx=_ctx()
        )

    assert result == expected_result
    statuses = [c[2] for c in sync_job_service._calls if c[0] == "update_status"]
    assert statuses == [SyncJobStatus.CANCELLING]
    assert len(temporal_workflow_service._calls) == 1


@pytest.mark.asyncio
async def test_cancel_job_workflow_not_found():
    """When workflow is not found, job should be marked CANCELLED directly."""
    from unittest.mock import patch

    sc_repo = FakeSourceConnectionRepository()
    sync_job_repo = FakeSyncJobRepository()
    sync_job_service = FakeSyncJobService()
    temporal_workflow_service = FakeTemporalWorkflowService()

    sc = _source_connection()
    sc_repo.seed(SC_ID, sc)

    job = _sync_job(status=SyncJobStatus.RUNNING)
    sync_job_repo.seed(JOB_ID, job)

    temporal_workflow_service.set_cancel_result({"success": True, "workflow_found": False})

    db_mock = AsyncMock()

    svc = _build_service(
        sc_repo=sc_repo,
        sync_job_repo=sync_job_repo,
        sync_job_service=sync_job_service,
        temporal_workflow_service=temporal_workflow_service,
    )

    mock_sj_schema = MagicMock()
    mock_sj_schema.to_source_connection_job.return_value = MagicMock()

    _mod = "airweave.domains.syncs.sync_lifecycle_service.schemas"
    with patch(f"{_mod}.SyncJob.model_validate", return_value=mock_sj_schema):
        await svc.cancel_job(db_mock, source_connection_id=SC_ID, job_id=JOB_ID, ctx=_ctx())

    statuses = [c[2] for c in sync_job_service._calls if c[0] == "update_status"]
    assert statuses == [SyncJobStatus.CANCELLING, SyncJobStatus.CANCELLED]


# ---------------------------------------------------------------------------
# provision_sync() tests
# ---------------------------------------------------------------------------


@dataclass
class ProvisionCase:
    """Table-driven case for provision_sync()."""

    name: str
    source_entry: Optional[SourceRegistryEntry] = None
    schedule_config: Optional[ScheduleConfig] = None
    run_immediately: bool = True
    expected_none: bool = False
    expected_error: Optional[str] = None
    expected_status: Optional[int] = None
    expected_cron: Optional[str] = None
    expect_schedule_call: bool = False


PROVISION_CASES = [
    ProvisionCase(
        name="federated_search_returns_none",
        source_entry=_source_entry(federated_search=True),
        expected_none=True,
    ),
    ProvisionCase(
        name="no_schedule_no_immediate_returns_none",
        source_entry=_source_entry(),
        schedule_config=ScheduleConfig(cron=None),
        run_immediately=False,
        expected_none=True,
    ),
    ProvisionCase(
        name="default_continuous_schedule",
        source_entry=_source_entry(supports_continuous=True),
        expected_cron=CONTINUOUS_SOURCE_DEFAULT_CRON,
        expect_schedule_call=True,
    ),
    ProvisionCase(
        name="explicit_cron_used",
        source_entry=_source_entry(),
        schedule_config=ScheduleConfig(cron="0 3 * * *"),
        expected_cron="0 3 * * *",
        expect_schedule_call=True,
    ),
    ProvisionCase(
        name="sub_hourly_rejected_for_non_continuous",
        source_entry=_source_entry(supports_continuous=False),
        schedule_config=ScheduleConfig(cron="*/5 * * * *"),
        expected_error="does not support continuous syncs",
        expected_status=400,
    ),
    ProvisionCase(
        name="every_minute_rejected_for_non_continuous",
        source_entry=_source_entry(supports_continuous=False),
        schedule_config=ScheduleConfig(cron="* * * * *"),
        expected_error="does not support continuous syncs",
        expected_status=400,
    ),
    ProvisionCase(
        name="sub_hourly_ok_for_continuous",
        source_entry=_source_entry(supports_continuous=True),
        schedule_config=ScheduleConfig(cron="*/5 * * * *"),
        expected_cron="*/5 * * * *",
        expect_schedule_call=True,
    ),
    ProvisionCase(
        name="happy_path_immediate_no_schedule",
        source_entry=_source_entry(),
        schedule_config=ScheduleConfig(cron=None),
        run_immediately=True,
        expected_none=False,
        expected_cron=None,
        expect_schedule_call=False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", PROVISION_CASES, ids=lambda c: c.name)
async def test_provision_sync(case: ProvisionCase):
    """Test provision_sync() with table-driven cases."""
    sync_service = FakeSyncRecordService()
    temporal_schedule_service = FakeTemporalScheduleService()

    mock_sync = _sync_schema()
    mock_sync_job = _sync_job_schema()
    sync_service.set_create_result(mock_sync, mock_sync_job)

    svc = _build_service(
        sync_service=sync_service,
        temporal_schedule_service=temporal_schedule_service,
    )

    uow = _FakeUoW()

    if case.expected_error:
        with pytest.raises(HTTPException) as exc_info:
            await svc.provision_sync(
                uow.session,
                name="Test",
                source_connection_id=SC_ID,
                destination_connection_ids=[DEST_CONN_ID],
                collection_id=COLLECTION_ID,
                collection_readable_id="test-collection",
                source_entry=case.source_entry or _source_entry(),
                schedule_config=case.schedule_config,
                run_immediately=case.run_immediately,
                ctx=_ctx(),
                uow=uow,
            )
        assert exc_info.value.status_code == case.expected_status
        assert case.expected_error in str(exc_info.value.detail)
        return

    result = await svc.provision_sync(
        uow.session,
        name="Test",
        source_connection_id=SC_ID,
        destination_connection_ids=[DEST_CONN_ID],
        collection_id=COLLECTION_ID,
        collection_readable_id="test-collection",
        source_entry=case.source_entry or _source_entry(),
        schedule_config=case.schedule_config,
        run_immediately=case.run_immediately,
        ctx=_ctx(),
        uow=uow,
    )

    if case.expected_none:
        assert result is None
        assert len(sync_service._calls) == 0
        return

    assert result is not None
    assert isinstance(result, SyncProvisionResult)
    assert result.sync_id == SYNC_ID
    assert result.cron_schedule == case.expected_cron

    create_calls = [c for c in sync_service._calls if c[0] == "create_sync"]
    assert len(create_calls) == 1
    assert create_calls[0][3] == case.expected_cron  # cron_schedule arg

    schedule_calls = [
        c for c in temporal_schedule_service._calls if c[0] == "create_or_update_schedule"
    ]
    if case.expect_schedule_call:
        assert len(schedule_calls) == 1
        assert schedule_calls[0][2] == case.expected_cron
    else:
        assert len(schedule_calls) == 0


@pytest.mark.asyncio
async def test_provision_sync_default_daily_schedule():
    """Default daily schedule uses current UTC hour:minute."""
    sync_service = FakeSyncRecordService()
    temporal_schedule_service = FakeTemporalScheduleService()

    mock_sync = _sync_schema()
    sync_service.set_create_result(mock_sync, _sync_job_schema())

    svc = _build_service(
        sync_service=sync_service,
        temporal_schedule_service=temporal_schedule_service,
    )

    uow = _FakeUoW()
    result = await svc.provision_sync(
        uow.session,
        name="Test",
        source_connection_id=SC_ID,
        destination_connection_ids=[DEST_CONN_ID],
        collection_id=COLLECTION_ID,
        collection_readable_id="test-collection",
        source_entry=_source_entry(supports_continuous=False),
        schedule_config=None,
        run_immediately=True,
        ctx=_ctx(),
        uow=uow,
    )

    assert result is not None
    parts = result.cron_schedule.split()
    assert len(parts) == 5
    assert parts[2:] == ["*", "*", "*"]  # daily schedule pattern

    schedule_calls = [
        c for c in temporal_schedule_service._calls if c[0] == "create_or_update_schedule"
    ]
    assert len(schedule_calls) == 1
