"""Unit tests for Svix adapter helper functions.

Tests pure functions (_generate_token, _raise_from_exception,
_is_transient_error, type converters) without needing a live Svix
server.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import jwt
import pytest

from airweave.adapters.webhooks.svix import (
    SVIX_ORG_ID,
    TOKEN_DURATION_SECONDS,
    _generate_token,
    _is_transient_error,
    _raise_from_exception,
    _to_attempt,
    _to_message,
    _to_subscription,
)
from airweave.domains.webhooks.types import WebhooksError

NOW = datetime(2024, 3, 15, 9, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# _generate_token
# ---------------------------------------------------------------------------


class TestGenerateToken:
    """Tests for _generate_token."""

    def test_returns_decodable_jwt(self):
        secret = "test-secret-key-that-is-at-least-32-bytes!"
        token = _generate_token(secret)
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        assert payload["iss"] == "svix-server"
        assert payload["sub"] == SVIX_ORG_ID
        assert "iat" in payload
        assert "exp" in payload
        assert "nbf" in payload

    def test_expiry_is_far_future(self):
        secret = "test-secret-key-that-is-at-least-32-bytes!"
        token = _generate_token(secret)
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        duration = payload["exp"] - payload["iat"]
        assert duration == TOKEN_DURATION_SECONDS

    def test_different_secrets_produce_different_tokens(self):
        t1 = _generate_token("secret-a-padding-to-reach-32-bytes!")
        t2 = _generate_token("secret-b-padding-to-reach-32-bytes!")
        assert t1 != t2


# ---------------------------------------------------------------------------
# _raise_from_exception
# ---------------------------------------------------------------------------


def _make_svix_http_error(code: str, detail: str, status_code: int):
    """Create a mock SvixHttpError."""
    from svix.exceptions import HttpError as SvixHttpError

    err = SvixHttpError.__new__(SvixHttpError)
    err.code = code
    err.detail = detail
    err.status_code = status_code
    err.args = (detail,)
    return err


def _make_svix_validation_error(messages: list[str] | None):
    """Create a mock SvixValidationError."""
    from svix.exceptions import HTTPValidationError as SvixValidationError

    err = SvixValidationError.__new__(SvixValidationError)
    if messages is not None:
        err.detail = [MagicMock(msg=m) for m in messages]
    else:
        err.detail = None
    err.args = ("validation error",)
    return err


class TestRaiseFromException:
    """Tests for _raise_from_exception."""

    def test_not_found_maps_to_404(self):
        exc = _make_svix_http_error("not_found", "Endpoint not found", 404)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 404
        assert "Endpoint not found" in exc_info.value.message

    def test_validation_error_code_maps_to_422(self):
        exc = _make_svix_http_error("validation", "Invalid URL", 422)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 422

    def test_validation_error_code_variant(self):
        exc = _make_svix_http_error("validation_error", "Bad field", 422)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 422

    def test_other_svix_error_preserves_status(self):
        exc = _make_svix_http_error("rate_limited", "Too many requests", 429)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 429

    def test_svix_error_with_no_status_defaults_to_500(self):
        exc = _make_svix_http_error("unknown", "Something failed", None)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 500

    def test_svix_validation_error_maps_to_422(self):
        exc = _make_svix_validation_error(["Field A is required", "Field B invalid"])
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 422
        assert "Field A is required" in exc_info.value.message
        assert "Field B invalid" in exc_info.value.message

    def test_svix_validation_error_no_detail(self):
        exc = _make_svix_validation_error(None)
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 422
        assert "Validation error" in exc_info.value.message

    def test_generic_exception_maps_to_500(self):
        exc = RuntimeError("unexpected failure")
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc)
        assert exc_info.value.status_code == 500
        assert "unexpected failure" in exc_info.value.message

    def test_context_prefix_included(self):
        exc = RuntimeError("boom")
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc, context="Failed to create subscription")
        assert exc_info.value.message.startswith("Failed to create subscription: ")

    def test_empty_context_no_prefix(self):
        exc = RuntimeError("boom")
        with pytest.raises(WebhooksError) as exc_info:
            _raise_from_exception(exc, context="")
        assert not exc_info.value.message.startswith(": ")


# ---------------------------------------------------------------------------
# _is_transient_error
# ---------------------------------------------------------------------------


class TestIsTransientError:
    """Tests for _is_transient_error."""

    def test_connection_error_is_transient(self):
        assert _is_transient_error(ConnectionError("refused")) is True

    def test_os_error_is_transient(self):
        assert _is_transient_error(OSError("network unreachable")) is True

    def test_timeout_error_is_transient(self):
        assert _is_transient_error(TimeoutError("timed out")) is True

    def test_svix_5xx_is_transient(self):
        exc = _make_svix_http_error("internal_error", "Internal", 500)
        assert _is_transient_error(exc) is True

    def test_svix_502_is_transient(self):
        exc = _make_svix_http_error("bad_gateway", "Bad Gateway", 502)
        assert _is_transient_error(exc) is True

    def test_svix_503_is_transient(self):
        exc = _make_svix_http_error("unavailable", "Service Unavailable", 503)
        assert _is_transient_error(exc) is True

    def test_svix_400_is_not_transient(self):
        exc = _make_svix_http_error("validation", "Bad Request", 400)
        assert _is_transient_error(exc) is False

    def test_svix_404_is_not_transient(self):
        exc = _make_svix_http_error("not_found", "Not Found", 404)
        assert _is_transient_error(exc) is False

    def test_svix_422_is_not_transient(self):
        exc = _make_svix_http_error("validation_error", "Invalid", 422)
        assert _is_transient_error(exc) is False

    def test_svix_none_status_is_not_transient(self):
        exc = _make_svix_http_error("unknown", "Unknown", None)
        assert _is_transient_error(exc) is False

    def test_generic_exception_is_not_transient(self):
        assert _is_transient_error(RuntimeError("boom")) is False

    def test_value_error_is_not_transient(self):
        assert _is_transient_error(ValueError("bad value")) is False


# ---------------------------------------------------------------------------
# Type converters: Svix SDK -> Domain types
# ---------------------------------------------------------------------------


def _mock_endpoint_out(**overrides) -> MagicMock:
    """Create a mock EndpointOut."""
    defaults = {
        "id": "ep_123",
        "url": "https://example.com/hook",
        "channels": ["sync.completed", "sync.failed"],
        "disabled": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def _mock_message_out(**overrides) -> MagicMock:
    """Create a mock MessageOut."""
    defaults = {
        "id": "msg_456",
        "event_type": "sync.completed",
        "payload": {"status": "completed"},
        "timestamp": NOW,
        "channels": ["sync.completed"],
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def _mock_attempt_out(**overrides) -> MagicMock:
    """Create a mock MessageAttemptOut."""
    defaults = {
        "id": "atmpt_789",
        "msg_id": "msg_456",
        "endpoint_id": "ep_123",
        "timestamp": NOW,
        "response_status_code": 200,
        "response": '{"ok": true}',
        "url": "https://example.com/hook",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


class TestToSubscription:
    """Tests for _to_subscription."""

    def test_maps_all_fields(self):
        endpoint = _mock_endpoint_out()
        sub = _to_subscription(endpoint)

        assert sub.id == "ep_123"
        assert sub.url == "https://example.com/hook"
        assert sub.event_types == ["sync.completed", "sync.failed"]
        assert sub.disabled is False
        assert sub.created_at == NOW
        assert sub.updated_at == NOW

    def test_none_channels_becomes_empty_list(self):
        endpoint = _mock_endpoint_out(channels=None)
        sub = _to_subscription(endpoint)
        assert sub.event_types == []

    def test_disabled_endpoint(self):
        endpoint = _mock_endpoint_out(disabled=True)
        sub = _to_subscription(endpoint)
        assert sub.disabled is True


class TestToMessage:
    """Tests for _to_message."""

    def test_maps_all_fields(self):
        msg_out = _mock_message_out()
        msg = _to_message(msg_out)

        assert msg.id == "msg_456"
        assert msg.event_type == "sync.completed"
        assert msg.payload == {"status": "completed"}
        assert msg.timestamp == NOW
        assert msg.channels == ["sync.completed"]

    def test_none_channels_becomes_empty_list(self):
        msg_out = _mock_message_out(channels=None)
        msg = _to_message(msg_out)
        assert msg.channels == []


class TestToAttempt:
    """Tests for _to_attempt."""

    def test_maps_all_fields(self):
        attempt_out = _mock_attempt_out()
        attempt = _to_attempt(attempt_out)

        assert attempt.id == "atmpt_789"
        assert attempt.message_id == "msg_456"
        assert attempt.endpoint_id == "ep_123"
        assert attempt.timestamp == NOW
        assert attempt.response_status_code == 200
        assert attempt.response == '{"ok": true}'
        assert attempt.url == "https://example.com/hook"

    def test_maps_msg_id_to_message_id(self):
        """Svix uses msg_id, domain uses message_id."""
        attempt_out = _mock_attempt_out(msg_id="custom_msg_id")
        attempt = _to_attempt(attempt_out)
        assert attempt.message_id == "custom_msg_id"

    def test_failed_attempt_status_code(self):
        attempt_out = _mock_attempt_out(response_status_code=500)
        attempt = _to_attempt(attempt_out)
        assert attempt.response_status_code == 500
