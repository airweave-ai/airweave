"""Unit tests for OrganizationService.

Focuses on org creation and regressions around context construction.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.organization_service import OrganizationService
from airweave.core import organization_service as org_service_module


class _FakeRowResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class _FakeUnitOfWork:
    def __init__(self, _db):
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_local_org(org_id):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=org_id,
        name="Test Organization",
        description="Test Description",
        auth0_org_id=None,
        created_at=now,
        modified_at=now,
        org_metadata={"k": "v"},
    )


@pytest.mark.asyncio
async def test_create_organization_uses_base_context_without_user(monkeypatch):
    """Regression: BaseContext should not be constructed with user=."""
    service = OrganizationService()

    org_id = uuid4()
    now = datetime.now(timezone.utc)
    owner_user = SimpleNamespace(id=uuid4(), email="owner@example.com", auth0_id="auth0|owner")
    org_data = schemas.OrganizationCreate(name="Test Organization", description="Test Description")
    local_org = _make_local_org(org_id)

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_FakeRowResult(
            (
                org_id,
                local_org.name,
                local_org.description,
                local_org.auth0_org_id,
                now,
                now,
                {"k": "v"},
            )
        )
    )

    create_with_owner_mock = AsyncMock(return_value=local_org)
    api_key_create_mock = AsyncMock()
    invalidate_user_mock = AsyncMock()
    create_customer_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(org_service_module, "UnitOfWork", _FakeUnitOfWork)
    monkeypatch.setattr(org_service_module.settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(org_service_module.crud.organization, "create_with_owner", create_with_owner_mock)
    monkeypatch.setattr(org_service_module.crud.api_key, "create", api_key_create_mock)
    monkeypatch.setattr(org_service_module.context_cache, "invalidate_user", invalidate_user_mock)
    monkeypatch.setattr(org_service_module._payment_gateway, "create_customer", create_customer_mock)

    result = await service.create_organization_with_integrations(
        db=db,
        org_data=org_data,
        owner_user=owner_user,
    )

    assert result.id == org_id
    assert result.name == org_data.name
    assert api_key_create_mock.await_count == 1
    api_key_ctx = api_key_create_mock.await_args.kwargs["ctx"]
    assert isinstance(api_key_ctx, BaseContext)
    assert api_key_ctx.organization.id == org_id
    assert not hasattr(api_key_ctx, "user")
    invalidate_user_mock.assert_awaited_once_with(owner_user.email)


@pytest.mark.asyncio
async def test_create_organization_rolls_back_customer_on_failure(monkeypatch):
    """If local flow fails after customer creation, customer cleanup is attempted."""
    service = OrganizationService()

    org_id = uuid4()
    now = datetime.now(timezone.utc)
    owner_user = SimpleNamespace(id=uuid4(), email="owner@example.com", auth0_id="auth0|owner")
    org_data = schemas.OrganizationCreate(name="Test Organization", description="Test Description")
    local_org = _make_local_org(org_id)

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_FakeRowResult(
            (
                org_id,
                local_org.name,
                local_org.description,
                local_org.auth0_org_id,
                now,
                now,
                {"k": "v"},
            )
        )
    )

    fake_customer = SimpleNamespace(id="cus_test_123")
    create_with_owner_mock = AsyncMock(return_value=local_org)
    create_customer_mock = AsyncMock(return_value=fake_customer)
    delete_customer_mock = AsyncMock()
    api_key_create_mock = AsyncMock(side_effect=RuntimeError("api key create failed"))
    create_billing_record_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(org_service_module, "UnitOfWork", _FakeUnitOfWork)
    monkeypatch.setattr(org_service_module.settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(org_service_module.crud.organization, "create_with_owner", create_with_owner_mock)
    monkeypatch.setattr(org_service_module.crud.api_key, "create", api_key_create_mock)
    monkeypatch.setattr(org_service_module._payment_gateway, "create_customer", create_customer_mock)
    monkeypatch.setattr(org_service_module._payment_gateway, "delete_customer", delete_customer_mock)
    monkeypatch.setattr(
        org_service_module._billing_ops, "create_billing_record", create_billing_record_mock
    )

    with pytest.raises(RuntimeError, match="api key create failed"):
        await service.create_organization_with_integrations(
            db=db,
            org_data=org_data,
            owner_user=owner_user,
        )

    delete_customer_mock.assert_awaited_once_with(fake_customer.id)
