"""Table-driven tests for SyncService.

Covers the happy path (factory → orchestrator → run) and the error path
(factory raises → job marked FAILED → re-raised).
"""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.fakes.sync_job_service import FakeSyncJobService
from airweave.domains.syncs.service import SyncService


def _mock_ctx():
    """Minimal mock that satisfies BaseContext duck-typing."""
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.logger = MagicMock()
    ctx.logger.error = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# run() — table-driven
# ---------------------------------------------------------------------------


@dataclass
class RunCase:
    name: str
    factory_error: Optional[Exception] = None
    orchestrator_result: Optional[MagicMock] = field(default=None)
    expect_job_failed: bool = False
    expect_raises: bool = False

    def __post_init__(self):
        """Default orchestrator_result to a MagicMock when no factory error."""
        if self.orchestrator_result is None and self.factory_error is None:
            self.orchestrator_result = MagicMock()


RUN_CASES = [
    RunCase(
        name="happy_path",
    ),
    RunCase(
        name="factory_raises_marks_job_failed",
        factory_error=RuntimeError("bad config"),
        expect_job_failed=True,
        expect_raises=True,
    ),
    RunCase(
        name="factory_value_error",
        factory_error=ValueError("missing field"),
        expect_job_failed=True,
        expect_raises=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", RUN_CASES, ids=lambda c: c.name)
async def test_run(case: RunCase):
    fake_job_svc = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake_job_svc)

    sync_id = uuid4()
    sync_job_id = uuid4()
    ctx = _mock_ctx()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=case.orchestrator_result)

    mock_db = AsyncMock()

    with (
        patch(
            "airweave.domains.syncs.service.get_db_context",
        ) as mock_db_ctx,
        patch(
            "airweave.domains.syncs.service.SyncFactory",
        ) as mock_factory_cls,
    ):
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        if case.factory_error:
            mock_factory_cls.create_orchestrator = AsyncMock(
                side_effect=case.factory_error,
            )
        else:
            mock_factory_cls.create_orchestrator = AsyncMock(
                return_value=mock_orchestrator,
            )

        if case.expect_raises:
            with pytest.raises(type(case.factory_error)):
                await svc.run(
                    sync_id=sync_id,
                    sync_job_id=sync_job_id,
                    ctx=ctx,
                )
        else:
            result = await svc.run(
                sync_id=sync_id,
                sync_job_id=sync_job_id,
                ctx=ctx,
            )
            assert result is case.orchestrator_result
            mock_orchestrator.run.assert_awaited_once()

    if case.expect_job_failed:
        assert len(fake_job_svc._calls) == 1
        call = fake_job_svc._calls[0]
        assert call[0] == "update_status"
        assert call[1] == sync_job_id
        assert call[2] == SyncJobStatus.FAILED
        assert call[5] == str(case.factory_error)
    else:
        assert len(fake_job_svc._calls) == 0


# ---------------------------------------------------------------------------
# run() — optional kwargs forwarded to factory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_force_full_sync():
    """force_full_sync reaches the factory."""
    fake_job_svc = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake_job_svc)

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=MagicMock())
    mock_db = AsyncMock()

    with (
        patch(
            "airweave.domains.syncs.service.get_db_context",
        ) as mock_db_ctx,
        patch(
            "airweave.domains.syncs.service.SyncFactory",
        ) as mock_factory_cls,
    ):
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_factory_cls.create_orchestrator = AsyncMock(
            return_value=mock_orchestrator,
        )

        await svc.run(
            sync_id=uuid4(),
            sync_job_id=uuid4(),
            ctx=_mock_ctx(),
            force_full_sync=True,
        )

        _, kwargs = mock_factory_cls.create_orchestrator.call_args
        assert kwargs["force_full_sync"] is True


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_stores_sync_job_service():
    fake = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake)
    assert svc._sync_job_service is fake
