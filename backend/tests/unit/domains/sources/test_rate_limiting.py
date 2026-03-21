"""Tests for the rate limiting domain — service, config provider, types."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.sources.rate_limiting.exceptions import InternalRateLimitExceeded
from airweave.domains.sources.rate_limiting.service import SourceRateLimiter
from airweave.domains.sources.rate_limiting.types import RateLimitConfig


@pytest.fixture
def org_id():
    return uuid4()


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.eval = AsyncMock()
    return r


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    entry = MagicMock()
    entry.rate_limit_level = "org"
    registry.get.return_value = entry
    return registry


@pytest.fixture
def mock_config_provider():
    return AsyncMock()


def _make_service(redis, registry, config_provider):
    return SourceRateLimiter(
        redis=redis,
        source_registry=registry,
        config_provider=config_provider,
    )


class TestCheckAndIncrement:
    """Tests for SourceRateLimiter.check_and_increment()."""

    @pytest.mark.asyncio
    async def test_skips_when_no_rate_limit_level(
        self, org_id, mock_redis, mock_config_provider
    ):
        registry = MagicMock()
        entry = MagicMock()
        entry.rate_limit_level = None
        registry.get.return_value = entry

        svc = _make_service(mock_redis, registry, mock_config_provider)
        await svc.check_and_increment(org_id, "stub")

        mock_config_provider.get_config.assert_not_called()
        mock_redis.eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_config(
        self, org_id, mock_redis, mock_registry, mock_config_provider
    ):
        mock_config_provider.get_config.return_value = None

        svc = _make_service(mock_redis, mock_registry, mock_config_provider)
        await svc.check_and_increment(org_id, "google_drive")

        mock_redis.eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_under_limit(
        self, org_id, mock_redis, mock_registry, mock_config_provider
    ):
        mock_config_provider.get_config.return_value = RateLimitConfig(
            limit=100, window_seconds=60
        )
        mock_redis.eval.return_value = [5, 0]

        svc = _make_service(mock_redis, mock_registry, mock_config_provider)
        await svc.check_and_increment(org_id, "google_drive")

        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_when_over_limit(
        self, org_id, mock_redis, mock_registry, mock_config_provider
    ):
        mock_config_provider.get_config.return_value = RateLimitConfig(
            limit=100, window_seconds=60
        )
        mock_redis.eval.return_value = [-1, 5.5]

        svc = _make_service(mock_redis, mock_registry, mock_config_provider)

        with pytest.raises(InternalRateLimitExceeded) as exc_info:
            await svc.check_and_increment(org_id, "google_drive")

        assert exc_info.value.retry_after == 5.5
        assert exc_info.value.source_short_name == "google_drive"


class TestBuildKey:
    """Tests for Redis key construction."""

    def test_org_level_key(self):
        oid = uuid4()
        key = SourceRateLimiter._build_key(oid, "google_drive", "org")
        assert key == f"source_rate_limit:{oid}:google_drive:org:org"

    def test_connection_level_key(self):
        oid = uuid4()
        cid = uuid4()
        key = SourceRateLimiter._build_key(oid, "notion", "connection", cid)
        assert key == f"source_rate_limit:{oid}:notion:connection:{cid}"


class TestRateLimitConfig:
    """Tests for the typed config dataclass."""

    def test_frozen(self):
        cfg = RateLimitConfig(limit=100, window_seconds=60)
        with pytest.raises(AttributeError):
            cfg.limit = 200

    def test_values(self):
        cfg = RateLimitConfig(limit=50, window_seconds=1)
        assert cfg.limit == 50
        assert cfg.window_seconds == 1
