"""Tests for http_helpers — HTTP response → domain exception translation."""

import httpx
import pytest

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceError,
    SourceRateLimitError,
    SourceServerError,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.platform.sources.http_helpers import raise_for_status

_SN = "test_source"
_TPK = AuthProviderKind.OAUTH


def _response(status: int, body: str = "", headers: dict | None = None) -> httpx.Response:
    """Build a fake httpx.Response for testing."""
    return httpx.Response(
        status_code=status,
        text=body,
        headers=headers or {},
        request=httpx.Request("GET", "https://api.example.com/test"),
    )


def _raise(status: int, body: str = "", headers: dict | None = None, **kwargs):
    """Call raise_for_status with default source_short_name and token_provider_kind."""
    raise_for_status(
        _response(status, body, headers),
        source_short_name=kwargs.get("source_short_name", _SN),
        token_provider_kind=kwargs.get("token_provider_kind", _TPK),
        context=kwargs.get("context", ""),
        entity_id=kwargs.get("entity_id", ""),
    )


class TestRaiseForStatus:
    """Tests for raise_for_status()."""

    def test_2xx_does_not_raise(self):
        _raise(200)
        _raise(201)
        _raise(204)

    def test_401_raises_source_auth_error(self):
        with pytest.raises(SourceAuthError, match="401") as exc_info:
            _raise(401)
        assert exc_info.value.status_code == 401
        assert exc_info.value.token_provider_kind == AuthProviderKind.OAUTH

    def test_403_raises_entity_forbidden(self):
        with pytest.raises(SourceEntityForbiddenError, match="403"):
            _raise(403)

    def test_404_raises_entity_not_found(self):
        with pytest.raises(SourceEntityNotFoundError, match="404"):
            _raise(404)

    def test_429_raises_rate_limit_error(self):
        with pytest.raises(SourceRateLimitError) as exc_info:
            _raise(429, headers={"Retry-After": "15"})
        assert exc_info.value.retry_after == 15.0

    def test_429_default_retry_after(self):
        with pytest.raises(SourceRateLimitError) as exc_info:
            _raise(429)
        assert exc_info.value.retry_after == 30.0

    def test_500_raises_server_error(self):
        with pytest.raises(SourceServerError) as exc_info:
            _raise(500)
        assert exc_info.value.status_code == 500

    def test_502_raises_server_error(self):
        with pytest.raises(SourceServerError) as exc_info:
            _raise(502)
        assert exc_info.value.status_code == 502

    def test_301_raises_source_error(self):
        with pytest.raises(SourceError, match="redirect"):
            _raise(301, headers={"Location": "https://new.example.com"})

    def test_400_generic_raises_source_error(self):
        with pytest.raises(SourceError, match="400"):
            _raise(400, body="bad request")

    def test_400_zoho_rate_limit_disguised(self):
        body = '{"error_description": "You have made too many requests", "error": "Access Denied"}'
        with pytest.raises(SourceRateLimitError, match="disguised"):
            _raise(400, body=body)

    def test_source_short_name_propagated(self):
        with pytest.raises(SourceAuthError) as exc_info:
            _raise(401, source_short_name="asana")
        assert exc_info.value.source_short_name == "asana"

    def test_context_in_message(self):
        with pytest.raises(SourceAuthError, match="fetching projects"):
            _raise(401, context="fetching projects")

    def test_entity_id_in_message(self):
        with pytest.raises(SourceEntityForbiddenError, match="entity item-42"):
            _raise(403, entity_id="item-42")

    def test_403_is_entity_error_not_auth_error(self):
        with pytest.raises(SourceEntityForbiddenError) as exc_info:
            _raise(403)
        assert not isinstance(exc_info.value, SourceAuthError)

    def test_404_is_entity_error_not_auth_error(self):
        with pytest.raises(SourceEntityNotFoundError) as exc_info:
            _raise(404)
        assert not isinstance(exc_info.value, SourceAuthError)
