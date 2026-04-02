"""Tests for session management endpoints in users.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave import schemas
from airweave.adapters.cache.fake import FakeContextCache
from airweave.api.v1.endpoints.users import (
    list_sessions,
    terminate_all_sessions,
    terminate_other_sessions,
    terminate_session,
)
from airweave.models.user_session import UserSession


def _make_user(**kwargs) -> schemas.User:
    defaults = {
        "id": uuid4(),
        "email": "user@example.com",
        "auth0_id": "auth0|abc123",
        "first_name": "Test",
        "last_name": "User",
        "created_at": datetime.now(timezone.utc),
        "modified_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return schemas.User(**defaults)


def _make_session_model(session_id: str, user_id, is_revoked: bool = False) -> MagicMock:
    s = MagicMock(spec=UserSession)
    s.id = uuid4()
    s.user_id = user_id
    s.session_id = session_id
    s.ip_address = "127.0.0.1"
    s.user_agent = "test-agent"
    s.last_active_at = datetime.now(timezone.utc)
    s.is_revoked = is_revoked
    s.created_at = datetime.now(timezone.utc)
    s.modified_at = datetime.now(timezone.utc)
    s.expires_at = None
    return s


class TestListSessions:
    @pytest.mark.asyncio
    async def test_marks_current_session(self):
        user = _make_user()
        s1 = _make_session_model("current-sid", user.id)
        s2 = _make_session_model("other-sid", user.id)

        request = MagicMock()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value="current-sid"),
            patch("airweave.api.v1.endpoints.users._session_repo") as repo,
        ):
            repo.get_active_by_user = AsyncMock(return_value=[s1, s2])
            result = await list_sessions(request=request, db=db, current_user=user)

        assert len(result) == 2
        current = [r for r in result if r.is_current]
        assert len(current) == 1

    @pytest.mark.asyncio
    async def test_no_sid_marks_none_as_current(self):
        user = _make_user()
        s1 = _make_session_model("sid-1", user.id)

        request = MagicMock()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value=None),
            patch("airweave.api.v1.endpoints.users._session_repo") as repo,
        ):
            repo.get_active_by_user = AsyncMock(return_value=[s1])
            result = await list_sessions(request=request, db=db, current_user=user)

        assert len(result) == 1
        assert result[0].is_current is False


class TestTerminateSession:
    @pytest.mark.asyncio
    async def test_session_not_found_returns_404(self):
        user = _make_user()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await terminate_session(
                session_id=uuid4(),
                request=MagicMock(),
                db=db,
                current_user=user,
                cache=FakeContextCache(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_already_revoked_returns_400(self):
        user = _make_user()
        session = _make_session_model("sid-1", user.id, is_revoked=True)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await terminate_session(
                session_id=session.id,
                request=MagicMock(),
                db=db,
                current_user=user,
                cache=FakeContextCache(),
            )
        assert exc_info.value.status_code == 400
        assert "already revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cannot_terminate_current_session(self):
        user = _make_user()
        session = _make_session_model("current-sid", user.id)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value="current-sid"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await terminate_session(
                session_id=session.id,
                request=MagicMock(),
                db=db,
                current_user=user,
                cache=FakeContextCache(),
            )
        assert exc_info.value.status_code == 400
        assert "current session" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_successful_termination(self):
        user = _make_user()
        session = _make_session_model("other-sid", user.id)
        cache = FakeContextCache()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value="current-sid"),
            patch("airweave.api.v1.endpoints.users._session_repo") as repo,
        ):
            repo.revoke = AsyncMock()
            result = await terminate_session(
                session_id=session.id,
                request=MagicMock(),
                db=db,
                current_user=user,
                cache=cache,
            )

        assert result.terminated_count == 1
        repo.revoke.assert_called_once_with(db, "other-sid", user_id=user.id)
        db.commit.assert_called_once()
        assert await cache.is_session_valid("other-sid") is False


class TestTerminateOtherSessions:
    @pytest.mark.asyncio
    async def test_no_sid_returns_400(self):
        user = _make_user()

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value=None),
            pytest.raises(HTTPException) as exc_info,
        ):
            await terminate_other_sessions(
                request=MagicMock(),
                db=AsyncMock(),
                current_user=user,
                cache=FakeContextCache(),
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_revokes_others_preserves_current(self):
        user = _make_user()
        current = _make_session_model("current-sid", user.id)
        other = _make_session_model("other-sid", user.id)
        cache = FakeContextCache()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.users.extract_sid", return_value="current-sid"),
            patch("airweave.api.v1.endpoints.users._session_repo") as repo,
        ):
            repo.get_active_by_user = AsyncMock(return_value=[current, other])
            repo.revoke_all_for_user = AsyncMock(return_value=1)

            result = await terminate_other_sessions(
                request=MagicMock(),
                db=db,
                current_user=user,
                cache=cache,
            )

        assert result.terminated_count == 1
        repo.revoke_all_for_user.assert_called_once_with(
            db, user.id, except_session_id="current-sid"
        )
        db.commit.assert_called_once()
        # Other session invalidated, current not
        assert await cache.is_session_valid("other-sid") is False
        assert await cache.is_session_valid("current-sid") is None
        # User cache must be flushed
        cache.assert_invalidated("user", user.email)


class TestTerminateAllSessions:
    @pytest.mark.asyncio
    async def test_revokes_all_and_sets_tokens_revoked(self):
        user = _make_user()
        s1 = _make_session_model("sid-1", user.id)
        cache = FakeContextCache()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.users._session_repo") as session_repo,
            patch("airweave.api.v1.endpoints.users._user_repo") as user_repo,
            patch("airweave.api.v1.endpoints.users.revoke_auth0_grants") as mock_revoke,
        ):
            user_repo.update_user_no_auth = AsyncMock()
            session_repo.get_active_by_user = AsyncMock(return_value=[s1])
            session_repo.revoke_all_for_user = AsyncMock(return_value=1)
            mock_revoke.return_value = None

            result = await terminate_all_sessions(db=db, current_user=user, cache=cache)

        assert result.terminated_count == 1
        user_repo.update_user_no_auth.assert_called_once()
        session_repo.revoke_all_for_user.assert_called_once_with(db, user.id)
        db.commit.assert_called_once()
        mock_revoke.assert_called_once_with(user.auth0_id)
        assert await cache.is_session_valid("sid-1") is False

    @pytest.mark.asyncio
    async def test_skips_grant_revocation_without_auth0_id(self):
        user = _make_user(auth0_id=None)
        cache = FakeContextCache()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.users._session_repo") as session_repo,
            patch("airweave.api.v1.endpoints.users._user_repo") as user_repo,
            patch("airweave.api.v1.endpoints.users.revoke_auth0_grants") as mock_revoke,
        ):
            user_repo.update_user_no_auth = AsyncMock()
            session_repo.get_active_by_user = AsyncMock(return_value=[])
            session_repo.revoke_all_for_user = AsyncMock(return_value=0)

            await terminate_all_sessions(db=db, current_user=user, cache=cache)

        mock_revoke.assert_not_called()
