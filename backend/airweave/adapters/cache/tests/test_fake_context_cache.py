"""Tests for FakeContextCache — read/write/invalidate + assertion helper.

The fake is the primary test double used throughout the codebase.
Verifying it works correctly prevents false-positive test passes.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.adapters.cache.fake import FakeContextCache


def _make_org(org_id=None):
    now = datetime.now(timezone.utc)
    return schemas.Organization(
        id=org_id or uuid4(), name="Test Org", created_at=now, modified_at=now,
    )


def _make_user(email="user@test.com"):
    return schemas.User(
        id=uuid4(),
        email=email,
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def cache():
    return FakeContextCache()


class TestOrganizationCache:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, cache):
        assert await cache.get_organization(uuid4()) is None

    @pytest.mark.asyncio
    async def test_set_then_get(self, cache):
        org = _make_org()
        await cache.set_organization(org)
        result = await cache.get_organization(org.id)
        assert result.id == org.id

    @pytest.mark.asyncio
    async def test_invalidate_removes(self, cache):
        org = _make_org()
        await cache.set_organization(org)
        await cache.invalidate_organization(org.id)
        assert await cache.get_organization(org.id) is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_does_not_raise(self, cache):
        await cache.invalidate_organization(uuid4())


class TestUserCache:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, cache):
        assert await cache.get_user("nobody@test.com") is None

    @pytest.mark.asyncio
    async def test_set_then_get(self, cache):
        user = _make_user("cached@test.com")
        await cache.set_user(user)
        result = await cache.get_user("cached@test.com")
        assert result.email == "cached@test.com"

    @pytest.mark.asyncio
    async def test_invalidate_removes(self, cache):
        user = _make_user("gone@test.com")
        await cache.set_user(user)
        await cache.invalidate_user("gone@test.com")
        assert await cache.get_user("gone@test.com") is None


class TestApiKeyCache:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, cache):
        assert await cache.get_api_key_org_id("nonexistent-key") is None

    @pytest.mark.asyncio
    async def test_set_then_get(self, cache):
        org_id = uuid4()
        await cache.set_api_key_org_id("secret-key", org_id)
        result = await cache.get_api_key_org_id("secret-key")
        assert result == org_id

    @pytest.mark.asyncio
    async def test_invalidate_removes(self, cache):
        org_id = uuid4()
        await cache.set_api_key_org_id("doomed-key", org_id)
        await cache.invalidate_api_key("doomed-key")
        assert await cache.get_api_key_org_id("doomed-key") is None


class TestAssertInvalidated:
    @pytest.mark.asyncio
    async def test_passes_when_invalidation_recorded(self, cache):
        await cache.invalidate_organization(uuid4())
        org_id = str(list(cache._invalidations[0])[1])
        cache.assert_invalidated("org", org_id)

    @pytest.mark.asyncio
    async def test_fails_when_not_invalidated(self, cache):
        with pytest.raises(AssertionError, match="not found"):
            cache.assert_invalidated("org", "missing-id")

    @pytest.mark.asyncio
    async def test_tracks_multiple_invalidation_types(self, cache):
        org_id = uuid4()
        await cache.invalidate_organization(org_id)
        await cache.invalidate_user("user@test.com")
        await cache.invalidate_api_key("key-123")

        cache.assert_invalidated("org", str(org_id))
        cache.assert_invalidated("user", "user@test.com")
        cache.assert_invalidated("api_key", "key-123")
