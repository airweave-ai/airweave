"""Tests for WorkerConfig defaults and from_settings() wiring."""

from datetime import timedelta
from unittest.mock import patch

from airweave.platform.temporal.worker.config import WorkerConfig


def test_sdk_metrics_port_default():
    """sdk_metrics_port defaults to 9090 when omitted."""
    config = WorkerConfig(
        task_queue="q",
        metrics_port=8080,
        graceful_shutdown_timeout_seconds=30,
    )
    assert config.sdk_metrics_port == 9090


def test_sdk_metrics_port_override():
    """sdk_metrics_port can be set explicitly."""
    config = WorkerConfig(
        task_queue="q",
        metrics_port=8080,
        graceful_shutdown_timeout_seconds=30,
        sdk_metrics_port=9999,
    )
    assert config.sdk_metrics_port == 9999


def test_from_settings_wires_sdk_metrics_port():
    """from_settings() reads TEMPORAL_SDK_METRICS_PORT."""
    with patch("airweave.platform.temporal.worker.config.settings") as mock:
        mock.TEMPORAL_TASK_QUEUE = "q"
        mock.WORKER_METRICS_PORT = 8080
        mock.TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT = 30
        mock.TEMPORAL_DISABLE_SANDBOX = False
        mock.TEMPORAL_SDK_METRICS_PORT = 7777

        config = WorkerConfig.from_settings()

    assert config.sdk_metrics_port == 7777


def test_from_settings_wires_all_fields():
    """from_settings() maps every settings field correctly."""
    with patch("airweave.platform.temporal.worker.config.settings") as mock:
        mock.TEMPORAL_TASK_QUEUE = "my-queue"
        mock.WORKER_METRICS_PORT = 9091
        mock.TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT = 60
        mock.TEMPORAL_DISABLE_SANDBOX = True
        mock.TEMPORAL_SDK_METRICS_PORT = 9999

        config = WorkerConfig.from_settings()

    assert config.task_queue == "my-queue"
    assert config.metrics_port == 9091
    assert config.graceful_shutdown_timeout_seconds == 60
    assert config.disable_sandbox is True
    assert config.sdk_metrics_port == 9999

    # Defaults for fields not covered by from_settings()
    assert config.max_concurrent_workflow_polls == 8
    assert config.max_concurrent_activity_polls == 16
    assert config.sticky_queue_schedule_to_start_timeout == timedelta(seconds=0.5)
    assert config.nonsticky_to_sticky_poll_ratio == 0.5
    assert config.default_heartbeat_throttle_interval == timedelta(seconds=2)
    assert config.max_heartbeat_throttle_interval == timedelta(seconds=2)
