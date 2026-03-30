"""Integration tests for role-based HTTP method authorization (CASA-13/32).

Verifies that:
- Members are rejected from privileged API key and auth provider operations.
- Admins/owners are permitted.
- API key auth is explicitly blocked for API key management endpoints.
- System auth bypasses role checks (existing test fixtures keep working).
- Operational endpoints remain open to all roles (no regression).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


from airweave.api.context import ApiContext
from airweave.api.deps import get_container, get_context
from airweave.db.session import get_db
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, FeatureFlag
from airweave.schemas.organization import Organization
from airweave.schemas.user import User, UserOrganization

TEST_ORG_ID = uuid4()
TEST_USER_ID = uuid4()
TEST_REQUEST_ID = "test-role-gating-000"


OTHER_ORG_ID = uuid4()


def _make_fake_api_key_obj() -> MagicMock:
    """Build a minimal mock API key for CRUD return values."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    key = MagicMock()
    key.id = uuid4()
    key.organization_id = TEST_ORG_ID
    key.created_at = now
    key.modified_at = now
    key.last_used_date = None
    key.expiration_date = now + timedelta(days=90)
    key.created_by_email = "testuser@example.com"
    key.modified_by_email = "testuser@example.com"
    key.encrypted_key = b"encrypted"
    return key


def _make_fake_rate_limit() -> MagicMock:
    """Build a minimal mock SourceRateLimit for CRUD return values."""
    now = datetime.now(timezone.utc)
    obj = MagicMock()
    obj.id = uuid4()
    obj.organization_id = TEST_ORG_ID
    obj.source_short_name = "some-source"
    obj.limit = 100
    obj.window_seconds = 60
    obj.created_at = now
    obj.modified_at = now
    return obj


def _make_fake_auth_provider_connection():
    """Build a minimal AuthProviderConnection for service return values."""
    from airweave.schemas.auth_provider import AuthProviderConnection

    now = datetime.now(timezone.utc)
    return AuthProviderConnection(
        id=uuid4(),
        name="Test Connection",
        readable_id="some-provider",
        short_name="test",
        description=None,
        created_by_email="testuser@example.com",
        modified_by_email="testuser@example.com",
        created_at=now,
        modified_at=now,
        masked_client_id=None,
    )


def _make_fake_context_with_role(
    role: str,
    auth_method: AuthMethod = AuthMethod.AUTH0,
    enabled_features: list[FeatureFlag] | None = None,
) -> ApiContext:
    """Build an ApiContext carrying a user with the given org role."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
        enabled_features=enabled_features or [],
    )

    if auth_method == AuthMethod.API_KEY:
        # API key auth has no user
        return ApiContext(
            request_id=TEST_REQUEST_ID,
            organization=org,
            auth_method=auth_method,
            user=None,
            logger=logger.with_context(request_id=TEST_REQUEST_ID),
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
        request_id=TEST_REQUEST_ID,
        organization=org,
        auth_method=auth_method,
        user=user,
        logger=logger.with_context(request_id=TEST_REQUEST_ID),
    )


def _make_system_context() -> ApiContext:
    """Build a system-auth context (no user, bypasses role checks)."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )
    return ApiContext(
        request_id=TEST_REQUEST_ID,
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        user=None,
        logger=logger.with_context(request_id=TEST_REQUEST_ID),
    )


def _make_internal_system_context() -> ApiContext:
    """Build an INTERNAL_SYSTEM auth context (bypasses role checks)."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )
    return ApiContext(
        request_id=TEST_REQUEST_ID,
        organization=org,
        auth_method=AuthMethod.INTERNAL_SYSTEM,
        user=None,
        logger=logger.with_context(request_id=TEST_REQUEST_ID),
    )


def _make_wrong_org_context() -> ApiContext:
    """Build a context where the user belongs to a *different* org."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )
    other_org = Organization(
        id=OTHER_ORG_ID,
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
                organization_id=OTHER_ORG_ID,
                organization=other_org,
                role="owner",
                is_primary=True,
            ),
        ],
    )
    return ApiContext(
        request_id=TEST_REQUEST_ID,
        organization=org,
        auth_method=AuthMethod.AUTH0,
        user=user,
        logger=logger.with_context(request_id=TEST_REQUEST_ID),
    )


