"""Tests for token revocation and SSE/WebSocket auth in deps.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from jose import jwt as jose_jwt

from airweave import schemas
from airweave.api.deps import _is_token_revoked, get_user_from_token


def _make_user(**kwargs) -> schemas.User:
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


def _encode_token(claims: dict) -> str:
    return jose_jwt.encode(claims, "secret", algorithm="HS256")


class TestIsTokenRevoked:
    @pytest.mark.asyncio
    async def test_unparseable_token_is_revoked(self):
        user = _make_user()
        db = AsyncMock()
        assert await _is_token_revoked("garbage-token", user, db) is True

    @pytest.mark.asyncio
    async def test_token_before_revocation_is_revoked(self):
        revoked_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        user = _make_user(tokens_revoked_at=revoked_at)
        token = _encode_token({"iat": int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp())})
        db = AsyncMock()
        assert await _is_token_revoked(token, user, db) is True

    @pytest.mark.asyncio
    async def test_token_after_revocation_is_not_revoked(self):
        revoked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        user = _make_user(tokens_revoked_at=revoked_at)
        token = _encode_token(
            {
                "iat": int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()),
            }
        )
        db = AsyncMock()

        with patch("airweave.api.deps.settings") as mock_settings:
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            assert await _is_token_revoked(token, user, db) is False

    @pytest.mark.asyncio
    async def test_token_missing_iat_with_revocation_is_revoked(self):
        revoked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        user = _make_user(tokens_revoked_at=revoked_at)
        token = _encode_token({"sub": "user-1"})
        db = AsyncMock()
        assert await _is_token_revoked(token, user, db) is True

    @pytest.mark.asyncio
    async def test_no_revocation_timestamp_is_not_revoked(self):
        user = _make_user(tokens_revoked_at=None)
        token = _encode_token({"iat": 9999999999})
        db = AsyncMock()

        with patch("airweave.api.deps.settings") as mock_settings:
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            assert await _is_token_revoked(token, user, db) is False

    @pytest.mark.asyncio
    async def test_revoked_session_sid_is_revoked(self):
        user = _make_user(tokens_revoked_at=None)
        token = _encode_token(
            {
                "iat": 9999999999,
                "https://airweave.ai/sid": "revoked-sid",
            }
        )
        db = AsyncMock()

        revoked_session = MagicMock()
        revoked_session.is_revoked = True

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._session_repo") as mock_repo,
        ):
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            mock_repo.get_by_session_id = AsyncMock(return_value=revoked_session)
            assert await _is_token_revoked(token, user, db) is True

    @pytest.mark.asyncio
    async def test_valid_session_sid_is_not_revoked(self):
        user = _make_user(tokens_revoked_at=None)
        token = _encode_token(
            {
                "iat": 9999999999,
                "https://airweave.ai/sid": "good-sid",
            }
        )
        db = AsyncMock()

        valid_session = MagicMock()
        valid_session.is_revoked = False

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._session_repo") as mock_repo,
        ):
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            mock_repo.get_by_session_id = AsyncMock(return_value=valid_session)
            assert await _is_token_revoked(token, user, db) is False


class TestGetUserFromToken:
    @pytest.mark.asyncio
    async def test_auth_disabled_returns_system_user(self):
        user = _make_user()
        db = AsyncMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
        ):
            mock_settings.AUTH_ENABLED = False
            mock_settings.FIRST_SUPERUSER = "admin@example.com"
            mock_user = MagicMock()
            mock_repo.get_by_email = AsyncMock(return_value=mock_user)

            with patch.object(schemas.User, "model_validate", return_value=user):
                result = await get_user_from_token("Bearer some-token", db)

            assert result is not None
            assert result.email == user.email

    @pytest.mark.asyncio
    async def test_auth_disabled_no_user_returns_none(self):
        db = AsyncMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
        ):
            mock_settings.AUTH_ENABLED = False
            mock_settings.FIRST_SUPERUSER = "admin@example.com"
            mock_repo.get_by_email = AsyncMock(return_value=None)

            result = await get_user_from_token("Bearer some-token", db)
            assert result is None

    @pytest.mark.asyncio
    async def test_strips_bearer_prefix(self):
        db = AsyncMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
        ):
            mock_settings.AUTH_ENABLED = False
            mock_settings.FIRST_SUPERUSER = "admin@example.com"
            mock_repo.get_by_email = AsyncMock(return_value=None)

            await get_user_from_token("Bearer tok", db)
            mock_repo.get_by_email.assert_called_once_with(db, email="admin@example.com")

    @pytest.mark.asyncio
    async def test_auth_enabled_valid_token_returns_user(self):
        user = _make_user()
        db = AsyncMock()
        mock_auth0_user = MagicMock()
        mock_auth0_user.email = user.email
        mock_orm_user = MagicMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
            patch("airweave.api.deps._is_token_revoked", new_callable=AsyncMock) as mock_revoked,
            patch("airweave.api.auth.get_user_from_token", new_callable=AsyncMock) as mock_auth,
        ):
            mock_settings.AUTH_ENABLED = True
            mock_auth.return_value = mock_auth0_user
            mock_repo.get_by_email = AsyncMock(return_value=mock_orm_user)
            mock_revoked.return_value = False

            with patch.object(schemas.User, "model_validate", return_value=user):
                result = await get_user_from_token("Bearer valid-token", db)

            assert result is not None
            assert result.email == user.email

    @pytest.mark.asyncio
    async def test_auth_enabled_revoked_token_returns_none(self):
        user = _make_user()
        db = AsyncMock()
        mock_auth0_user = MagicMock()
        mock_auth0_user.email = user.email
        mock_orm_user = MagicMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
            patch("airweave.api.deps._is_token_revoked", new_callable=AsyncMock) as mock_revoked,
            patch("airweave.api.auth.get_user_from_token", new_callable=AsyncMock) as mock_auth,
        ):
            mock_settings.AUTH_ENABLED = True
            mock_auth.return_value = mock_auth0_user
            mock_repo.get_by_email = AsyncMock(return_value=mock_orm_user)
            mock_revoked.return_value = True

            with patch.object(schemas.User, "model_validate", return_value=user):
                result = await get_user_from_token("Bearer revoked-token", db)

            assert result is None

    @pytest.mark.asyncio
    async def test_auth_enabled_unknown_auth0_user_returns_none(self):
        db = AsyncMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.auth.get_user_from_token", new_callable=AsyncMock) as mock_auth,
        ):
            mock_settings.AUTH_ENABLED = True
            mock_auth.return_value = None

            result = await get_user_from_token("Bearer unknown-token", db)
            assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        db = AsyncMock()

        with (
            patch("airweave.api.deps.settings") as mock_settings,
            patch("airweave.api.deps._user_repo") as mock_repo,
        ):
            mock_settings.AUTH_ENABLED = False
            mock_settings.FIRST_SUPERUSER = "admin@example.com"
            # Simulate an unexpected error inside the try block
            mock_repo.get_by_email = AsyncMock(side_effect=RuntimeError("db gone"))

            result = await get_user_from_token("Bearer some-token", db)
            assert result is None
