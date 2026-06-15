"""Tests for re-authentication recency checks (CASA-29).

Verifies:
- _check_auth_recency pure function behavior
- _extract_auth_time JWT claim extraction
- require_org_role with recent_auth_seconds parameter
- require_recent_auth standalone dependency
"""

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from airweave.api.deps import _check_auth_recency, _extract_auth_time, _extract_claims
from airweave.core.exceptions import ReauthenticationRequiredException
from airweave.core.shared_models import AuthMethod

# ---------------------------------------------------------------------------
# _check_auth_recency
# ---------------------------------------------------------------------------


class TestCheckAuthRecency:
    """Pure function: (auth_time, max_age, auth_method) -> None | raise."""

    @patch("airweave.api.deps.time")
    def test_fresh_auth_time_passes(self, mock_time):
        mock_time.time.return_value = 1000.0
        _check_auth_recency(940, 300, AuthMethod.AUTH0)

    @patch("airweave.api.deps.time")
    def test_stale_auth_time_raises(self, mock_time):
        mock_time.time.return_value = 1000.0
        with pytest.raises(ReauthenticationRequiredException) as exc_info:
            _check_auth_recency(400, 300, AuthMethod.AUTH0)
        assert exc_info.value.max_age == 300

    @patch("airweave.api.deps.time")
    def test_none_auth_time_raises(self, mock_time):
        mock_time.time.return_value = 1000.0
        with pytest.raises(ReauthenticationRequiredException) as exc_info:
            _check_auth_recency(None, 300, AuthMethod.AUTH0)
        assert exc_info.value.max_age == 300

    def test_system_auth_skipped(self):
        _check_auth_recency(None, 300, AuthMethod.SYSTEM)

    def test_internal_system_skipped(self):
        _check_auth_recency(None, 300, AuthMethod.INTERNAL_SYSTEM)

    def test_stripe_webhook_skipped(self):
        _check_auth_recency(None, 300, AuthMethod.STRIPE_WEBHOOK)

    def test_oauth_callback_skipped(self):
        _check_auth_recency(None, 300, AuthMethod.OAUTH_CALLBACK)

    @patch("airweave.api.deps.time")
    def test_boundary_exactly_at_max_age_passes(self, mock_time):
        mock_time.time.return_value = 1000.0
        _check_auth_recency(700, 300, AuthMethod.AUTH0)

    @patch("airweave.api.deps.time")
    def test_boundary_one_second_past_raises(self, mock_time):
        mock_time.time.return_value = 1000.0
        with pytest.raises(ReauthenticationRequiredException):
            _check_auth_recency(699, 300, AuthMethod.AUTH0)

    def test_api_key_auth_with_none_raises(self):
        with pytest.raises(ReauthenticationRequiredException):
            _check_auth_recency(None, 300, AuthMethod.API_KEY)

    def test_zero_max_age_disables_check(self):
        _check_auth_recency(None, 0, AuthMethod.AUTH0)


# ---------------------------------------------------------------------------
# _extract_auth_time
# ---------------------------------------------------------------------------


