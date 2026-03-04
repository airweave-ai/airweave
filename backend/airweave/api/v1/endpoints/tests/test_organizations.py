"""API tests for organizations endpoint."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave import schemas
from airweave.api.v1.endpoints import organizations as organizations_endpoint


def _make_org_schema() -> schemas.Organization:
    now = datetime.utcnow()
    return schemas.Organization(
        id=uuid4(),
        name="Test Organization",
        description="Test Description",
        created_at=now,
        modified_at=now,
        role="owner",
    )


@pytest.mark.asyncio
async def test_create_organization_delegates_and_returns_org(monkeypatch):
    db = AsyncMock()
    user = SimpleNamespace(email="owner@example.com")
    org_in = schemas.OrganizationCreate(name="Test Organization", description="Test Description")
    created_org = _make_org_schema()

    create_with_integrations_mock = AsyncMock(return_value=created_org)
    notify_signup_mock = AsyncMock()
    set_org_properties_mock = AsyncMock()
    track_event_mock = AsyncMock()

    monkeypatch.setattr(
        organizations_endpoint.organization_service,
        "create_organization_with_integrations",
        create_with_integrations_mock,
    )
    monkeypatch.setattr(organizations_endpoint, "_notify_donke_signup", notify_signup_mock)
    monkeypatch.setattr(
        organizations_endpoint.business_events,
        "set_organization_properties",
        set_org_properties_mock,
    )
    monkeypatch.setattr("airweave.analytics.service.analytics.track_event", track_event_mock)

    result = await organizations_endpoint.create_organization(
        organization_data=org_in,
        db=db,
        user=user,
    )

    assert result == created_org
    create_with_integrations_mock.assert_awaited_once()
    notify_signup_mock.assert_awaited_once_with(created_org, user, db)
    set_org_properties_mock.assert_called_once()
    track_event_mock.assert_called_once()


@pytest.mark.asyncio
async def test_create_organization_wraps_failures_in_http_500(monkeypatch):
    db = AsyncMock()
    user = SimpleNamespace(email="owner@example.com")
    org_in = schemas.OrganizationCreate(name="Test Organization", description="Test Description")

    monkeypatch.setattr(
        organizations_endpoint.organization_service,
        "create_organization_with_integrations",
        AsyncMock(side_effect=TypeError("BaseContext.__init__() got an unexpected keyword argument 'user'")),
    )

    with pytest.raises(HTTPException) as exc:
        await organizations_endpoint.create_organization(
            organization_data=org_in,
            db=db,
            user=user,
        )

    assert exc.value.status_code == 500
    assert "unexpected keyword argument 'user'" in str(exc.value.detail)
