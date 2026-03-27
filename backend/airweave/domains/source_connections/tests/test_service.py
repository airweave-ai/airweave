"""Unit tests for SourceConnectionService.

Verifies parity with the old core.source_connection_service.list implementation
and ensures no regressions in the new domain-based architecture.

Uses table-driven tests wherever possible.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SourceConnectionStatus, SyncJobStatus
from airweave.domains.auth_provider.fake import FakeAuthProviderRegistry
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.oauth.fakes.repository import FakeOAuthRedirectSessionRepository
from airweave.domains.source_connections.fakes.create import FakeSourceConnectionCreateService
from airweave.domains.source_connections.fakes.delete import FakeSourceConnectionDeletionService
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.source_connections.fakes.update import FakeSourceConnectionUpdateService
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.source_connections.types import LastJobInfo, SourceConnectionStats
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.syncs.fakes.sync_service import FakeSyncService
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import AuthenticationMethod, SourceConnectionListItem

NOW = utc_now()
ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _make_stats(
    *,
    name: str = "conn",
    short_name: str = "github",
    collection_id: str = "col-abc",
    is_authenticated: bool = True,
    is_active: bool = True,
    entity_count: int = 42,
    federated_search: bool = False,
    last_job: Optional[LastJobInfo] = None,
    authentication_method: Optional[str] = "direct",
) -> SourceConnectionStats:
    return SourceConnectionStats(
        id=uuid4(),
        name=name,
        short_name=short_name,
        readable_collection_id=collection_id,
        created_at=NOW,
        modified_at=NOW,
        is_authenticated=is_authenticated,
        readable_auth_provider_id=None,
        connection_init_session_id=None,
        is_active=is_active,
        authentication_method=authentication_method,
        last_job=last_job,
        entity_count=entity_count,
        federated_search=federated_search,
    )


def _build_service(
    sc_repo: Optional[FakeSourceConnectionRepository] = None,
    redirect_session_repo: Optional[FakeOAuthRedirectSessionRepository] = None,
) -> SourceConnectionService:
    return SourceConnectionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=FakeCollectionRepository(),
        connection_repo=FakeConnectionRepository(),
        redirect_session_repo=redirect_session_repo or FakeOAuthRedirectSessionRepository(),
        source_registry=FakeSourceRegistry(),
        auth_provider_registry=FakeAuthProviderRegistry(),
        response_builder=FakeResponseBuilder(),
        sync_service=FakeSyncService(),
        temporal_workflow_service=AsyncMock(),
        event_bus=AsyncMock(),
        create_service=FakeSourceConnectionCreateService(),
        update_service=FakeSourceConnectionUpdateService(),
        deletion_service=FakeSourceConnectionDeletionService(),
    )


async def _list_single(stats: SourceConnectionStats) -> SourceConnectionListItem:
    """Seed one stats object, run list, return the single item."""
    repo = FakeSourceConnectionRepository()
    repo.seed_stats([stats])
    svc = _build_service(sc_repo=repo)
    items = await svc.list(AsyncMock(), ctx=_make_ctx())
    assert len(items) == 1
    return items[0]


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


async def test_empty_repo_returns_empty_list():
    svc = _build_service()
    assert await svc.list(AsyncMock(), ctx=_make_ctx()) == []


async def test_maps_all_fields():
    stats = _make_stats(
        name="My GitHub",
        short_name="github",
        collection_id="docs-x7k9",
        entity_count=150,
        authentication_method="direct",
        federated_search=False,
        is_active=True,
        is_authenticated=True,
    )
    item = await _list_single(stats)

    assert isinstance(item, SourceConnectionListItem)
    assert item.id == stats.id
    assert item.name == "My GitHub"
    assert item.short_name == "github"
    assert item.readable_collection_id == "docs-x7k9"
    assert item.created_at == NOW
    assert item.modified_at == NOW
    assert item.is_authenticated is True
    assert item.entity_count == 150
    assert item.federated_search is False
    assert item.authentication_method == "direct"
    assert item.is_active is True
    assert item.last_job_status is None


async def test_preserves_order():
    repo = FakeSourceConnectionRepository()
    repo.seed_stats(
        [
            _make_stats(name="A", short_name="slack"),
            _make_stats(name="B", short_name="github"),
            _make_stats(name="C", short_name="notion"),
        ]
    )
    svc = _build_service(sc_repo=repo)

    items = await svc.list(AsyncMock(), ctx=_make_ctx())
    assert [i.name for i in items] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Filter / pagination delegation
# ---------------------------------------------------------------------------


async def test_collection_filter_delegated():
    repo = FakeSourceConnectionRepository()
    repo.seed_stats(
        [
            _make_stats(name="A", collection_id="col-1"),
            _make_stats(name="B", collection_id="col-2"),
        ]
    )
    svc = _build_service(sc_repo=repo)

    items = await svc.list(AsyncMock(), ctx=_make_ctx(), readable_collection_id="col-1")

    assert len(items) == 1
    assert items[0].readable_collection_id == "col-1"


async def test_skip_and_limit_delegated():
    repo = FakeSourceConnectionRepository()
    repo.seed_stats([_make_stats(name=f"conn-{i}") for i in range(5)])
    svc = _build_service(sc_repo=repo)

    items = await svc.list(AsyncMock(), ctx=_make_ctx(), skip=1, limit=2)

    assert len(items) == 2
    assert items[0].name == "conn-1"
    assert items[1].name == "conn-2"


# ---------------------------------------------------------------------------
# Last-job status extraction (table-driven)
# ---------------------------------------------------------------------------


@dataclass
class LastJobCase:
    desc: str
    job_status: SyncJobStatus
    completed_at: Optional[datetime]


LAST_JOB_CASES = [
    LastJobCase("completed", SyncJobStatus.COMPLETED, NOW),
    LastJobCase("running", SyncJobStatus.RUNNING, None),
    LastJobCase("failed", SyncJobStatus.FAILED, NOW),
    LastJobCase("cancelling", SyncJobStatus.CANCELLING, None),
]


@pytest.mark.parametrize("case", LAST_JOB_CASES, ids=lambda c: c.desc)
async def test_last_job_status_extraction(case: LastJobCase):
    job = LastJobInfo(status=case.job_status, completed_at=case.completed_at)
    item = await _list_single(_make_stats(last_job=job))
    assert item.last_job_status == case.job_status


async def test_no_last_job_yields_none():
    item = await _list_single(_make_stats(last_job=None))
    assert item.last_job_status is None


# ---------------------------------------------------------------------------
# Computed status parity — regression check against old service (table-driven)
# ---------------------------------------------------------------------------


@dataclass
class StatusCase:
    desc: str
    is_authenticated: bool
    is_active: bool
    job_status: Optional[SyncJobStatus]
    expect: SourceConnectionStatus


STATUS_CASES = [
    StatusCase(
        "unauthenticated → PENDING_AUTH", False, True, None, SourceConnectionStatus.PENDING_AUTH
    ),
    StatusCase("inactive → INACTIVE", True, False, None, SourceConnectionStatus.INACTIVE),
    StatusCase(
        "running → SYNCING", True, True, SyncJobStatus.RUNNING, SourceConnectionStatus.SYNCING
    ),
    StatusCase(
        "cancelling → SYNCING", True, True, SyncJobStatus.CANCELLING, SourceConnectionStatus.SYNCING
    ),
    StatusCase("failed → ERROR", True, True, SyncJobStatus.FAILED, SourceConnectionStatus.ERROR),
    StatusCase(
        "completed → ACTIVE", True, True, SyncJobStatus.COMPLETED, SourceConnectionStatus.ACTIVE
    ),
    StatusCase("no job → ACTIVE", True, True, None, SourceConnectionStatus.ACTIVE),
]


@pytest.mark.parametrize("case", STATUS_CASES, ids=lambda c: c.desc)
async def test_computed_status(case: StatusCase):
    last_job = (
        LastJobInfo(status=case.job_status, completed_at=NOW if case.job_status else None)
        if case.job_status
        else None
    )
    item = await _list_single(
        _make_stats(
            is_authenticated=case.is_authenticated, is_active=case.is_active, last_job=last_job
        )
    )
    assert item.status == case.expect


# ---------------------------------------------------------------------------
# Computed auth_method parity (table-driven)
# ---------------------------------------------------------------------------


@dataclass
class AuthMethodCase:
    desc: str
    db_value: str
    expect: AuthenticationMethod


AUTH_METHOD_CASES = [
    AuthMethodCase("direct", "direct", AuthenticationMethod.DIRECT),
    AuthMethodCase("oauth_browser", "oauth_browser", AuthenticationMethod.OAUTH_BROWSER),
    AuthMethodCase("oauth_token", "oauth_token", AuthenticationMethod.OAUTH_TOKEN),
    AuthMethodCase("oauth_byoc", "oauth_byoc", AuthenticationMethod.OAUTH_BYOC),
    AuthMethodCase("auth_provider", "auth_provider", AuthenticationMethod.AUTH_PROVIDER),
]


@pytest.mark.parametrize("case", AUTH_METHOD_CASES, ids=lambda c: c.desc)
async def test_computed_auth_method(case: AuthMethodCase):
    item = await _list_single(_make_stats(authentication_method=case.db_value))
    assert item.auth_method == case.expect


# ---------------------------------------------------------------------------
# Federated search — regression test (old service dropped this field)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [True, False], ids=["federated=True", "federated=False"])
async def test_federated_search_propagated(value: bool):
    item = await _list_single(_make_stats(federated_search=value))
    assert item.federated_search is value


# ---------------------------------------------------------------------------
# get_sync_id
# ---------------------------------------------------------------------------


async def test_get_sync_id_returns_sync_id():
    sc = MagicMock()
    sc.sync_id = uuid4()
    repo = FakeSourceConnectionRepository()
    repo.seed(sc.id, sc)
    svc = _build_service(sc_repo=repo)

    result = await svc.get_sync_id(AsyncMock(), id=sc.id, ctx=_make_ctx())
    assert result == {"sync_id": str(sc.sync_id)}


async def test_get_sync_id_not_found_raises():
    svc = _build_service()
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.get_sync_id(AsyncMock(), id=uuid4(), ctx=_make_ctx())


async def test_get_sync_id_no_sync_raises():
    sc = MagicMock()
    sc.sync_id = None
    repo = FakeSourceConnectionRepository()
    repo.seed(sc.id, sc)
    svc = _build_service(sc_repo=repo)

    with pytest.raises(NotFoundException, match="No sync found"):
        await svc.get_sync_id(AsyncMock(), id=sc.id, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# get_redirect_url
# ---------------------------------------------------------------------------


async def test_get_redirect_url_returns_url():
    redirect_repo = FakeOAuthRedirectSessionRepository()
    session = MagicMock()
    session.final_url = "https://provider.example.com/auth?state=abc"
    session.expires_at = utc_now() + timedelta(minutes=5)
    redirect_repo.seed("abc123", session)
    svc = _build_service(redirect_session_repo=redirect_repo)

    result = await svc.get_redirect_url(AsyncMock(), code="abc123")
    assert result == "https://provider.example.com/auth?state=abc"


async def test_get_redirect_url_replay_raises():
    redirect_repo = FakeOAuthRedirectSessionRepository()
    session = MagicMock()
    session.final_url = "https://provider.example.com/auth?state=abc"
    session.expires_at = utc_now() + timedelta(minutes=5)
    redirect_repo.seed("abc123", session)
    svc = _build_service(redirect_session_repo=redirect_repo)

    await svc.get_redirect_url(AsyncMock(), code="abc123")
    with pytest.raises(NotFoundException, match="Authorization link expired or invalid"):
        await svc.get_redirect_url(AsyncMock(), code="abc123")


async def test_get_redirect_url_expired_raises():
    redirect_repo = FakeOAuthRedirectSessionRepository()
    session = MagicMock()
    session.final_url = "https://provider.example.com/auth?state=abc"
    session.expires_at = utc_now() - timedelta(minutes=1)
    redirect_repo.seed("abc123", session)
    svc = _build_service(redirect_session_repo=redirect_repo)

    with pytest.raises(NotFoundException, match="Authorization link expired or invalid"):
        await svc.get_redirect_url(AsyncMock(), code="abc123")


async def test_get_redirect_url_missing_code_raises():
    svc = _build_service()
    with pytest.raises(NotFoundException, match="Authorization link expired or invalid"):
        await svc.get_redirect_url(AsyncMock(), code="nonexistent")


# ---------------------------------------------------------------------------
# Sync lifecycle proxies: run, get_jobs, cancel_job, count_by_organization
# ---------------------------------------------------------------------------

SYNC_ID = uuid4()
SC_ID = uuid4()
JOB_ID = uuid4()
CONN_ID = uuid4()
COL_READABLE_ID = "test-col-abc"


def _make_source_conn(
    *,
    id: UUID = SC_ID,
    sync_id: UUID = SYNC_ID,
    connection_id: UUID = CONN_ID,
    readable_collection_id: str = COL_READABLE_ID,
):
    sc = MagicMock()
    sc.id = id
    sc.sync_id = sync_id
    sc.connection_id = connection_id
    sc.readable_collection_id = readable_collection_id
    return sc


def _make_collection(readable_id: str = COL_READABLE_ID):
    col = MagicMock()
    col.id = uuid4()
    col.name = "Test Collection"
    col.readable_id = readable_id
    col.organization_id = ORG_ID
    return col


def _make_connection(id: UUID = CONN_ID):
    conn = MagicMock()
    conn.id = id
    conn.short_name = "github"
    conn.name = "GitHub"
    return conn


def _make_sync_schema():
    return MagicMock(spec_set=["id", "status"])


def _make_sync_job_schema(*, sync_id: UUID = SYNC_ID, job_id: UUID = JOB_ID):
    job = MagicMock()
    job.id = job_id
    job.sync_id = sync_id
    job.status = SyncJobStatus.PENDING
    job.started_at = None
    job.completed_at = None
    job.error = None
    job.error_category = None
    job.entities_inserted = 0
    job.entities_updated = 0
    job.entities_deleted = 0
    job.entities_skipped = 0
    return job


def _build_run_service(
    sc_repo=None,
    sync_service=None,
    collection_repo=None,
    connection_repo=None,
    temporal_workflow_service=None,
    event_bus=None,
):
    return SourceConnectionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        redirect_session_repo=FakeOAuthRedirectSessionRepository(),
        source_registry=FakeSourceRegistry(),
        auth_provider_registry=FakeAuthProviderRegistry(),
        response_builder=FakeResponseBuilder(),
        sync_service=sync_service or FakeSyncService(),
        temporal_workflow_service=temporal_workflow_service or AsyncMock(),
        event_bus=event_bus or AsyncMock(),
        create_service=FakeSourceConnectionCreateService(),
        update_service=FakeSourceConnectionUpdateService(),
        deletion_service=FakeSourceConnectionDeletionService(),
    )


async def test_run_triggers_workflow_and_returns_job():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    sync_svc.set_trigger_run_result(_make_sync_schema(), _make_sync_job_schema())

    temporal = AsyncMock()
    event_bus = AsyncMock()

    svc = _build_run_service(
        sc_repo=sc_repo,
        sync_service=sync_svc,
        temporal_workflow_service=temporal,
        event_bus=event_bus,
    )

    col_id = uuid4()
    col_schema = MagicMock(id=col_id, name="Col", readable_id="col-x")
    conn_schema = MagicMock(short_name="github")
    svc._resolve_collection = AsyncMock(return_value=col_schema)
    svc._resolve_connection = AsyncMock(return_value=conn_schema)

    result = await svc.run(AsyncMock(), id=SC_ID, ctx=_make_ctx())

    assert result.id == JOB_ID
    assert result.source_connection_id == SC_ID
    assert result.status == SyncJobStatus.PENDING
    temporal.run_source_connection_workflow.assert_awaited_once()
    call_kwargs = temporal.run_source_connection_workflow.call_args.kwargs
    assert call_kwargs["collection"] is col_schema
    assert call_kwargs["connection"] is conn_schema
    assert call_kwargs["force_full_sync"] is False


async def test_run_event_failure_does_not_block():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    sync_svc.set_trigger_run_result(_make_sync_schema(), _make_sync_job_schema())

    event_bus = AsyncMock()
    event_bus.publish.side_effect = RuntimeError("event bus down")

    svc = _build_run_service(sc_repo=sc_repo, sync_service=sync_svc, event_bus=event_bus)
    svc._resolve_collection = AsyncMock(
        return_value=MagicMock(id=uuid4(), name="Col", readable_id="col-x")
    )
    svc._resolve_connection = AsyncMock(return_value=MagicMock(short_name="github"))

    result = await svc.run(AsyncMock(), id=SC_ID, ctx=_make_ctx())

    assert result.id == JOB_ID


async def test_run_not_found_raises():
    svc = _build_run_service()
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.run(AsyncMock(), id=uuid4(), ctx=_make_ctx())


async def test_get_jobs_returns_mapped_jobs():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    j1 = _make_sync_job_schema(job_id=uuid4())
    j1.entities_inserted = 42
    j1.entities_updated = 3
    j2 = _make_sync_job_schema(job_id=uuid4())
    sync_svc.seed_jobs(SYNC_ID, [j1, j2])

    svc = _build_run_service(sc_repo=sc_repo, sync_service=sync_svc)
    jobs = await svc.get_jobs(AsyncMock(), id=SC_ID, ctx=_make_ctx())

    assert len(jobs) == 2
    assert jobs[0].source_connection_id == SC_ID
    assert jobs[0].entities_inserted == 42
    assert jobs[0].entities_updated == 3
    assert jobs[1].source_connection_id == SC_ID
    assert jobs[1].entities_inserted == 0


async def test_get_jobs_not_found_raises():
    svc = _build_run_service()
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.get_jobs(AsyncMock(), id=uuid4(), ctx=_make_ctx())


async def test_cancel_job_validates_ownership():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    job = _make_sync_job_schema(sync_id=SYNC_ID)
    sync_svc.set_cancel_result(job)

    svc = _build_run_service(sc_repo=sc_repo, sync_service=sync_svc)
    result = await svc.cancel_job(
        AsyncMock(), source_connection_id=SC_ID, job_id=JOB_ID, ctx=_make_ctx()
    )
    assert result.id == JOB_ID


async def test_cancel_job_wrong_sync_raises():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    wrong_job = _make_sync_job_schema(sync_id=uuid4())
    sync_svc.set_cancel_result(wrong_job)

    svc = _build_run_service(sc_repo=sc_repo, sync_service=sync_svc)
    with pytest.raises(NotFoundException, match="Job not found for this source connection"):
        await svc.cancel_job(
            AsyncMock(), source_connection_id=SC_ID, job_id=JOB_ID, ctx=_make_ctx()
        )


async def test_run_with_force_full_sync():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    sync_svc = FakeSyncService()
    sync_svc.set_trigger_run_result(_make_sync_schema(), _make_sync_job_schema())

    svc = _build_run_service(sc_repo=sc_repo, sync_service=sync_svc)
    svc._resolve_collection = AsyncMock(
        return_value=MagicMock(id=uuid4(), name="Col", readable_id="col-x")
    )
    svc._resolve_connection = AsyncMock(return_value=MagicMock(short_name="github"))

    result = await svc.run(AsyncMock(), id=SC_ID, ctx=_make_ctx(), force_full_sync=True)
    assert result.id == JOB_ID
    assert ("validate_force_full_sync", SYNC_ID) in sync_svc._calls


async def test_resolve_collection_not_found():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    col_repo = FakeCollectionRepository()
    svc = _build_run_service(sc_repo=sc_repo, collection_repo=col_repo)

    with pytest.raises(NotFoundException, match="Collection not found"):
        await svc._resolve_collection(AsyncMock(), sc, _make_ctx())


async def test_resolve_collection_no_readable_id():
    sc = _make_source_conn(readable_collection_id=None)
    svc = _build_run_service()

    with pytest.raises(ValueError, match="has no readable_collection_id"):
        await svc._resolve_collection(AsyncMock(), sc, _make_ctx())


async def test_resolve_connection_not_found():
    sc = _make_source_conn()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(SC_ID, sc)

    conn_repo = FakeConnectionRepository()
    svc = _build_run_service(sc_repo=sc_repo, connection_repo=conn_repo)

    with pytest.raises(ValueError, match="not found"):
        await svc._resolve_connection(AsyncMock(), sc, _make_ctx())


async def test_resolve_connection_no_connection_id():
    sc = _make_source_conn(connection_id=None)
    svc = _build_run_service()

    with pytest.raises(ValueError, match="has no connection_id"):
        await svc._resolve_connection(AsyncMock(), sc, _make_ctx())


async def test_count_by_organization():
    sc_repo = FakeSourceConnectionRepository()
    svc = _build_run_service(sc_repo=sc_repo)
    count = await svc.count_by_organization(AsyncMock(), organization_id=ORG_ID)
    assert count == 0
