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
from airweave.domains.syncs.service import SyncService


def _mock_ctx():
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.logger = MagicMock()
    ctx.logger.error = MagicMock()
    return ctx


def _mock_sync(sync_id=None):
    s = MagicMock()
    s.id = sync_id or uuid4()
    return s


def _mock_sync_job(job_id=None):
    j = MagicMock()
    j.id = job_id or uuid4()
    return j


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
    fake_state_machine = AsyncMock()
    fake_factory = MagicMock()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=case.orchestrator_result)

    if case.factory_error:
        fake_factory.create_orchestrator = AsyncMock(
            side_effect=case.factory_error,
        )
    else:
        fake_factory.create_orchestrator = AsyncMock(
            return_value=mock_orchestrator,
        )

    svc = SyncService(
        state_machine=fake_state_machine,
        sync_factory=fake_factory,
    )

    sync = _mock_sync()
    sync_job = _mock_sync_job()
    collection = MagicMock()
    source_connection = MagicMock()
    ctx = _mock_ctx()

    mock_db = AsyncMock()

    with patch(
        "airweave.domains.syncs.service.get_db_context",
    ) as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        if case.expect_raises:
            with pytest.raises(type(case.factory_error)):
                await svc.run(
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    source_connection=source_connection,
                    ctx=ctx,
                )
        else:
            result = await svc.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=source_connection,
                ctx=ctx,
            )
            assert result is case.orchestrator_result
            mock_orchestrator.run.assert_awaited_once()

    if case.expect_job_failed:
        fake_state_machine.transition.assert_awaited_once()
        call_kwargs = fake_state_machine.transition.call_args.kwargs
        assert call_kwargs["sync_job_id"] == sync_job.id
        assert call_kwargs["target"] == SyncJobStatus.FAILED
        assert call_kwargs["error"] == str(case.factory_error)
    else:
        fake_state_machine.transition.assert_not_awaited()


# ---------------------------------------------------------------------------
# run() — optional kwargs forwarded to factory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_optional_kwargs():
    """force_full_sync, execution_config reach the factory."""
    fake_state_machine = AsyncMock()
    fake_factory = MagicMock()

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=_mock_sync())
    fake_factory.create_orchestrator = AsyncMock(
        return_value=mock_orchestrator,
    )

    svc = SyncService(
        state_machine=fake_state_machine,
        sync_factory=fake_factory,
    )

    mock_db = AsyncMock()
    exec_config = MagicMock()

    with patch(
        "airweave.domains.syncs.service.get_db_context",
    ) as mock_db_ctx:
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await svc.run(
            sync=_mock_sync(),
            sync_job=_mock_sync_job(),
            collection=MagicMock(),
            source_connection=MagicMock(),
            ctx=_mock_ctx(),
            force_full_sync=True,
            execution_config=exec_config,
        )

        _, kwargs = fake_factory.create_orchestrator.call_args
        assert kwargs["force_full_sync"] is True
        assert kwargs["execution_config"] is exec_config


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_stores_injected_deps():
    fake_sm = MagicMock()
    fake_factory = MagicMock()
    svc = SyncService(state_machine=fake_sm, sync_factory=fake_factory)
    assert svc._state_machine is fake_sm
    assert svc._sync_factory is fake_factory
