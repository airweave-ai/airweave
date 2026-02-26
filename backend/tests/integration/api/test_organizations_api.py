"""API integration tests for organization creation endpoint."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from airweave.api import deps
from airweave.api.v1.endpoints import organizations as organizations_endpoint
from airweave.main import app
from airweave.schemas.organization import Organization


@pytest.fixture
def override_user_dep():
    """Override get_user dependency for endpoints using user-based auth."""
    fake_user = SimpleNamespace(
        id=uuid4(),
        email="owner@example.com",
        full_name="Owner User",
        auth0_id="auth0|owner",
    )
    app.dependency_overrides[deps.get_user] = lambda: fake_user
    yield fake_user
    app.dependency_overrides.pop(deps.get_user, None)


class TestOrganizationsCreateAPI:
    @pytest.mark.asyncio
    async def test_create_organization_success(self, client, override_user_dep, monkeypatch):
        now = datetime.now(timezone.utc)
        created_org = Organization(
            id=uuid4(),
            name="Org Alpha",
            description="Integration test org",
            created_at=now,
            modified_at=now,
        )

        async def _fake_create_with_integrations(*, db, org_data, owner_user):
            return created_org

        async def _fake_notify_signup(*args, **kwargs):
            return None

        monkeypatch.setattr(
            organizations_endpoint.organization_service,
            "create_organization_with_integrations",
            _fake_create_with_integrations,
        )
        monkeypatch.setattr(organizations_endpoint, "_notify_donke_signup", _fake_notify_signup)
        monkeypatch.setattr(
            organizations_endpoint.business_events, "set_organization_properties", lambda **kwargs: None
        )
        monkeypatch.setattr(
            "airweave.analytics.service.analytics.track_event", lambda **kwargs: None
        )

        response = await client.post(
            "/organizations",
            json={"name": "Org Alpha", "description": "Integration test org"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(created_org.id)
        assert data["name"] == "Org Alpha"

    @pytest.mark.asyncio
    async def test_create_organization_failure_returns_500(self, client, override_user_dep, monkeypatch):
        async def _fake_create_with_integrations(*, db, org_data, owner_user):
            raise TypeError("BaseContext.__init__() got an unexpected keyword argument 'user'")

        monkeypatch.setattr(
            organizations_endpoint.organization_service,
            "create_organization_with_integrations",
            _fake_create_with_integrations,
        )

        response = await client.post(
            "/organizations",
            json={"name": "Org Beta", "description": "Failure path"},
        )

        assert response.status_code == 500
        assert "unexpected keyword argument 'user'" in response.json()["detail"]
