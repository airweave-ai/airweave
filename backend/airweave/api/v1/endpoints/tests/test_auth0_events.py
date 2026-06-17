"""Tests for Auth0 event webhook endpoints.

Covers payload validation, HMAC verification, rate limiting,
and the full password-changed handler flow.
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from airweave import schemas
from airweave.adapters.cache.fake import FakeContextCache
from airweave.api.v1.endpoints.auth0_events import (
    PasswordChangedPayload,
    _WEBHOOK_MAX_REQUESTS,
    _webhook_timestamps,
    handle_password_changed,
    revoke_auth0_grants,
)


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


def _make_user_model(user_schema: schemas.User) -> MagicMock:
    """Mock ORM model that model_validate can consume."""
    model = MagicMock()
    for field in user_schema.__class__.model_fields:
        setattr(model, field, getattr(user_schema, field))
    return model


class TestPasswordChangedPayload:
    """Validates auth0_id constraints."""

    def test_valid_auth0_id(self):
        p = PasswordChangedPayload(auth0_id="auth0|507f1f77bcf86cd799439011")
        assert p.auth0_id == "auth0|507f1f77bcf86cd799439011"

    def test_valid_google_oauth2(self):
        p = PasswordChangedPayload(auth0_id="google-oauth2|123456789")
        assert p.auth0_id.startswith("google-oauth2|")

    def test_valid_enterprise_saml(self):
        p = PasswordChangedPayload(auth0_id="samlp|example.com|user@example.com")
        assert p.auth0_id == "samlp|example.com|user@example.com"

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="")

    def test_rejects_oversized(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="a" * 129)

    def test_rejects_whitespace(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="auth0 |bad")

    def test_rejects_newlines(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="auth0|bad\ninjection")

    def test_rejects_html_tags(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="<script>alert(1)</script>")

    def test_rejects_control_characters(self):
        with pytest.raises(ValidationError):
            PasswordChangedPayload(auth0_id="auth0|\x00bad")


class TestWebhookRateLimiting:
    """Verifies the in-memory rate limiter module-level state."""

    def setup_method(self):
        _webhook_timestamps.clear()

    def test_max_requests_constant(self):
        assert _WEBHOOK_MAX_REQUESTS == 30


class TestHandlePasswordChanged:
    def setup_method(self):
        _webhook_timestamps.clear()

    @pytest.mark.asyncio
    async def test_disabled_webhook_returns_403(self):
        with patch("airweave.api.v1.endpoints.auth0_events.settings") as s:
            s.AUTH0_WEBHOOK_SECRET = ""
            with pytest.raises(HTTPException) as exc_info:
                await handle_password_changed(
                    payload=PasswordChangedPayload(auth0_id="auth0|abc"),
                    x_auth0_webhook_secret="anything",
                    db=AsyncMock(),
                    cache=FakeContextCache(),
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_hmac_returns_403(self):
        with patch("airweave.api.v1.endpoints.auth0_events.settings") as s:
            s.AUTH0_WEBHOOK_SECRET = "a" * 32
            with pytest.raises(HTTPException) as exc_info:
                await handle_password_changed(
                    payload=PasswordChangedPayload(auth0_id="auth0|abc"),
                    x_auth0_webhook_secret="wrong-secret",
                    db=AsyncMock(),
                    cache=FakeContextCache(),
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_same_length_wrong_hmac_returns_403(self):
        secret = "a" * 32
        wrong = "b" * 32
        with patch("airweave.api.v1.endpoints.auth0_events.settings") as s:
            s.AUTH0_WEBHOOK_SECRET = secret
            with pytest.raises(HTTPException) as exc_info:
                await handle_password_changed(
                    payload=PasswordChangedPayload(auth0_id="auth0|abc"),
                    x_auth0_webhook_secret=wrong,
                    db=AsyncMock(),
                    cache=FakeContextCache(),
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429(self):
        secret = "a" * 32
        with patch("airweave.api.v1.endpoints.auth0_events.settings") as s:
            s.AUTH0_WEBHOOK_SECRET = secret
            # Fill the rate limit window
            now = time.monotonic()
            for _ in range(30):
                _webhook_timestamps.append(now)

            with pytest.raises(HTTPException) as exc_info:
                await handle_password_changed(
                    payload=PasswordChangedPayload(auth0_id="auth0|abc"),
                    x_auth0_webhook_secret=secret,
                    db=AsyncMock(),
                    cache=FakeContextCache(),
                )
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_unknown_user_returns_ok(self):
        secret = "a" * 32
        with (
            patch("airweave.api.v1.endpoints.auth0_events.settings") as s,
            patch("airweave.api.v1.endpoints.auth0_events._user_repo") as user_repo,
        ):
            s.AUTH0_WEBHOOK_SECRET = secret
            user_repo.get_by_auth0_id = AsyncMock(return_value=None)

            result = await handle_password_changed(
                payload=PasswordChangedPayload(auth0_id="auth0|unknown"),
                x_auth0_webhook_secret=secret,
                db=AsyncMock(),
                cache=FakeContextCache(),
            )
            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_valid_request_revokes_sessions(self):
        secret = "a" * 32
        user_schema = _make_user()
        user_model = _make_user_model(user_schema)

        active_session = MagicMock()
        active_session.session_id = "sid-1"
        cache = FakeContextCache()
        db = AsyncMock()

        with (
            patch("airweave.api.v1.endpoints.auth0_events.settings") as s,
            patch("airweave.api.v1.endpoints.auth0_events._user_repo") as user_repo,
            patch("airweave.api.v1.endpoints.auth0_events._session_repo") as session_repo,
            patch("airweave.api.v1.endpoints.auth0_events.revoke_auth0_grants") as mock_revoke,
        ):
            s.AUTH0_WEBHOOK_SECRET = secret
            user_repo.get_by_auth0_id = AsyncMock(return_value=user_model)
            user_repo.update_user_no_auth = AsyncMock()
            session_repo.get_active_by_user = AsyncMock(return_value=[active_session])
            session_repo.revoke_all_for_user = AsyncMock(return_value=1)
            mock_revoke.return_value = None

            result = await handle_password_changed(
                payload=PasswordChangedPayload(auth0_id=user_schema.auth0_id),
                x_auth0_webhook_secret=secret,
                db=db,
                cache=cache,
            )

            assert result == {"status": "ok"}
            user_repo.update_user_no_auth.assert_called_once()
            session_repo.revoke_all_for_user.assert_called_once()
            db.commit.assert_called_once()
            # Session should be negative-cached
            assert await cache.is_session_valid("sid-1") is False
            # User cache must be invalidated to prevent stale auth context
            cache.assert_invalidated("user", user_schema.email)


class TestRevokeAuth0Grants:
    @pytest.mark.asyncio
    async def test_no_client_is_noop(self):
        with patch("airweave.api.v1.endpoints.auth0_events.auth0_management_client", None):
            await revoke_auth0_grants("auth0|abc")

    @pytest.mark.asyncio
    async def test_client_error_logs_warning(self):
        mock_client = AsyncMock()
        mock_client.revoke_user_grants = AsyncMock(side_effect=Exception("API error"))

        with patch("airweave.api.v1.endpoints.auth0_events.auth0_management_client", mock_client):
            # Should not raise
            await revoke_auth0_grants("auth0|abc")
            mock_client.revoke_user_grants.assert_called_once_with("auth0|abc")

    @pytest.mark.asyncio
    async def test_client_success(self):
        mock_client = AsyncMock()
        mock_client.revoke_user_grants = AsyncMock()

        with patch("airweave.api.v1.endpoints.auth0_events.auth0_management_client", mock_client):
            await revoke_auth0_grants("auth0|abc")
            mock_client.revoke_user_grants.assert_called_once_with("auth0|abc")
