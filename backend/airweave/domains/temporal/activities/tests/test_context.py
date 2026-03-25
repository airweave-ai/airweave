"""Tests for build_activity_context — coverage of legacy fallback path."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave import schemas
from airweave.domains.temporal.activities.context import (
    _fetch_organization,
    build_activity_context,
)

MODULE = "airweave.domains.temporal.activities.context"

ORG_ID = "00000000-0000-0000-0000-000000000001"


def _make_org_schema():
    return schemas.Organization(
        id=UUID(ORG_ID),
        name="Test Org",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


@asynccontextmanager
async def _fake_db():
    yield AsyncMock()


# ── build_activity_context ─────────────────────────────────────────


@pytest.mark.unit
async def test_legacy_ctx_dict_fetches_from_db():
    """When ctx_dict has organization_id but no organization, fetch from DB."""
    org = _make_org_schema()

    with patch(f"{MODULE}._fetch_organization", new_callable=AsyncMock, return_value=org):
        ctx = await build_activity_context({"organization_id": ORG_ID})

    assert ctx.organization.id == UUID(ORG_ID)


@pytest.mark.unit
async def test_legacy_ctx_dict_missing_both_raises():
    """When ctx_dict has neither organization nor organization_id, raise."""
    with pytest.raises(ValueError, match="neither"):
        await build_activity_context({})


# ── _fetch_organization ───────────────────────────────────────────


@pytest.mark.unit
async def test_fetch_organization_returns_schema_directly():
    """When crud.organization.get returns a schema, return it as-is."""
    org = _make_org_schema()
    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(return_value=org)

    with (
        patch("airweave.db.session.get_db_context", _fake_db),
        patch("airweave.crud", mock_crud),
    ):
        result = await _fetch_organization(UUID(ORG_ID))

    assert result.id == UUID(ORG_ID)


@pytest.mark.unit
async def test_fetch_organization_validates_orm_model():
    """When crud.organization.get returns an ORM model, validate it."""
    from airweave.models.organization import Organization

    orm_org = MagicMock(spec=Organization)
    orm_org.id = UUID(ORG_ID)
    orm_org.name = "Test Org"
    orm_org.description = None
    orm_org.auth0_org_id = None
    orm_org.billing = None
    orm_org.org_metadata = None
    orm_org.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    orm_org.modified_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(return_value=orm_org)

    with (
        patch("airweave.db.session.get_db_context", _fake_db),
        patch("airweave.crud", mock_crud),
    ):
        result = await _fetch_organization(UUID(ORG_ID))

    assert result.id == UUID(ORG_ID)
