"""Table-driven tests for SyncService.

Covers the happy path (factory → orchestrator → run) and the error path
(factory raises → job marked FAILED → re-raised).
"""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import SourceConnectionErrorCategory, SyncJobStatus
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.exceptions import TokenCredentialsInvalidError
from airweave.domains.syncs.fakes.sync_job_service import FakeSyncJobService
from airweave.domains.syncs.service import SyncService


def _mock_ctx():
    """Minimal mock that satisfies ApiContext duck-typing."""
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
    fake_job_svc = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake_job_svc)

    sync = _mock_sync()
    sync_job = _mock_sync_job()
    collection = MagicMock()
    source_connection = MagicMock()
    ctx = _mock_ctx()
    dense_embedder = MagicMock()
    sparse_embedder = MagicMock()

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
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    source_connection=source_connection,
                    ctx=ctx,
                    dense_embedder=dense_embedder,
                    sparse_embedder=sparse_embedder,
                )
        else:
            result = await svc.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=source_connection,
                ctx=ctx,
                dense_embedder=dense_embedder,
                sparse_embedder=sparse_embedder,
            )
            assert result is case.orchestrator_result
            mock_orchestrator.run.assert_awaited_once()

    if case.expect_job_failed:
        assert len(fake_job_svc._calls) == 1
        call = fake_job_svc._calls[0]
        assert call[0] == "update_status"
        assert call[1] == sync_job.id
        assert call[2] == SyncJobStatus.FAILED
        assert call[5] == str(case.factory_error)
    else:
        assert len(fake_job_svc._calls) == 0


# ---------------------------------------------------------------------------
# run() — optional kwargs forwarded to factory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_forwards_optional_kwargs():
    """access_token, force_full_sync, execution_config reach the factory."""
    fake_job_svc = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake_job_svc)

    mock_orchestrator = MagicMock()
    mock_orchestrator.run = AsyncMock(return_value=_mock_sync())
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

        exec_config = MagicMock()

        await svc.run(
            sync=_mock_sync(),
            sync_job=_mock_sync_job(),
            collection=MagicMock(),
            source_connection=MagicMock(),
            ctx=_mock_ctx(),
            dense_embedder=MagicMock(),
            sparse_embedder=MagicMock(),
            access_token="tok-123",
            force_full_sync=True,
            execution_config=exec_config,
        )

        _, kwargs = mock_factory_cls.create_orchestrator.call_args
        assert kwargs["access_token"] == "tok-123"
        assert kwargs["force_full_sync"] is True
        assert kwargs["execution_config"] is exec_config


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_stores_sync_job_service():
    fake = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake)
    assert svc._sync_job_service is fake


# ---------------------------------------------------------------------------
# run() — error_category written on auth failures
# ---------------------------------------------------------------------------


@dataclass
class ErrorCategoryCase:
    name: str
    exception: Exception
    auth_method: str
    expected_category: Optional[str]


ERROR_CATEGORY_CASES = [
    ErrorCategoryCase(
        name="oauth_source_auth_error",
        exception=SourceAuthError("token expired"),
        auth_method="oauth2",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED.value,
    ),
    ErrorCategoryCase(
        name="api_key_credentials_invalid",
        exception=TokenCredentialsInvalidError("bad key"),
        auth_method="api_key",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID.value,
    ),
    ErrorCategoryCase(
        name="generic_error_no_category",
        exception=RuntimeError("network timeout"),
        auth_method="oauth2",
        expected_category=None,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ERROR_CATEGORY_CASES, ids=lambda c: c.name)
async def test_run_writes_error_category(case: ErrorCategoryCase):
    """Validate failure in factory writes error_category to sync job."""
    fake_job_svc = FakeSyncJobService()
    svc = SyncService(sync_job_service=fake_job_svc)

    sync = _mock_sync()
    sync_job = _mock_sync_job()
    source_connection = MagicMock()
    ctx = _mock_ctx()

    mock_db = AsyncMock()

    with (
        patch("airweave.domains.syncs.service.get_db_context") as mock_db_ctx,
        patch("airweave.domains.syncs.service.SyncFactory") as mock_factory_cls,
        patch(
            "airweave.domains.syncs.service.SyncService._resolve_authentication_method",
            new_callable=AsyncMock,
            return_value=case.auth_method,
        ),
    ):
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_factory_cls.create_orchestrator = AsyncMock(side_effect=case.exception)

        with pytest.raises(type(case.exception)):
            await svc.run(
                sync=sync,
                sync_job=sync_job,
                collection=MagicMock(),
                source_connection=source_connection,
                ctx=ctx,
                dense_embedder=MagicMock(),
                sparse_embedder=MagicMock(),
            )

    assert len(fake_job_svc._calls) == 1
    call = fake_job_svc._calls[0]
    assert call[0] == "update_status"
    assert call[2] == SyncJobStatus.FAILED
    # error_category is at index 6 in the tuple
    assert call[6] == case.expected_category


# ---------------------------------------------------------------------------
# _resolve_authentication_method — direct unit tests (not patched)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_auth_method_no_credential_id():
    """Connection with integration_credential_id=None returns ''."""
    connection = MagicMock()
    connection.integration_credential_id = None
    ctx = _mock_ctx()

    result = await SyncService._resolve_authentication_method(connection, ctx)
    assert result == ""


@pytest.mark.asyncio
async def test_resolve_auth_method_returns_method_from_db():
    """Connection with credential_id, DB returns credential with authentication_method → returns it."""
    cred_id = uuid4()
    connection = MagicMock()
    connection.integration_credential_id = cred_id
    ctx = _mock_ctx()

    credential = MagicMock()
    credential.authentication_method = "oauth2"

    mock_db = AsyncMock()

    with (
        patch("airweave.domains.syncs.service.get_db_context") as mock_db_ctx,
        patch("airweave.crud.integration_credential.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_get.return_value = credential

        result = await SyncService._resolve_authentication_method(connection, ctx)

    assert result == "oauth2"
    mock_get.assert_awaited_once_with(mock_db, id=cred_id, ctx=ctx)
