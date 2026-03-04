"""Table-driven tests for TemporalWorkflowService.

Covers run_source_connection_workflow, cancel_sync_job_workflow,
start_cleanup_sync_data_workflow, and is_temporal_enabled.
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from temporalio.service import RPCError, RPCStatusCode

from airweave.domains.temporal.service import TemporalWorkflowService


def _rpc_error(msg: str, status: RPCStatusCode) -> RPCError:
    return RPCError(msg, status, b"")


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.logger = MagicMock()
    ctx.logger.info = MagicMock()
    ctx.logger.warning = MagicMock()
    ctx.logger.error = MagicMock()
    ctx.to_serializable_dict.return_value = {"org_id": str(uuid4())}
    return ctx


def _mock_schema(name: str = "test") -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.name = name
    m.model_dump.return_value = {"id": str(m.id), "name": name}
    return m


# ---------------------------------------------------------------------------
# run_source_connection_workflow
# ---------------------------------------------------------------------------


@dataclass
class RunWorkflowCase:
    name: str
    force_full_sync: bool = False
    access_token: Optional[str] = None


RUN_WORKFLOW_CASES = [
    RunWorkflowCase(name="default"),
    RunWorkflowCase(name="force_full_sync", force_full_sync=True),
    RunWorkflowCase(name="with_access_token", access_token="tok-abc"),
    RunWorkflowCase(name="full_sync_with_token", force_full_sync=True, access_token="tok-xyz"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", RUN_WORKFLOW_CASES, ids=lambda c: c.name)
async def test_run_source_connection_workflow(case: RunWorkflowCase):
    svc = TemporalWorkflowService()
    ctx = _mock_ctx()

    mock_client = AsyncMock()
    mock_handle = MagicMock()
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)

    sync = _mock_schema("my-sync")
    sync_job = _mock_schema("my-job")
    collection = _mock_schema("my-collection")
    connection = _mock_schema("my-connection")

    with patch(
        "airweave.domains.temporal.service.temporal_client"
    ) as mock_tc:
        mock_tc.get_client = AsyncMock(return_value=mock_client)

        result = await svc.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
            access_token=case.access_token,
            force_full_sync=case.force_full_sync,
        )

        assert result is mock_handle
        mock_client.start_workflow.assert_called_once()
        call_kwargs = mock_client.start_workflow.call_args
        args_list = call_kwargs.kwargs.get("args") or call_kwargs[1].get("args")
        assert args_list[-1] == case.force_full_sync
        assert args_list[-2] == case.access_token


# ---------------------------------------------------------------------------
# cancel_sync_job_workflow
# ---------------------------------------------------------------------------


@dataclass
class CancelCase:
    name: str
    cancel_side_effect: Optional[Exception] = None
    expected_success: bool = True
    expected_found: bool = True


CANCEL_CASES = [
    CancelCase(name="happy"),
    CancelCase(
        name="workflow_not_found",
        cancel_side_effect=_rpc_error("workflow not found", RPCStatusCode.NOT_FOUND),
        expected_success=True,
        expected_found=False,
    ),
    CancelCase(
        name="rpc_error_non_not_found",
        cancel_side_effect=_rpc_error("connection refused", RPCStatusCode.UNAVAILABLE),
        expected_success=False,
        expected_found=False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CANCEL_CASES, ids=lambda c: c.name)
async def test_cancel_sync_job_workflow(case: CancelCase):
    svc = TemporalWorkflowService()
    ctx = _mock_ctx()
    job_id = str(uuid4())

    mock_client = MagicMock()
    mock_handle = AsyncMock()
    if case.cancel_side_effect:
        mock_handle.cancel = AsyncMock(side_effect=case.cancel_side_effect)
    else:
        mock_handle.cancel = AsyncMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    with patch(
        "airweave.domains.temporal.service.temporal_client"
    ) as mock_tc:
        mock_tc.get_client = AsyncMock(return_value=mock_client)

        result = await svc.cancel_sync_job_workflow(job_id, ctx)

        assert result["success"] == case.expected_success
        assert result["workflow_found"] == case.expected_found


# ---------------------------------------------------------------------------
# start_cleanup_sync_data_workflow
# ---------------------------------------------------------------------------


@dataclass
class CleanupCase:
    name: str
    start_raises: bool = False
    expected_none: bool = False


CLEANUP_CASES = [
    CleanupCase(name="happy"),
    CleanupCase(name="start_fails", start_raises=True, expected_none=True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CLEANUP_CASES, ids=lambda c: c.name)
async def test_start_cleanup_sync_data_workflow(case: CleanupCase):
    svc = TemporalWorkflowService()
    ctx = _mock_ctx()

    mock_client = AsyncMock()
    if case.start_raises:
        mock_client.start_workflow = AsyncMock(side_effect=Exception("boom"))
    else:
        mock_client.start_workflow = AsyncMock(return_value=MagicMock())

    with patch(
        "airweave.domains.temporal.service.temporal_client"
    ) as mock_tc:
        mock_tc.get_client = AsyncMock(return_value=mock_client)

        result = await svc.start_cleanup_sync_data_workflow(
            sync_ids=["id1", "id2"],
            collection_id="col-1",
            organization_id="org-1",
            ctx=ctx,
        )

        if case.expected_none:
            assert result is None
        else:
            assert result is not None


# ---------------------------------------------------------------------------
# is_temporal_enabled
# ---------------------------------------------------------------------------


@dataclass
class EnabledCase:
    name: str
    setting_enabled: bool = True
    client_raises: bool = False
    expected: bool = True


ENABLED_CASES = [
    EnabledCase(name="enabled_and_reachable", expected=True),
    EnabledCase(name="disabled_in_settings", setting_enabled=False, expected=False),
    EnabledCase(name="enabled_but_unreachable", client_raises=True, expected=False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENABLED_CASES, ids=lambda c: c.name)
async def test_is_temporal_enabled(case: EnabledCase):
    svc = TemporalWorkflowService()

    with (
        patch("airweave.domains.temporal.service.settings") as mock_settings,
        patch("airweave.domains.temporal.service.temporal_client") as mock_tc,
    ):
        mock_settings.TEMPORAL_ENABLED = case.setting_enabled
        if case.client_raises:
            mock_tc.get_client = AsyncMock(side_effect=Exception("unreachable"))
        else:
            mock_tc.get_client = AsyncMock(return_value=MagicMock())

        result = await svc.is_temporal_enabled()
        assert result == case.expected
