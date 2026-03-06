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
async def test_create_organization_delegates_and_returns_org():
    db = AsyncMock()
    user = SimpleNamespace(email="owner@example.com")
    org_in = schemas.OrganizationCreate(name="Test Organization", description="Test Description")
    created_org = _make_org_schema()

    mock_org_service = AsyncMock()
    mock_org_service.create_organization = AsyncMock(return_value=created_org)

    result = await organizations_endpoint.create_organization(
        organization_data=org_in,
        db=db,
        user=user,
        org_service=mock_org_service,
    )

    assert result == created_org
    mock_org_service.create_organization.assert_awaited_once_with(
        db=db, org_data=org_in, owner_user=user
    )


@pytest.mark.asyncio
async def test_create_organization_wraps_failures_in_http_500():
    db = AsyncMock()
    user = SimpleNamespace(email="owner@example.com")
    org_in = schemas.OrganizationCreate(name="Test Organization", description="Test Description")

    mock_org_service = AsyncMock()
    mock_org_service.create_organization = AsyncMock(
        side_effect=TypeError("BaseContext.__init__() got an unexpected keyword argument 'user'"),
    )

    with pytest.raises(HTTPException) as exc:
        await organizations_endpoint.create_organization(
            organization_data=org_in,
            db=db,
            user=user,
            org_service=mock_org_service,
        )

    assert exc.value.status_code == 500