@pytest_asyncio.fixture
async def _role_client(test_container):
    """Yield a factory that creates an HTTP client with a specific role context."""
    from airweave.core import container as container_mod
    from airweave.main import app

    async def _fake_db():
        yield None

    async def _build(ctx: ApiContext) -> AsyncClient:
        app.dependency_overrides[get_container] = lambda: test_container
        app.dependency_overrides[get_context] = lambda: ctx
        app.dependency_overrides[get_db] = _fake_db
        prev_container = container_mod.container
        container_mod.container = test_container
        app.state.http_metrics = test_container.metrics.http
        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://test")
        client._prev_container = prev_container  # stash for cleanup
        return client

    clients: list[AsyncClient] = []
    original_build = _build

    async def tracked_build(ctx: ApiContext) -> AsyncClient:
        c = await original_build(ctx)
        clients.append(c)
        return c

    yield tracked_build

    for c in clients:
        await c.aclose()

    from airweave.core import container as container_mod
    from airweave.main import app

    app.dependency_overrides.clear()
    if clients:
        container_mod.container = clients[0]._prev_container


# ---------------------------------------------------------------------------
# API key endpoint tests (CASA-32)
# ---------------------------------------------------------------------------


class TestApiKeyRoleGating:
    """API key endpoints require owner/admin and block API key auth."""

    @pytest.mark.asyncio
    async def test_member_create_api_key_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post("/api-keys/", json={})
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_create_api_key_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with (
            patch("airweave.crud.api_key.create", new_callable=AsyncMock, return_value=_make_fake_api_key_obj()),
            patch("airweave.core.credentials.decrypt", return_value={"key": "ak_test1234"}),
        ):
            response = await client.post("/api-keys/", json={})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_delete_api_key_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("owner")
        client = await _role_client(ctx)
        fake_id = str(uuid4())
        with (
            patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=_make_fake_api_key_obj()),
            patch("airweave.core.credentials.decrypt", return_value={"key": "ak_test1234"}),
            patch("airweave.crud.api_key.remove", new_callable=AsyncMock),
        ):
            response = await client.delete(f"/api-keys/?id={fake_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_create_api_key_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("owner")
        client = await _role_client(ctx)
        with (
            patch("airweave.crud.api_key.create", new_callable=AsyncMock, return_value=_make_fake_api_key_obj()),
            patch("airweave.core.credentials.decrypt", return_value={"key": "ak_test1234"}),
        ):
            response = await client.post("/api-keys/", json={})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_key_auth_create_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("", auth_method=AuthMethod.API_KEY)
        client = await _role_client(ctx)
        response = await client.post("/api-keys/", json={})
        assert response.status_code == 403
        assert "API key authentication is not permitted" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_system_auth_create_api_key_allowed(self, _role_client):
        ctx = _make_system_context()
        client = await _role_client(ctx)
        with (
            patch("airweave.crud.api_key.create", new_callable=AsyncMock, return_value=_make_fake_api_key_obj()),
            patch("airweave.core.credentials.decrypt", return_value={"key": "ak_test1234"}),
        ):
            response = await client.post("/api-keys/", json={})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_member_read_api_key_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        fake_id = str(uuid4())
        response = await client.get(f"/api-keys/{fake_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_read_api_key_allowed(self, _role_client):
        """Admin passes the role gate; CRUD mocked so endpoint returns 200."""
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        fake_id = str(uuid4())
        with (
            patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=_make_fake_api_key_obj()),
            patch("airweave.core.credentials.decrypt", return_value={"key": "ak_test1234"}),
        ):
            response = await client.get(f"/api-keys/{fake_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_member_list_api_keys_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.get("/api-keys/")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_list_api_keys_allowed(self, _role_client):
        """Admin lists keys; CRUD mocked to return [] so the full
        endpoint body (including audit logging) executes."""
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with patch("airweave.crud.api_key.get_multi", new_callable=AsyncMock, return_value=[]):
            response = await client.get("/api-keys/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_read_nonexistent_key_returns_404(self, _role_client):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=None):
            response = await client.get(f"/api-keys/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key_returns_404(self, _role_client):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=None):
            response = await client.delete(f"/api-keys/?id={uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rotate_nonexistent_key_returns_404(self, _role_client):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=None):
            response = await client.post(f"/api-keys/{uuid4()}/rotate")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth provider endpoint tests (CASA-13)
# ---------------------------------------------------------------------------


class TestAuthProviderRoleGating:
    """Mutating auth provider endpoints require owner/admin."""

    @pytest.mark.asyncio
    async def test_member_delete_auth_provider_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.delete("/auth-providers/some-provider")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_put_auth_provider_allowed(self, _role_client, test_container):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        fake_conn = _make_fake_auth_provider_connection()
        with patch.object(
            test_container.auth_provider_service,
            "update_connection",
            new_callable=AsyncMock,
            return_value=fake_conn,
        ):
            response = await client.put(
                "/auth-providers/some-provider",
                json={"auth_provider_short_name": "x", "credentials": {}},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_create_auth_provider_allowed(self, _role_client, test_container):
        ctx = _make_fake_context_with_role("owner")
        client = await _role_client(ctx)
        fake_conn = _make_fake_auth_provider_connection()
        with patch.object(
            test_container.auth_provider_service,
            "update_connection",
            new_callable=AsyncMock,
            return_value=fake_conn,
        ):
            response = await client.put(
                "/auth-providers/some-provider",
                json={"auth_provider_short_name": "x", "credentials": {}},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_member_list_auth_providers_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.get("/auth-providers/list")
        # Read endpoints remain open to all roles.
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Operational endpoint regression (no role restriction)
# ---------------------------------------------------------------------------


class TestOperationalEndpointsNoRegression:
    """Collections and other operational endpoints stay open to members."""

    @pytest.mark.asyncio
    async def test_member_list_collections_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.get("/collections/")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Webhook endpoint tests — no RBAC gating (webhook endpoints use get_context,
# not require_org_role, so that API key auth works for SDK consumers).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Billing endpoint tests
# ---------------------------------------------------------------------------


class TestBillingRoleGating:
    """Mutating billing endpoints require owner/admin."""

    @pytest.mark.asyncio
    async def test_member_checkout_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post(
            "/billing/checkout-session",
            json={
                "plan": "pro",
                "success_url": "https://example.com/ok",
                "cancel_url": "https://example.com/no",
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_checkout_allowed(self, _role_client, test_container):
        ctx = _make_fake_context_with_role("admin")
        client = await _role_client(ctx)
        with patch.object(
            test_container.billing_service,
            "start_subscription_checkout",
            new_callable=AsyncMock,
            return_value="https://checkout.fake/session",
        ):
            response = await client.post(
                "/billing/checkout-session",
                json={
                    "plan": "pro",
                    "success_url": "https://example.com/ok",
                    "cancel_url": "https://example.com/no",
                },
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_checkout_allowed(self, _role_client, test_container):
        ctx = _make_fake_context_with_role("owner")
        client = await _role_client(ctx)
        with patch.object(
            test_container.billing_service,
            "start_subscription_checkout",
            new_callable=AsyncMock,
            return_value="https://checkout.fake/session",
        ):
            response = await client.post(
                "/billing/checkout-session",
                json={
                    "plan": "pro",
                    "success_url": "https://example.com/ok",
                    "cancel_url": "https://example.com/no",
                },
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_member_yearly_checkout_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post(
            "/billing/yearly/checkout-session",
            json={
                "plan": "pro",
                "success_url": "https://example.com/ok",
                "cancel_url": "https://example.com/no",
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_portal_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post(
            "/billing/portal-session",
            json={"return_url": "https://example.com"},
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_update_plan_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post(
            "/billing/update-plan",
            json={"plan": "pro"},
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_cancel_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post("/billing/cancel")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_reactivate_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post("/billing/reactivate")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_cancel_plan_change_rejected(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.post("/billing/cancel-plan-change")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_get_subscription_allowed(self, _role_client):
        ctx = _make_fake_context_with_role("member")
        client = await _role_client(ctx)
        response = await client.get("/billing/subscription")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_stripe_webhook_not_gated(self, test_container):
        """Stripe webhook uses its own signature auth, no RBAC gating."""
        from airweave.core import container as container_mod
        from airweave.main import app

        async def _fake_db():
            yield None

        app.dependency_overrides[get_container] = lambda: test_container
        app.dependency_overrides[get_db] = _fake_db
        prev_container = container_mod.container
        container_mod.container = test_container
        app.state.http_metrics = test_container.metrics.http
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/billing/webhook")
        # 400 from missing Stripe signature proves the endpoint is not
        # behind an RBAC gate (which would return 403 instead).
        assert response.status_code == 400
        app.dependency_overrides.clear()
        container_mod.container = prev_container


# ---------------------------------------------------------------------------
# Source rate limit endpoint tests
# ---------------------------------------------------------------------------


class TestSourceRateLimitRoleGating:
    """Source rate limit endpoints require owner/admin + feature flag."""

    @pytest.mark.asyncio
    async def test_member_set_rejected(self, _role_client):
        ctx = _make_fake_context_with_role(
            "member",
            enabled_features=[FeatureFlag.SOURCE_RATE_LIMITING],
        )
        client = await _role_client(ctx)
        response = await client.put(
            "/source-rate-limits/some-source",
            json={"limit": 100, "window_seconds": 60},
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_set_allowed(self, _role_client):
        ctx = _make_fake_context_with_role(
            "admin",
            enabled_features=[FeatureFlag.SOURCE_RATE_LIMITING],
        )
        client = await _role_client(ctx)
        with patch(
            "airweave.core.source_rate_limit_helpers.set_source_rate_limit",
            new_callable=AsyncMock,
            return_value=_make_fake_rate_limit(),
        ):
            response = await client.put(
                "/source-rate-limits/some-source",
                json={"limit": 100, "window_seconds": 60},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_set_allowed(self, _role_client):
        ctx = _make_fake_context_with_role(
            "owner",
            enabled_features=[FeatureFlag.SOURCE_RATE_LIMITING],
        )
        client = await _role_client(ctx)
        with patch(
            "airweave.core.source_rate_limit_helpers.set_source_rate_limit",
            new_callable=AsyncMock,
            return_value=_make_fake_rate_limit(),
        ):
            response = await client.put(
                "/source-rate-limits/some-source",
                json={"limit": 100, "window_seconds": 60},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_member_delete_rejected(self, _role_client):
        ctx = _make_fake_context_with_role(
            "member",
            enabled_features=[FeatureFlag.SOURCE_RATE_LIMITING],
        )
        client = await _role_client(ctx)
        response = await client.delete("/source-rate-limits/some-source")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_member_list_allowed(self, _role_client):
        ctx = _make_fake_context_with_role(
            "member",
            enabled_features=[FeatureFlag.SOURCE_RATE_LIMITING],
        )
        client = await _role_client(ctx)

        # The endpoint queries the DB (which is None in this harness).
        # Provide a mock session so the query returns an empty result.
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        from airweave.main import app

        async def _mock_db():
            yield mock_db

        app.dependency_overrides[get_db] = _mock_db
        try:
            response = await client.get("/source-rate-limits/")
        finally:
            async def _fake_db():
                yield None

            app.dependency_overrides[get_db] = _fake_db
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Edge case tests for require_org_role
# ---------------------------------------------------------------------------


class TestRequireOrgRoleEdgeCases:
    """Cover require_org_role branches not exercised elsewhere."""

    @pytest.mark.asyncio
    async def test_api_key_auth_no_user_rejected(self, _role_client):
        """API key auth with no user on a non-block_api_key_auth endpoint."""
        ctx = _make_fake_context_with_role("", auth_method=AuthMethod.API_KEY)
        client = await _role_client(ctx)
        response = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 403
        assert "requires user authentication" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_user_not_in_org_rejected(self, _role_client):
        """User exists but belongs to a different org than ctx.organization."""
        ctx = _make_wrong_org_context()
        client = await _role_client(ctx)
        response = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_internal_system_auth_bypasses(self, _role_client):
        """INTERNAL_SYSTEM auth method bypasses role checks."""
        ctx = _make_internal_system_context()
        client = await _role_client(ctx)
        response = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
