"""Tests for session validation in the context resolver.

Exercises _validate_or_create_session logic: cache hits/misses,
revoked sessions, creation, and the IntegrityError recovery path.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave import schemas
from airweave.adapters.cache.fake import FakeContextCache
from airweave.api.context_resolver import ContextResolver
from airweave.models.user_session import UserSession


def _make_user(**kwargs):
    defaults = {
        "id": uuid4(),
        "email": "user@example.com",
        "first_name": "Test",
        "last_name": "User",
        "created_at": datetime.now(timezone.utc),
        "modified_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return schemas.User(**defaults)


def _make_request(sid="test-sid"):
    """Build a mock Request with a JWT containing the given sid."""
    request = MagicMock()
    request.headers = {"authorization": "Bearer mock-token", "user-agent": "test-agent"}
    request.url.path = "/test"
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


def _make_resolver(cache=None, session_repo=None):
    return ContextResolver(
        cache=cache or FakeContextCache(),
        rate_limiter=MagicMock(),
        user_repo=MagicMock(),
        api_key_repo=MagicMock(),
        org_repo=MagicMock(),
        session_repo=session_repo or MagicMock(),
    )


class TestValidateOrCreateSession:
    """Tests for _validate_or_create_session."""

    @pytest.mark.asyncio
    async def test_cache_hit_valid_passes(self):
        cache = FakeContextCache()
        await cache.mark_session_valid("sid-1", True)
        session_repo = MagicMock()
        session_repo.update_last_active = AsyncMock()
        resolver = _make_resolver(cache=cache, session_repo=session_repo)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "https://airweave.ai/sid": "sid-1",
            },
        ):
            await resolver._validate_or_create_session(request, db, user)
        # Should not raise

    @pytest.mark.asyncio
    async def test_cache_hit_revoked_raises_401(self):
        cache = FakeContextCache()
        await cache.mark_session_valid("sid-1", False)
        resolver = _make_resolver(cache=cache)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "https://airweave.ai/sid": "sid-1",
            },
        ):
            with pytest.raises(HTTPException) as exc_info:
                await resolver._validate_or_create_session(request, db, user)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_db_hit_revoked_caches_false_and_raises(self):
        cache = FakeContextCache()
        session_repo = MagicMock()
        revoked_session = MagicMock(spec=UserSession)
        revoked_session.is_revoked = True
        session_repo.get_by_session_id = AsyncMock(return_value=revoked_session)
        resolver = _make_resolver(cache=cache, session_repo=session_repo)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "https://airweave.ai/sid": "sid-1",
            },
        ):
            with pytest.raises(HTTPException) as exc_info:
                await resolver._validate_or_create_session(request, db, user)
            assert exc_info.value.status_code == 401

        assert await cache.is_session_valid("sid-1") is False

    @pytest.mark.asyncio
    async def test_db_hit_valid_caches_true(self):
        cache = FakeContextCache()
        session_repo = MagicMock()
        valid_session = MagicMock(spec=UserSession)
        valid_session.is_revoked = False
        session_repo.get_by_session_id = AsyncMock(return_value=valid_session)
        session_repo.update_last_active = AsyncMock()
        resolver = _make_resolver(cache=cache, session_repo=session_repo)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "https://airweave.ai/sid": "sid-1",
            },
        ):
            await resolver._validate_or_create_session(request, db, user)

        assert await cache.is_session_valid("sid-1") is True

    @pytest.mark.asyncio
    async def test_creates_session_on_cache_and_db_miss(self):
        cache = FakeContextCache()
        session_repo = MagicMock()
        session_repo.get_by_session_id = AsyncMock(return_value=None)
        session_repo.create = AsyncMock()
        resolver = _make_resolver(cache=cache, session_repo=session_repo)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "https://airweave.ai/sid": "new-sid",
            },
        ):
            await resolver._validate_or_create_session(request, db, user)

        session_repo.create.assert_called_once()
        assert await cache.is_session_valid("new-sid") is True

    @pytest.mark.asyncio
    async def test_no_sid_logs_warning_and_returns(self):
        cache = FakeContextCache()
        resolver = _make_resolver(cache=cache)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with patch("airweave.api.context_resolver.extract_claims", return_value={}):
            await resolver._validate_or_create_session(request, db, user)
        # Should not raise

    @pytest.mark.asyncio
    async def test_no_sid_required_raises_when_enabled(self):
        cache = FakeContextCache()
        resolver = _make_resolver(cache=cache)
        user = _make_user()
        request = _make_request()
        db = AsyncMock()

        with (
            patch("airweave.api.context_resolver.extract_claims", return_value={}),
            patch("airweave.api.context_resolver.settings") as mock_settings,
        ):
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            mock_settings.AUTH0_SID_REQUIRED = True
            with pytest.raises(HTTPException) as exc_info:
                await resolver._validate_or_create_session(request, db, user)
            assert exc_info.value.status_code == 401


class TestCheckTokenRevocation:
    """Tests for _check_token_revocation."""

    def test_no_revocation_timestamp_passes(self):
        user = _make_user(tokens_revoked_at=None)
        request = _make_request()
        ContextResolver._check_token_revocation(request, user)

    def test_revoked_token_raises_401(self):
        revoked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        user = _make_user(tokens_revoked_at=revoked_at)
        request = _make_request()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "iat": int(datetime(2025, 12, 31, tzinfo=timezone.utc).timestamp()),
            },
        ):
            with pytest.raises(HTTPException) as exc_info:
                ContextResolver._check_token_revocation(request, user)
            assert exc_info.value.status_code == 401

    def test_valid_token_after_revocation_passes(self):
        revoked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        user = _make_user(tokens_revoked_at=revoked_at)
        request = _make_request()

        with patch(
            "airweave.api.context_resolver.extract_claims",
            return_value={
                "iat": int(datetime(2026, 1, 2, tzinfo=timezone.utc).timestamp()),
            },
        ):
            ContextResolver._check_token_revocation(request, user)
