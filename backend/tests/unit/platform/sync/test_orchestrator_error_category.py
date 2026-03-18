"""Tests for SyncOrchestrator._handle_sync_failure writing error_category."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import SourceConnectionErrorCategory, SyncJobStatus
from airweave.domains.sources.exceptions import SourceAuthError, SourceTokenRefreshError
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderAccountGoneError,
)
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pipeline.entity_tracker import SyncStats


def _make_sync_context(auth_method: str = "oauth2") -> MagicMock:
    ctx = MagicMock()
    ctx.sync_job.id = uuid4()
    ctx.sync_job.started_at = None
    ctx.sync.id = uuid4()
    ctx.connection.authentication_method = auth_method
    ctx.logger = MagicMock()
    return ctx


def _make_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.entity_tracker.get_stats.return_value = SyncStats()
    return runtime


def _make_orchestrator(sync_context: MagicMock, runtime: MagicMock) -> SyncOrchestrator:
    return SyncOrchestrator(
        entity_pipeline=MagicMock(),
        worker_pool=MagicMock(),
        stream=MagicMock(),
        sync_context=sync_context,
        runtime=runtime,
        access_control_pipeline=MagicMock(),
    )


@dataclass
class OrchestratorErrorCase:
    name: str
    exception: Exception
    auth_method: str
    expected_category: Optional[str]


CASES = [
    OrchestratorErrorCase(
        name="oauth_token_refresh",
        exception=SourceTokenRefreshError("refresh failed"),
        auth_method="oauth2",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED.value,
    ),
    OrchestratorErrorCase(
        name="api_key_auth_error",
        exception=SourceAuthError("401 unauthorized"),
        auth_method="api_key",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID.value,
    ),
    OrchestratorErrorCase(
        name="auth_provider_account_gone",
        exception=TokenProviderAccountGoneError("account deleted"),
        auth_method="auth_provider",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE.value,
    ),
    OrchestratorErrorCase(
        name="credentials_invalid_client_creds",
        exception=TokenCredentialsInvalidError("invalid client secret"),
        auth_method="oauth2_client_credentials",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED.value,
    ),
    OrchestratorErrorCase(
        name="generic_runtime_error",
        exception=RuntimeError("network issue"),
        auth_method="oauth2",
        expected_category=None,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_handle_sync_failure_writes_error_category(case: OrchestratorErrorCase):
    """_handle_sync_failure calls sync_job_service.update_status with correct error_category."""
    sync_context = _make_sync_context(auth_method=case.auth_method)
    runtime = _make_runtime()
    orchestrator = _make_orchestrator(sync_context, runtime)

    mock_update = AsyncMock()

    with (
        patch(
            "airweave.platform.sync.orchestrator.sync_job_service"
        ) as mock_sjs,
        patch(
            "airweave.platform.sync.orchestrator.business_events"
        ),
    ):
        mock_sjs.update_status = mock_update

        await orchestrator._handle_sync_failure(case.exception)

        mock_update.assert_awaited_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["status"] == SyncJobStatus.FAILED
        assert call_kwargs["error_category"] == case.expected_category
