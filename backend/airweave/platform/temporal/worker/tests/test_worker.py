"""Tests for TemporalWorker — mock only Runtime (port-binding side effect).

Every other dependency (PrometheusConfig, TelemetryConfig, CollectorRegistry,
PrometheusWorkerMetrics, PrometheusMetricsRenderer, WorkerControlServer,
WorkerMetricsRegistry) is constructed for real so tests exercise actual wiring.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.runtime import PrometheusConfig, TelemetryConfig

from airweave.platform.temporal.worker.config import WorkerConfig
from airweave.platform.temporal.worker.control_server import WorkerControlServer


def _make_config(**overrides):
    """Build a minimal WorkerConfig for testing."""
    defaults = dict(
        task_queue="test-queue",
        metrics_port=8080,
        graceful_shutdown_timeout_seconds=30,
    )
    defaults.update(overrides)
    return WorkerConfig(**defaults)


# ── __init__ tests ──────────────────────────────────────────────────


@patch("temporalio.runtime.Runtime")
def test_init_creates_runtime_with_correct_config(mock_runtime_cls):
    """__init__ builds a real TelemetryConfig(PrometheusConfig) and passes it to Runtime."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config(sdk_metrics_port=9999)
    worker = TemporalWorker(config)

    # Runtime was called exactly once
    mock_runtime_cls.assert_called_once()
    _, kwargs = mock_runtime_cls.call_args

    # The telemetry arg is a real TelemetryConfig, not a mock
    telemetry = kwargs["telemetry"]
    assert isinstance(telemetry, TelemetryConfig)

    # Its metrics member is a real PrometheusConfig with the right address
    assert isinstance(telemetry.metrics, PrometheusConfig)
    assert telemetry.metrics.bind_address == "0.0.0.0:9999"

    # The worker holds the Runtime *instance*
    assert worker._runtime is mock_runtime_cls.return_value


@patch("temporalio.runtime.Runtime")
def test_init_default_sdk_metrics_port(mock_runtime_cls):
    """Default sdk_metrics_port (9090) wires through to PrometheusConfig."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config()  # sdk_metrics_port defaults to 9090
    TemporalWorker(config)

    _, kwargs = mock_runtime_cls.call_args
    assert kwargs["telemetry"].metrics.bind_address == "0.0.0.0:9090"


@patch("temporalio.runtime.Runtime")
def test_init_constructs_real_control_server(mock_runtime_cls):
    """__init__ creates a real WorkerControlServer with real metrics objects."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config()
    worker = TemporalWorker(config)

    assert isinstance(worker._control_server, WorkerControlServer)


# ── start() tests ───────────────────────────────────────────────────


@patch("airweave.platform.temporal.worker.Worker")
@patch("airweave.platform.temporal.worker.get_workflows", return_value=[])
@patch("airweave.platform.temporal.worker.create_activities", return_value=[])
@patch("temporalio.runtime.Runtime")
async def test_start_passes_runtime_to_get_client(
    mock_runtime_cls,
    _mock_activities,
    _mock_workflows,
    mock_worker_cls,
):
    """start() forwards self._runtime when calling get_client()."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config(sdk_metrics_port=9999)
    worker = TemporalWorker(config)
    runtime_instance = worker._runtime

    # Make control_server.start() and Worker.run() no-ops
    worker._control_server.start = AsyncMock()
    mock_worker_cls.return_value.run = AsyncMock()

    with patch(
        "airweave.platform.temporal.client.TemporalClient.get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_get_client.return_value = MagicMock()
        await worker.start()

        mock_get_client.assert_awaited_once()
        _, kwargs = mock_get_client.call_args
        assert kwargs["runtime"] is runtime_instance


# ── _get_sandbox_runner() tests ─────────────────────────────────────


@patch("temporalio.runtime.Runtime")
def test_get_sandbox_runner_default(mock_runtime_cls):
    """With disable_sandbox=False, returns a SandboxedWorkflowRunner."""
    from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config(disable_sandbox=False)
    worker = TemporalWorker(config)

    runner = worker._get_sandbox_runner()
    assert isinstance(runner, SandboxedWorkflowRunner)


@patch("temporalio.runtime.Runtime")
def test_get_sandbox_runner_disabled(mock_runtime_cls):
    """With disable_sandbox=True, returns an UnsandboxedWorkflowRunner."""
    from temporalio.worker import UnsandboxedWorkflowRunner

    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config(disable_sandbox=True)
    worker = TemporalWorker(config)

    runner = worker._get_sandbox_runner()
    assert isinstance(runner, UnsandboxedWorkflowRunner)


# ── stop() tests ────────────────────────────────────────────────────


@patch("airweave.platform.temporal.client.TemporalClient.close", new_callable=AsyncMock)
@patch("temporalio.runtime.Runtime")
async def test_stop_shuts_down_worker_and_control_server(mock_runtime_cls, mock_client_close):
    """stop() shuts down the worker, stops the control server, and closes the client."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config()
    worker = TemporalWorker(config)

    # Simulate a running worker
    mock_temporal_worker = AsyncMock()
    worker._worker = mock_temporal_worker
    worker._state.running = True
    worker._control_server.stop = AsyncMock()

    await worker.stop()

    mock_temporal_worker.shutdown.assert_awaited_once()
    worker._control_server.stop.assert_awaited_once()
    mock_client_close.assert_awaited_once()
    assert worker._state.running is False


@patch("airweave.platform.temporal.client.TemporalClient.close", new_callable=AsyncMock)
@patch("temporalio.runtime.Runtime")
async def test_stop_skips_shutdown_when_not_running(mock_runtime_cls, mock_client_close):
    """stop() skips worker shutdown if no worker is active."""
    from airweave.platform.temporal.worker import TemporalWorker

    config = _make_config()
    worker = TemporalWorker(config)
    worker._control_server.stop = AsyncMock()

    # _worker is None, _state.running is False — should not raise
    await worker.stop()

    worker._control_server.stop.assert_awaited_once()
    mock_client_close.assert_awaited_once()
