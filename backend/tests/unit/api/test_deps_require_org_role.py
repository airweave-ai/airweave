"""Unit tests for require_org_role — direct calls to the inner _enforce closure.

These bypass the ASGI transport so coverage instrumentation traces every branch
inside deps.py.  Integration-level tests in test_role_gating.py cover the same
logic end-to-end but the coverage tool loses visibility through httpx/ASGI.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.api.deps import require_org_role
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.organizations import logic
from airweave.schemas.organization import Organization
from airweave.schemas.user import User, UserOrganization

TEST_ORG_ID = uuid4()
TEST_USER_ID = uuid4()


def _org() -> Organization:
    now = datetime.now(timezone.utc)
    return Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )


def _ctx_with_role(
    role: str,
    auth_method: AuthMethod = AuthMethod.AUTH0,
) -> ApiContext:
    org = _org()
    if auth_method == AuthMethod.API_KEY:
        return ApiContext(
            request_id="unit-test",
            organization=org,
            auth_method=auth_method,
            user=None,
            logger=logger.with_context(request_id="unit-test"),
        )
    user = User(
        id=TEST_USER_ID,
        email="testuser@example.com",
        full_name="Test User",
        user_organizations=[
            UserOrganization(
                user_id=TEST_USER_ID,
                organization_id=TEST_ORG_ID,
                organization=org,
                role=role,
                is_primary=True,
            ),
        ],
    )
    return ApiContext(
        request_id="unit-test",
        organization=org,
        auth_method=auth_method,
        user=user,
        logger=logger.with_context(request_id="unit-test"),
    )


def _wrong_org_ctx() -> ApiContext:
    org = _org()
    other_org_id = uuid4()
    now = datetime.now(timezone.utc)
    other_org = Organization(
        id=other_org_id,
        name="Other Organization",
        created_at=now,
        modified_at=now,
    )
    user = User(
        id=TEST_USER_ID,
        email="testuser@example.com",
        full_name="Test User",
        user_organizations=[
            UserOrganization(
                user_id=TEST_USER_ID,
                organization_id=other_org_id,
                organization=other_org,
                role="owner",
                is_primary=True,
            ),
        ],
    )
    return ApiContext(
        request_id="unit-test",
        organization=org,
        auth_method=AuthMethod.AUTH0,
        user=user,
        logger=logger.with_context(request_id="unit-test"),
    )


def _system_ctx(method: AuthMethod = AuthMethod.SYSTEM) -> ApiContext:
    return ApiContext(
        request_id="unit-test",
        organization=_org(),
        auth_method=method,
        user=None,
        logger=logger.with_context(request_id="unit-test"),
    )


def _dummy_request() -> MagicMock:
    """Build a mock Request with no Authorization header (no reauth claims)."""
    request = MagicMock()
    request.headers = {}
    return request


def _get_enforce(check, *, block_api_key_auth=False):
    """Extract the inner _enforce closure from require_org_role's Depends."""
    dep = require_org_role(check, block_api_key_auth=block_api_key_auth)
    return dep.dependency


class TestRequireOrgRoleBranches:
    """Exercises every branch inside the _enforce closure."""

    @pytest.mark.asyncio
    async def test_api_key_auth_blocked(self):
        enforce = _get_enforce(logic.can_manage_api_keys, block_api_key_auth=True)
        ctx = _ctx_with_role("", auth_method=AuthMethod.API_KEY)
        with pytest.raises(HTTPException) as exc_info:
            await enforce(request=_dummy_request(), ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "API key authentication is not permitted" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_system_auth_bypasses(self):
        enforce = _get_enforce(logic.can_manage_api_keys, block_api_key_auth=True)
        ctx = _system_ctx(AuthMethod.SYSTEM)
        result = await enforce(request=_dummy_request(), ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_internal_system_auth_bypasses(self):
        enforce = _get_enforce(logic.can_manage_api_keys)
        ctx = _system_ctx(AuthMethod.INTERNAL_SYSTEM)
        result = await enforce(request=_dummy_request(), ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_no_user_rejected(self):
        """AUTH0 context with user=None (edge case) raises 403."""
        ctx = ApiContext(
            request_id="unit-test",
            organization=_org(),
            auth_method=AuthMethod.AUTH0,
            user=None,
            logger=logger.with_context(request_id="unit-test"),
        )
        enforce = _get_enforce(logic.can_manage_api_keys)
        with pytest.raises(HTTPException) as exc_info:
            await enforce(request=_dummy_request(), ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "requires user authentication" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_in_org_rejected(self):
        enforce = _get_enforce(logic.can_manage_api_keys)
        ctx = _wrong_org_ctx()
        with pytest.raises(HTTPException) as exc_info:
            await enforce(request=_dummy_request(), ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_role_fails_predicate_rejected(self):
        enforce = _get_enforce(logic.can_manage_api_keys)
        ctx = _ctx_with_role("member")
        with pytest.raises(HTTPException) as exc_info:
            await enforce(request=_dummy_request(), ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["admin", "owner"])
    async def test_privileged_role_passes(self, role):
        enforce = _get_enforce(logic.can_manage_api_keys)
        ctx = _ctx_with_role(role)
        result = await enforce(request=_dummy_request(), ctx=ctx)
        assert result is ctx