class TestExtractAuthTime:
    """Extracts auth_time from JWT claims in the Authorization header."""

    @patch("airweave.api.deps.settings")
    def test_valid_jwt_with_auth_time(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"
        now = int(time.time())

        request = MagicMock()
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"https://airweave.ai/auth_time": now}).encode()
        ).rstrip(b"=")
        token = f"{header.decode()}.{payload.decode()}."
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result == now

    @patch("airweave.api.deps.settings")
    def test_jwt_without_auth_time_returns_none(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        request = MagicMock()
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "user123"}).encode()).rstrip(b"=")
        token = f"{header.decode()}.{payload.decode()}."
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result is None

    @patch("airweave.api.deps.settings")
    def test_no_authorization_header_returns_none(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"
        request = MagicMock()
        request.headers = {}

        result = _extract_auth_time(request)
        assert result is None

    @patch("airweave.api.deps.settings")
    def test_non_bearer_header_returns_none(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"
        request = MagicMock()
        request.headers = {"authorization": "Basic abc123"}

        result = _extract_auth_time(request)
        assert result is None

    @patch("airweave.api.deps.settings")
    def test_float_value_truncated_to_int(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"
        now = int(time.time())

        request = MagicMock()
        token = _make_jwt({"https://airweave.ai/auth_time": float(now) + 0.7})
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result == now

    @patch("airweave.api.deps.time")
    @patch("airweave.api.deps.settings")
    def test_future_timestamp_rejected(self, mock_settings, mock_time):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"
        mock_time.time.return_value = 1000.0

        request = MagicMock()
        token = _make_jwt({"https://airweave.ai/auth_time": 1200})  # 200s in future
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result is None

    @patch("airweave.api.deps.settings")
    def test_negative_value_rejected(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        request = MagicMock()
        token = _make_jwt({"https://airweave.ai/auth_time": -100})
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result is None

    @patch("airweave.api.deps.settings")
    def test_string_value_returns_none(self, mock_settings):
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        request = MagicMock()
        token = _make_jwt({"https://airweave.ai/auth_time": "not_a_number"})
        request.headers = {"authorization": f"Bearer {token}"}

        result = _extract_auth_time(request)
        assert result is None


# ---------------------------------------------------------------------------
# _extract_claims
# ---------------------------------------------------------------------------


class TestExtractClaims:
    """Direct tests for _extract_claims helper."""

    def test_valid_jwt_returns_claims(self):
        request = MagicMock()
        token = _make_jwt({"sub": "user123", "iss": "https://example.com"})
        request.headers = {"authorization": f"Bearer {token}"}

        claims = _extract_claims(request)
        assert claims is not None
        assert claims["sub"] == "user123"

    def test_malformed_jwt_returns_none(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer not.a.valid.jwt"}

        result = _extract_claims(request)
        assert result is None

    def test_empty_bearer_returns_none(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer "}

        result = _extract_claims(request)
        assert result is None


# ---------------------------------------------------------------------------
# ReauthenticationRequiredException
# ---------------------------------------------------------------------------


class TestReauthenticationRequiredException:
    def test_default_message(self):
        exc = ReauthenticationRequiredException(max_age=300)
        assert exc.max_age == 300
        assert "300" in exc.message

    def test_custom_message(self):
        exc = ReauthenticationRequiredException(max_age=60, message="custom")
        assert exc.message == "custom"
        assert exc.max_age == 60


# ---------------------------------------------------------------------------
# require_org_role integration (with recent_auth_seconds)
# ---------------------------------------------------------------------------


def _make_jwt(claims: dict) -> str:
    """Build a minimal unsigned JWT for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}."


def _mock_request(auth_time: int | None = None) -> MagicMock:
    """Build a mock Request with optional auth_time in a JWT Bearer header."""
    request = MagicMock()
    if auth_time is not None:
        token = _make_jwt({"https://airweave.ai/auth_time": auth_time})
        request.headers = {"authorization": f"Bearer {token}"}
    else:
        request.headers = {}
    return request


def _mock_ctx(
    auth_method: AuthMethod = AuthMethod.AUTH0,
    role: str = "owner",
) -> MagicMock:
    """Build a mock ApiContext with the given auth method and role."""
    from uuid import uuid4

    ctx = MagicMock()
    ctx.auth_method = auth_method
    ctx.is_api_key_auth = auth_method == AuthMethod.API_KEY
    ctx.user = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.user.organization_roles = {ctx.organization.id: role}
    ctx.logger = MagicMock()
    ctx.logger.with_context.return_value = MagicMock()
    return ctx


class TestRequireOrgRoleWithRecency:
    """Integration tests for the _enforce closure inside require_org_role."""

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_fresh_auth_passes(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, recent_auth_seconds=300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=800)

        result = await _enforce(request=request, ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_stale_auth_raises(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, recent_auth_seconds=300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=100)

        with pytest.raises(ReauthenticationRequiredException):
            await _enforce(request=request, ctx=ctx)

    @pytest.mark.asyncio
    async def test_api_key_auth_rejected(self):
        from fastapi import HTTPException

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, recent_auth_seconds=300)
        _enforce = dep.dependency

        ctx = _mock_ctx(auth_method=AuthMethod.API_KEY)
        request = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await _enforce(request=request, ctx=ctx)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_none_recent_auth_skips_check(self):
        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request()  # No auth_time in JWT

        result = await _enforce(request=request, ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_system_auth_skips_all_checks(self):
        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, recent_auth_seconds=300)
        _enforce = dep.dependency

        ctx = _mock_ctx(auth_method=AuthMethod.SYSTEM)
        request = _mock_request()

        result = await _enforce(request=request, ctx=ctx)
        assert result is ctx


class TestRequireRecentAuth:
    """Integration tests for the _enforce closure inside require_recent_auth."""

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_fresh_auth_returns_ctx(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_recent_auth

        dep = require_recent_auth(300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=800)

        result = await _enforce(request=request, ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_stale_auth_raises(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_recent_auth

        dep = require_recent_auth(300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=100)

        with pytest.raises(ReauthenticationRequiredException):
            await _enforce(request=request, ctx=ctx)

    @pytest.mark.asyncio
    async def test_api_key_rejected(self):
        from fastapi import HTTPException

        from airweave.api.deps import require_recent_auth

        dep = require_recent_auth(300)
        _enforce = dep.dependency

        ctx = _mock_ctx(auth_method=AuthMethod.API_KEY)
        request = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await _enforce(request=request, ctx=ctx)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_stale_auth_emits_audit_log(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_recent_auth

        dep = require_recent_auth(300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=100)

        with pytest.raises(ReauthenticationRequiredException):
            await _enforce(request=request, ctx=ctx)

        ctx.logger.with_context.assert_called_with(event_type="reauth_challenge")
        ctx.logger.with_context.return_value.info.assert_called_once()


# ---------------------------------------------------------------------------
# require_org_role: role / user checks (without recency)
# ---------------------------------------------------------------------------


class TestRequireOrgRoleBaseChecks:
    """Verify role check and user-is-None behavior in require_org_role."""

    @pytest.mark.asyncio
    async def test_insufficient_role_raises_403(self):
        from fastapi import HTTPException

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: role == "owner", recent_auth_seconds=None)
        _enforce = dep.dependency

        ctx = _mock_ctx(role="member")
        request = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await _enforce(request=request, ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_none_raises_403(self):
        from fastapi import HTTPException

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        ctx.user = None
        request = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await _enforce(request=request, ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "user authentication" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("airweave.api.deps.settings")
    @patch("airweave.api.deps.time")
    async def test_stale_auth_emits_audit_log(self, mock_time, mock_settings):
        mock_time.time.return_value = 1000.0
        mock_settings.AUTH0_AUTH_TIME_CLAIM_KEY = "https://airweave.ai/auth_time"

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, recent_auth_seconds=300)
        _enforce = dep.dependency

        ctx = _mock_ctx()
        request = _mock_request(auth_time=100)

        with pytest.raises(ReauthenticationRequiredException):
            await _enforce(request=request, ctx=ctx)

        ctx.logger.with_context.assert_called_with(event_type="reauth_challenge")
        ctx.logger.with_context.return_value.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_block_api_key_auth_without_recency(self):
        from fastapi import HTTPException

        from airweave.api.deps import require_org_role

        dep = require_org_role(lambda role: True, block_api_key_auth=True)
        _enforce = dep.dependency

        ctx = _mock_ctx(auth_method=AuthMethod.API_KEY)
        request = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await _enforce(request=request, ctx=ctx)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# reauth_required_exception_handler
# ---------------------------------------------------------------------------


class TestReauthRequiredExceptionHandler:
    """Test the middleware exception handler returns structured 403."""

    @pytest.mark.asyncio
    async def test_returns_structured_403(self):
        from airweave.api.middleware import reauth_required_exception_handler

        exc = ReauthenticationRequiredException(max_age=300)
        request = MagicMock()

        response = await reauth_required_exception_handler(request, exc)

        assert response.status_code == 403
        body = json.loads(response.body)
        assert body["error"] == "reauthentication_required"
        assert body["max_age"] == 300
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_custom_message_in_detail(self):
        from airweave.api.middleware import reauth_required_exception_handler

        exc = ReauthenticationRequiredException(max_age=60, message="Please re-login")
        request = MagicMock()

        response = await reauth_required_exception_handler(request, exc)

        body = json.loads(response.body)
        assert body["detail"] == "Please re-login"
        assert body["max_age"] == 60
