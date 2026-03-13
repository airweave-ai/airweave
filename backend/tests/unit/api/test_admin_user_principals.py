"""Unit tests for admin user-principals endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.api.v1.endpoints.admin import admin_get_user_principals
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.platform.access_control.schemas import AccessContext


@pytest.fixture
def mock_ctx():
    """Mock API context with admin permissions."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.request_id = "req-123"
    ctx.user = MagicMock()
    ctx.user.id = uuid4()
    ctx.user.is_admin = True
    ctx.user.is_superuser = True
    ctx.organization_id = uuid4()
    return ctx


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


def _collection_repo(readable_id: str, organization_id) -> FakeCollectionRepository:
    """Build a FakeCollectionRepository seeded with a single collection."""
    col = MagicMock()
    col.organization_id = organization_id
    repo = FakeCollectionRepository()
    repo.seed_readable(readable_id, col)
    return repo


@pytest.mark.asyncio
class TestAdminGetUserPrincipals:
    """Test admin_get_user_principals endpoint."""

    async def test_returns_principals_for_user(self, mock_db, mock_ctx):
        """Returns resolved principals when access context is found."""
        fake_access_ctx = AccessContext(
            user_principal="sp_admin",
            user_principals=["user:sp_admin"],
            group_principals=["group:ad:engineering", "group:sp:site_members"],
        )

        collection_repo = _collection_repo("test-collection", mock_ctx.organization_id)

        with patch(
            "airweave.api.v1.endpoints.admin._require_admin_permission"
        ), patch(
            "airweave.platform.access_control.broker.access_broker"
        ) as mock_broker:
            mock_broker.resolve_access_context_for_collection = AsyncMock(
                return_value=fake_access_ctx
            )

            result = await admin_get_user_principals(
                readable_id="test-collection",
                user_principal="sp_admin",
                db=mock_db,
                ctx=mock_ctx,
                collection_repo=collection_repo,
            )

        assert "user:sp_admin" in result
        assert "group:ad:engineering" in result
        assert "group:sp:site_members" in result
        assert len(result) == 3

    async def test_returns_empty_when_no_access_context(self, mock_db, mock_ctx):
        """Returns empty list when access broker returns None."""
        collection_repo = _collection_repo("test-collection", mock_ctx.organization_id)

        with patch(
            "airweave.api.v1.endpoints.admin._require_admin_permission"
        ), patch(
            "airweave.platform.access_control.broker.access_broker"
        ) as mock_broker:
            mock_broker.resolve_access_context_for_collection = AsyncMock(return_value=None)

            result = await admin_get_user_principals(
                readable_id="test-collection",
                user_principal="unknown_user",
                db=mock_db,
                ctx=mock_ctx,
                collection_repo=collection_repo,
            )

        assert result == []
