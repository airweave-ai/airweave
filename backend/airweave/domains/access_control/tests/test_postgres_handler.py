"""Tests for ACPostgresHandler — upsert batching and bulk_create path."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.access_control.actions import ACActionBatch, ACUpsertAction
from airweave.domains.access_control.fakes.repository import (
    FakeAccessControlMembershipRepository,
)
from airweave.domains.access_control.postgres_handler import ACPostgresHandler
from airweave.domains.sync_pipeline.exceptions import SyncFailureError


@dataclass
class FakeSyncContext:
    organization_id: object = field(default_factory=uuid4)
    source_connection_id: object = field(default_factory=uuid4)
    connection: object = field(default_factory=lambda: SimpleNamespace(short_name="slack"))
    logger: object = field(default_factory=lambda: MagicMock())


def _make_membership(member_id="alice", group_id="g1"):
    return SimpleNamespace(member_id=member_id, group_id=group_id)


_GET_DB_CTX = "airweave.domains.access_control.postgres_handler.get_db_context"


class TestHandleBatch:
    @pytest.mark.asyncio
    async def test_no_mutations_returns_zero(self):
        handler = ACPostgresHandler(acl_repo=FakeAccessControlMembershipRepository())
        batch = ACActionBatch()
        result = await handler.handle_batch(batch, FakeSyncContext())
        assert result == 0

    @pytest.mark.asyncio
    async def test_upserts_call_bulk_create(self):
        repo = FakeAccessControlMembershipRepository()
        handler = ACPostgresHandler(acl_repo=repo)
        ctx = FakeSyncContext()

        memberships = [_make_membership(f"user-{i}", "g1") for i in range(3)]
        batch = ACActionBatch(upserts=[ACUpsertAction(membership=m) for m in memberships])

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handler.handle_batch(batch, ctx)

        assert result == 3

    @pytest.mark.asyncio
    async def test_upserts_batch_large_set(self):
        """Batches of >2000 memberships are split into chunks."""
        call_counts = []
        repo = FakeAccessControlMembershipRepository()

        original_bulk_create = repo.bulk_create

        async def tracking_bulk_create(*args, **kwargs):
            result = await original_bulk_create(*args, **kwargs)
            call_counts.append(result)
            return result

        repo.bulk_create = tracking_bulk_create
        handler = ACPostgresHandler(acl_repo=repo)
        ctx = FakeSyncContext()

        memberships = [_make_membership(f"user-{i}", "g1") for i in range(4500)]
        batch = ACActionBatch(upserts=[ACUpsertAction(membership=m) for m in memberships])

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await handler.handle_batch(batch, ctx)

        assert result == 4500
        assert len(call_counts) == 3  # 2000 + 2000 + 500

    @pytest.mark.asyncio
    async def test_exception_wraps_as_sync_failure(self):
        repo = FakeAccessControlMembershipRepository()

        async def failing_bulk_create(*args, **kwargs):
            raise RuntimeError("DB connection lost")

        repo.bulk_create = failing_bulk_create
        handler = ACPostgresHandler(acl_repo=repo)
        ctx = FakeSyncContext()

        batch = ACActionBatch(
            upserts=[ACUpsertAction(membership=_make_membership())]
        )

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(SyncFailureError, match="persistence failed"):
                await handler.handle_batch(batch, ctx)


class TestHandleUpserts:
    @pytest.mark.asyncio
    async def test_empty_actions_returns_zero(self):
        handler = ACPostgresHandler(acl_repo=FakeAccessControlMembershipRepository())
        result = await handler.handle_upserts([], FakeSyncContext())
        assert result == 0
