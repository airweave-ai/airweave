"""Tests for session validity caching — covers the negative-cache invariant.

The core property: invalidate_session must make is_session_valid return False
(not None), preventing a TOCTOU race where a concurrent request re-populates
the cache as valid after revocation.
"""

import pytest

from airweave.adapters.cache.fake import FakeContextCache


@pytest.fixture
def cache():
    return FakeContextCache()


class TestSessionValidity:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self, cache):
        assert await cache.is_session_valid("unknown-sid") is None

    @pytest.mark.asyncio
    async def test_mark_valid_then_read(self, cache):
        await cache.mark_session_valid("sid-1", True)
        assert await cache.is_session_valid("sid-1") is True

    @pytest.mark.asyncio
    async def test_mark_invalid_then_read(self, cache):
        await cache.mark_session_valid("sid-1", False)
        assert await cache.is_session_valid("sid-1") is False

    @pytest.mark.asyncio
    async def test_invalidate_returns_false_not_none(self, cache):
        """Core invariant: negative-cache prevents race condition."""
        await cache.mark_session_valid("sid-1", True)
        await cache.invalidate_session("sid-1")
        result = await cache.is_session_valid("sid-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_unknown_session_returns_false(self, cache):
        """Even an unknown session should be negative-cached after invalidation."""
        await cache.invalidate_session("never-seen")
        assert await cache.is_session_valid("never-seen") is False

    @pytest.mark.asyncio
    async def test_invalidation_recorded(self, cache):
        await cache.invalidate_session("sid-1")
        cache.assert_invalidated("session", "sid-1")
