"""Tests for ContextResolver — the pure/testable methods.

The resolver's main ``resolve()`` method touches the DB via crud,
so it requires integration tests. These tests focus on the pure logic
that can be tested without a database:
- Organization ID resolution from AuthResult
- Billing plan extraction from ApiContext
- Client IP extraction
- Header extraction
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.api.context_resolver import (
    AuthResult,
    ContextResolver,
    _extract_client_ip,
    _extract_headers,
)
from airweave.adapters.cache.fake import FakeContextCache
from airweave.adapters.rate_limiter.fake import FakeRateLimiter
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.schemas.organization import Organization

ORG_ID = uuid4()


def _make_resolver():
    return ContextResolver(
        cache=FakeContextCache(),
        rate_limiter=FakeRateLimiter(),
        user_repo=MagicMock(),
        api_key_repo=MagicMock(),
        org_repo=MagicMock(),
    )


def _make_org(org_id=ORG_ID, billing=None):
    now = datetime.now(timezone.utc)
    return Organization(
        id=org_id, name="Test Org", created_at=now, modified_at=now, billing=billing,
    )


def _make_user_with_orgs(org_ids: list):
    """Build a minimal schemas.User-like object with user_organizations."""
    orgs = []
    for oid in org_ids:
        org_obj = SimpleNamespace(id=oid)
        orgs.append(SimpleNamespace(organization=org_obj))

    return SimpleNamespace(
        id=uuid4(),
        email="user@test.com",
        primary_organization_id=org_ids[0] if org_ids else None,
        user_organizations=orgs,
    )


# ---------------------------------------------------------------------------
# _resolve_organization_id
# ---------------------------------------------------------------------------


class TestResolveOrganizationId:
    def test_explicit_header_wins(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.AUTH0, user=_make_user_with_orgs([ORG_ID]))
        result = resolver._resolve_organization_id(str(uuid4()), auth)
        assert result != str(ORG_ID)

    def test_auth0_falls_back_to_primary_org(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.AUTH0, user=_make_user_with_orgs([ORG_ID]))
        result = resolver._resolve_organization_id(None, auth)
        assert result == str(ORG_ID)

    def test_system_falls_back_to_primary_org(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.SYSTEM, user=_make_user_with_orgs([ORG_ID]))
        result = resolver._resolve_organization_id(None, auth)
        assert result == str(ORG_ID)

    def test_api_key_uses_resolved_org_id(self):
        resolver = _make_resolver()
        api_key_org = str(uuid4())
        auth = AuthResult(method=AuthMethod.API_KEY, api_key_org_id=api_key_org)
        result = resolver._resolve_organization_id(None, auth)
        assert result == api_key_org

    def test_no_org_raises_400(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.AUTH0, user=_make_user_with_orgs([]))
        # user has no primary_organization_id (empty orgs list)
        auth.user.primary_organization_id = None
        with pytest.raises(HTTPException) as exc_info:
            resolver._resolve_organization_id(None, auth)
        assert exc_info.value.status_code == 400

    def test_api_key_without_org_id_raises_400(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.API_KEY, api_key_org_id=None)
        with pytest.raises(HTTPException) as exc_info:
            resolver._resolve_organization_id(None, auth)
        assert exc_info.value.status_code == 400

    def test_no_auth_user_no_api_key_raises_400(self):
        resolver = _make_resolver()
        auth = AuthResult(method=AuthMethod.AUTH0, user=None)
        with pytest.raises(HTTPException) as exc_info:
            resolver._resolve_organization_id(None, auth)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# _extract_client_ip
# ---------------------------------------------------------------------------


class TestExtractClientIp:
    def test_x_forwarded_for_single(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        assert _extract_client_ip(request) == "1.2.3.4"

    def test_x_forwarded_for_chain_takes_first(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        assert _extract_client_ip(request) == "1.2.3.4"

    def test_x_forwarded_for_strips_whitespace(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "  1.2.3.4  "}
        assert _extract_client_ip(request) == "1.2.3.4"

    def test_falls_back_to_client_host(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert _extract_client_ip(request) == "10.0.0.1"

    def test_no_client_returns_unknown(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _extract_client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# _extract_headers
# ---------------------------------------------------------------------------


class TestExtractHeaders:
    def test_extracts_standard_headers(self):
        request = MagicMock()
        request.headers = {
            "user-agent": "TestAgent/1.0",
            "x-client-name": "web",
            "x-airweave-session-id": "sess-123",
        }
        request.state.request_id = "req-abc"

        headers = _extract_headers(request)
        assert headers.user_agent == "TestAgent/1.0"
        assert headers.client_name == "web"
        assert headers.session_id == "sess-123"
        assert headers.request_id == "req-abc"

    def test_missing_headers_are_none(self):
        request = MagicMock()
        request.headers = {}
        request.state.request_id = "req-abc"

        headers = _extract_headers(request)
        assert headers.user_agent is None
        assert headers.sdk_name is None

    def test_fern_sdk_fallback(self):
        """x-sdk-name takes priority, x-fern-sdk-name is fallback."""
        request = MagicMock()
        request.headers = {"x-fern-sdk-name": "fern-python"}
        request.state.request_id = "req-abc"

        headers = _extract_headers(request)
        assert headers.sdk_name == "fern-python"

    def test_sdk_name_priority_over_fern(self):
        request = MagicMock()
        request.headers = {"x-sdk-name": "airweave-py", "x-fern-sdk-name": "fern-python"}
        request.state.request_id = "req-abc"

        headers = _extract_headers(request)
        assert headers.sdk_name == "airweave-py"


# ---------------------------------------------------------------------------
# AuthResult dataclass
# ---------------------------------------------------------------------------


class TestAuthResult:
    def test_defaults(self):
        r = AuthResult()
        assert r.user is None
        assert r.method == AuthMethod.SYSTEM
        assert r.metadata == {}
        assert r.api_key_org_id is None

    def test_api_key_result(self):
        r = AuthResult(
            method=AuthMethod.API_KEY,
            api_key_org_id="org-123",
            metadata={"api_key_id": "key-1"},
        )
        assert r.method == AuthMethod.API_KEY
        assert r.api_key_org_id == "org-123"

    def test_metadata_independent_per_instance(self):
        """Default dict must not be shared across instances."""
        a = AuthResult()
        b = AuthResult()
        a.metadata["x"] = 1
        assert "x" not in b.metadata
