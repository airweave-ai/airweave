"""Unit tests for SourceRateLimitService.

Covers:
- list_rate_limits (merge, sort, pipedream defaults, empty sources)
- set_rate_limit (create new, update existing)
- delete_rate_limit (existing, no-op)
- Feature flag gating (all three methods)

Uses table-driven tests with fakes — no mocks, no database.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, FeatureFlag
from airweave.domains.source_rate_limits.fakes.repository import FakeSourceRateLimitRepository
from airweave.domains.source_rate_limits.service import SourceRateLimitService
from airweave.domains.source_rate_limits.types import PIPEDREAM_PROXY_LIMIT, PIPEDREAM_PROXY_WINDOW
from airweave.schemas.organization import Organization

NOW = datetime.now(tz=timezone.utc)
ORG_ID = uuid4()


def _make_ctx(
    org_id: UUID = ORG_ID,
    features: Optional[list[str]] = None,
) -> ApiContext:
    if features is None:
        features = [FeatureFlag.SOURCE_RATE_LIMITING.value]
    org = Organization(
        id=str(org_id),
        name="Test Org",
        created_at=NOW,
        modified_at=NOW,
        enabled_features=features,
    )
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req"),
    )


def _build_service(
    repo: Optional[FakeSourceRateLimitRepository] = None,
) -> tuple[SourceRateLimitService, FakeSourceRateLimitRepository]:
    repo = repo or FakeSourceRateLimitRepository()
    svc = SourceRateLimitService(repo=repo)
    return svc, repo


# -----------------------------------------------------------------------
# list_rate_limits
# -----------------------------------------------------------------------


@dataclass
class ListCase:
    desc: str
    sources: list[tuple[str, Optional[str]]]
    limits: list[tuple[str, int, int]]
    expected_first_short_name: str
    expected_count: int


LIST_CASES = [
    ListCase(
        desc="no sources -> only pipedream entry",
        sources=[],
        limits=[],
        expected_first_short_name="pipedream_proxy",
        expected_count=1,
    ),
    ListCase(
        desc="two sources, one with limit",
        sources=[("google_drive", "org"), ("slack", None)],
        limits=[("google_drive", 800, 60)],
        expected_first_short_name="pipedream_proxy",
        expected_count=3,
    ),
    ListCase(
        desc="pipedream source in DB is skipped from regular list",
        sources=[("pipedream_proxy", None), ("notion", "connection")],
        limits=[],
        expected_first_short_name="pipedream_proxy",
        expected_count=2,
    ),
]


@pytest.mark.parametrize("case", LIST_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_list_rate_limits(case: ListCase):
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    for short_name, level in case.sources:
        repo.seed_source(short_name, rate_limit_level=level)
    for short_name, limit, window in case.limits:
        repo.seed_limit(ORG_ID, short_name, limit, window)

    result = await svc.list_rate_limits(db, ctx=ctx)

    assert len(result) == case.expected_count
    assert result[0].source_short_name == case.expected_first_short_name


@pytest.mark.asyncio
async def test_list_pipedream_defaults():
    """Pipedream entry shows hardcoded defaults when no custom limit exists."""
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    result = await svc.list_rate_limits(db, ctx=ctx)
    pipedream = result[0]

    assert pipedream.source_short_name == "pipedream_proxy"
    assert pipedream.limit == PIPEDREAM_PROXY_LIMIT
    assert pipedream.window_seconds == PIPEDREAM_PROXY_WINDOW
    assert pipedream.id is None


@pytest.mark.asyncio
async def test_list_pipedream_custom_limit():
    """Pipedream entry shows custom limit when configured."""
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    custom_id = uuid4()
    repo.seed_limit(ORG_ID, "pipedream_proxy", limit=500, window_seconds=120, id=custom_id)

    result = await svc.list_rate_limits(db, ctx=ctx)
    pipedream = result[0]

    assert pipedream.limit == 500
    assert pipedream.window_seconds == 120
    assert pipedream.id == custom_id


@pytest.mark.asyncio
async def test_list_sort_order():
    """Sources with rate_limit_level sort before those without."""
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    repo.seed_source("zzz_unsupported", rate_limit_level=None)
    repo.seed_source("aaa_supported", rate_limit_level="org")

    result = await svc.list_rate_limits(db, ctx=ctx)
    # [0] is pipedream, [1] should be aaa_supported, [2] zzz_unsupported
    assert result[1].source_short_name == "aaa_supported"
    assert result[2].source_short_name == "zzz_unsupported"


# -----------------------------------------------------------------------
# set_rate_limit
# -----------------------------------------------------------------------


@dataclass
class SetCase:
    desc: str
    existing: bool
    limit: int
    window_seconds: int


SET_CASES = [
    SetCase(desc="create new", existing=False, limit=100, window_seconds=60),
    SetCase(desc="update existing", existing=True, limit=200, window_seconds=30),
]


@pytest.mark.parametrize("case", SET_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_set_rate_limit(case: SetCase):
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    if case.existing:
        repo.seed_limit(ORG_ID, "google_drive", limit=50, window_seconds=60)

    result = await svc.set_rate_limit(
        db,
        source_short_name="google_drive",
        limit=case.limit,
        window_seconds=case.window_seconds,
        ctx=ctx,
    )

    assert result.limit == case.limit
    assert result.source_short_name == "google_drive"


# -----------------------------------------------------------------------
# delete_rate_limit
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_existing_limit():
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    repo.seed_limit(ORG_ID, "notion", limit=3, window_seconds=1)
    await svc.delete_rate_limit(db, source_short_name="notion", ctx=ctx)

    assert (ORG_ID, "notion") not in repo._store


@pytest.mark.asyncio
async def test_delete_nonexistent_is_noop():
    svc, repo = _build_service()
    ctx = _make_ctx()
    db = AsyncMock()

    await svc.delete_rate_limit(db, source_short_name="unknown", ctx=ctx)
    remove_calls = [c for c in repo._calls if c[0] == "remove"]
    assert len(remove_calls) == 0


# -----------------------------------------------------------------------
# Feature flag gating
# -----------------------------------------------------------------------


@dataclass
class FeatureFlagCase:
    desc: str
    method: str


FEATURE_FLAG_CASES = [
    FeatureFlagCase(desc="list blocked", method="list_rate_limits"),
    FeatureFlagCase(desc="set blocked", method="set_rate_limit"),
    FeatureFlagCase(desc="delete blocked", method="delete_rate_limit"),
]


@pytest.mark.parametrize("case", FEATURE_FLAG_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_feature_flag_disabled(case: FeatureFlagCase):
    svc, _ = _build_service()
    ctx = _make_ctx(features=[])
    db = AsyncMock()

    kwargs: dict = {"source_short_name": "x", "ctx": ctx}
    if case.method == "set_rate_limit":
        kwargs["limit"] = 10
        kwargs["window_seconds"] = 60
    elif case.method == "list_rate_limits":
        kwargs = {"ctx": ctx}

    with pytest.raises(HTTPException) as exc_info:
        await getattr(svc, case.method)(db, **kwargs)

    assert exc_info.value.status_code == 403
