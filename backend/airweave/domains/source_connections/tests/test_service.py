"""Unit tests for SourceConnectionService.list.

Verifies parity with the old core.source_connection_service.list implementation
and ensures no regressions in the new domain-based architecture.

Uses table-driven tests wherever possible.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SourceConnectionStatus, SyncJobStatus
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.source_connections.types import LastJobInfo, SourceConnectionStats
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import AuthenticationMethod, SourceConnectionListItem

NOW = datetime.now(timezone.utc)
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
) -> SourceConnectionService:
    return SourceConnectionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=AsyncMock(),
        connection_repo=AsyncMock(),
        source_registry=AsyncMock(),
        auth_provider_registry=AsyncMock(),
        response_builder=FakeResponseBuilder(),
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
    repo.seed_stats([
        _make_stats(name="A", short_name="slack"),
        _make_stats(name="B", short_name="github"),
        _make_stats(name="C", short_name="notion"),
    ])
    svc = _build_service(sc_repo=repo)

    items = await svc.list(AsyncMock(), ctx=_make_ctx())
    assert [i.name for i in items] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Filter / pagination delegation
# ---------------------------------------------------------------------------


async def test_collection_filter_delegated():
    repo = FakeSourceConnectionRepository()
    repo.seed_stats([
        _make_stats(name="A", collection_id="col-1"),
        _make_stats(name="B", collection_id="col-2"),
    ])
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
    StatusCase("unauthenticated → PENDING_AUTH", False, True, None, SourceConnectionStatus.PENDING_AUTH),
    StatusCase("inactive → INACTIVE", True, False, None, SourceConnectionStatus.INACTIVE),
    StatusCase("running → SYNCING", True, True, SyncJobStatus.RUNNING, SourceConnectionStatus.SYNCING),
    StatusCase("cancelling → SYNCING", True, True, SyncJobStatus.CANCELLING, SourceConnectionStatus.SYNCING),
    StatusCase("failed → ERROR", True, True, SyncJobStatus.FAILED, SourceConnectionStatus.ERROR),
    StatusCase("completed → ACTIVE", True, True, SyncJobStatus.COMPLETED, SourceConnectionStatus.ACTIVE),
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
        _make_stats(is_authenticated=case.is_authenticated, is_active=case.is_active, last_job=last_job)
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
