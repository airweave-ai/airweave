"""Unit tests for SourceConnectionDeletionService.

Table-driven tests covering:
- Happy paths: no sync vs with sync (delegates to sync_service.delete)
- Error paths: not found, collection not found
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.source_connections.delete import SourceConnectionDeletionService
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.syncs.fakes.service import FakeSyncService
from airweave.models.collection import Collection
from airweave.models.source_connection import SourceConnection
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
COLLECTION_ID = uuid4()


def _make_ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _make_sc(*, id=None, sync_id=None, readable_collection_id="test-col", name="Test SC", short_name="github"):
    sc = MagicMock(spec=SourceConnection)
    sc.id = id or uuid4()
    sc.sync_id = sync_id
    sc.readable_collection_id = readable_collection_id
    sc.name = name
    sc.short_name = short_name
    sc.organization_id = ORG_ID
    sc.description = None
    sc.is_authenticated = True
    sc.created_at = NOW
    sc.modified_at = NOW
    return sc


def _make_collection(*, id=None, readable_id="test-col"):
    col = MagicMock(spec=Collection)
    col.id = id or COLLECTION_ID
    col.readable_id = readable_id
    col.organization_id = ORG_ID
    return col


def _build_service(
    sc_repo=None,
    collection_repo=None,
    response_builder=None,
    sync_service=None,
):
    return SourceConnectionDeletionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        response_builder=response_builder or FakeResponseBuilder(),
        sync_service=sync_service or FakeSyncService(),
    )


# ---------------------------------------------------------------------------
# Happy paths -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class DeleteCase:
    desc: str
    has_sync: bool
    expect_sync_delete: bool


DELETE_CASES = [
    DeleteCase("no_sync", has_sync=False, expect_sync_delete=False),
    DeleteCase("with_sync", has_sync=True, expect_sync_delete=True),
]


@pytest.mark.parametrize("case", DELETE_CASES, ids=lambda c: c.desc)
async def test_delete_happy_path(case: DeleteCase):
    sync_id = uuid4() if case.has_sync else None
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    sync_service = FakeSyncService()

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_service=sync_service,
    )

    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())

    assert result.id == sc.id
    assert sc_repo._store.get(sc.id) is None

    if case.expect_sync_delete:
        assert any(c[0] == "delete" for c in sync_service._calls)
    else:
        assert not any(c[0] == "delete" for c in sync_service._calls)


# ---------------------------------------------------------------------------
# Error paths -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class DeleteErrorCase:
    desc: str
    seed_sc: bool
    seed_collection: bool
    expect_exception: type
    expect_match: str


DELETE_ERROR_CASES = [
    DeleteErrorCase("not_found", seed_sc=False, seed_collection=False, expect_exception=NotFoundException, expect_match="Source connection not found"),
    DeleteErrorCase("collection_not_found", seed_sc=True, seed_collection=False, expect_exception=NotFoundException, expect_match="Collection not found"),
]


@pytest.mark.parametrize("case", DELETE_ERROR_CASES, ids=lambda c: c.desc)
async def test_delete_error(case: DeleteErrorCase):
    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    col_repo = FakeCollectionRepository()

    if case.seed_sc:
        sc_repo.seed(sc.id, sc)
    if case.seed_collection:
        col_repo.seed_readable(sc.readable_collection_id, _make_collection())

    svc = _build_service(sc_repo=sc_repo, collection_repo=col_repo)

    with pytest.raises(case.expect_exception, match=case.expect_match):
        await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())


async def test_delete_sync_service_failure_propagates():
    """If sync_service.delete raises, the error propagates."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    sync_service = FakeSyncService()
    sync_service.set_error(RuntimeError("sync delete boom"))

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_service=sync_service,
    )

    with pytest.raises(RuntimeError, match="sync delete boom"):
        await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())
