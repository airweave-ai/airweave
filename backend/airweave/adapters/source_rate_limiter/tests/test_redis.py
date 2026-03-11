"""Unit tests for RedisSourceRateLimiter.

Covers:
- check_and_increment: skips when no rate_limit_level, skips when no config,
  calls Lua script, raises on limit exceeded
- check_pipedream_proxy_limit: uses defaults, uses custom config, raises on exceeded
- Redis key format (org-level, connection-level)
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.adapters.source_rate_limiter.redis import (
    RedisSourceRateLimiter,
    _build_redis_key,
)
from airweave.core.exceptions import SourceRateLimitExceededException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_limiter(redis: AsyncMock) -> RedisSourceRateLimiter:
    return RedisSourceRateLimiter(redis_client=redis)


def _mock_redis() -> AsyncMock:
    """Minimal mock Redis with eval + get + setex."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock(return_value=True)
    # Default: allowed (count=1, retry=0)
    r.eval = AsyncMock(return_value=[1, 0])
    return r


# ---------------------------------------------------------------------------
# Redis key format
# ---------------------------------------------------------------------------


@dataclass
class KeyCase:
    desc: str
    org_id: UUID
    source_short_name: str
    rate_limit_level: str
    source_connection_id: Optional[UUID]
    expected_suffix: str


_ORG = uuid4()
_CONN = uuid4()

KEY_CASES = [
    KeyCase(
        desc="org-level",
        org_id=_ORG,
        source_short_name="google_drive",
        rate_limit_level="org",
        source_connection_id=None,
        expected_suffix=f"source_rate_limit:{_ORG}:google_drive:org:org",
    ),
    KeyCase(
        desc="connection-level",
        org_id=_ORG,
        source_short_name="notion",
        rate_limit_level="connection",
        source_connection_id=_CONN,
        expected_suffix=f"source_rate_limit:{_ORG}:notion:connection:{_CONN}",
    ),
]


@pytest.mark.parametrize("case", KEY_CASES, ids=lambda c: c.desc)
def test_build_redis_key(case: KeyCase):
    result = _build_redis_key(
        case.org_id,
        case.source_short_name,
        case.rate_limit_level,
        case.source_connection_id,
    )
    assert result == case.expected_suffix


# ---------------------------------------------------------------------------
# check_and_increment
# ---------------------------------------------------------------------------


@dataclass
class CheckCase:
    desc: str
    rate_limit_level: Optional[str]
    limit_config: Optional[dict]
    lua_result: list
    expect_raise: bool


CHECK_CASES = [
    CheckCase(
        desc="no rate_limit_level → skip",
        rate_limit_level=None,
        limit_config=None,
        lua_result=[1, 0],
        expect_raise=False,
    ),
    CheckCase(
        desc="no config → skip",
        rate_limit_level="org",
        limit_config=None,
        lua_result=[1, 0],
        expect_raise=False,
    ),
    CheckCase(
        desc="within limit → allow",
        rate_limit_level="org",
        limit_config={"limit": 100, "window_seconds": 60},
        lua_result=[5, 0],
        expect_raise=False,
    ),
    CheckCase(
        desc="over limit → raise",
        rate_limit_level="org",
        limit_config={"limit": 100, "window_seconds": 60},
        lua_result=[-1, 3.5],
        expect_raise=True,
    ),
]


@pytest.mark.parametrize("case", CHECK_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_check_and_increment(case: CheckCase):
    redis = _mock_redis()
    redis.eval = AsyncMock(return_value=case.lua_result)
    limiter = _make_limiter(redis)

    with (
        patch.object(
            limiter,
            "_get_source_rate_limit_level",
            return_value=case.rate_limit_level,
        ),
        patch.object(limiter, "_get_limit_config", return_value=case.limit_config),
    ):
        if case.expect_raise:
            with pytest.raises(SourceRateLimitExceededException):
                await limiter.check_and_increment(
                    org_id=uuid4(),
                    source_short_name="google_drive",
                )
        else:
            await limiter.check_and_increment(
                org_id=uuid4(),
                source_short_name="google_drive",
            )


@pytest.mark.asyncio
async def test_check_and_increment_no_lua_call_when_skipped():
    """Lua script should NOT be called when rate_limit_level is None."""
    redis = _mock_redis()
    limiter = _make_limiter(redis)

    with patch.object(limiter, "_get_source_rate_limit_level", return_value=None):
        await limiter.check_and_increment(org_id=uuid4(), source_short_name="x")

    redis.eval.assert_not_called()


# ---------------------------------------------------------------------------
# check_pipedream_proxy_limit
# ---------------------------------------------------------------------------


@dataclass
class PipedreamCase:
    desc: str
    limit_config: Optional[dict]
    lua_result: list
    expect_raise: bool


PIPEDREAM_CASES = [
    PipedreamCase(
        desc="defaults when no config",
        limit_config=None,
        lua_result=[50, 0],
        expect_raise=False,
    ),
    PipedreamCase(
        desc="custom config",
        limit_config={"limit": 500, "window_seconds": 120},
        lua_result=[10, 0],
        expect_raise=False,
    ),
    PipedreamCase(
        desc="over limit → raise",
        limit_config=None,
        lua_result=[-1, 2.0],
        expect_raise=True,
    ),
]


@pytest.mark.parametrize("case", PIPEDREAM_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_check_pipedream_proxy_limit(case: PipedreamCase):
    redis = _mock_redis()
    redis.eval = AsyncMock(return_value=case.lua_result)
    limiter = _make_limiter(redis)

    with patch.object(limiter, "_get_limit_config", return_value=case.limit_config):
        if case.expect_raise:
            with pytest.raises(SourceRateLimitExceededException):
                await limiter.check_pipedream_proxy_limit(org_id=uuid4())
        else:
            await limiter.check_pipedream_proxy_limit(org_id=uuid4())


@pytest.mark.asyncio
async def test_pipedream_uses_default_constants_when_no_config():
    """When no config is found, Lua should be called with PIPEDREAM defaults."""
    from airweave.domains.source_rate_limits.types import (
        PIPEDREAM_PROXY_LIMIT,
        PIPEDREAM_PROXY_WINDOW,
    )

    redis = _mock_redis()
    redis.eval = AsyncMock(return_value=[1, 0])
    limiter = _make_limiter(redis)

    with patch.object(limiter, "_get_limit_config", return_value=None):
        await limiter.check_pipedream_proxy_limit(org_id=uuid4())

    call_args = redis.eval.call_args
    assert int(call_args[0][3]) == PIPEDREAM_PROXY_LIMIT
    assert int(call_args[0][6]) == PIPEDREAM_PROXY_WINDOW
