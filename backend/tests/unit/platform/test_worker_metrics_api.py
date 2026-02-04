"""Tests for Temporal worker metrics API endpoints.

Tests the public API endpoints exposed by the worker:
- /metrics (Prometheus format)
- /status (JSON format)

These tests cover commits:
- 9527bc63d6fbe7b39f21271ae962ca472a9beb89: feat: extensive sync worker metrics
- 6b7cae7898c859cd51de4dbf6136389da264a6df: fix: remove deadlock risks and private API dependencies
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.temporal.worker import TemporalWorker, WorkerControlServer, WorkerState
from airweave.platform.temporal.worker.config import WorkerConfig


class MockAsyncWorkerPool:
    """Mock AsyncWorkerPool for testing."""

    def __init__(self, active_count: int = 5, pending_count: int = 3):
        """Initialize mock worker pool."""
        self.max_workers = 20
        self.pending_tasks = [MagicMock() for _ in range(active_count + pending_count)]
        self._cancelled = False

    @property
    def active_and_pending_count(self) -> int:
        """Return total active and pending tasks."""
        return len(self.pending_tasks)


@pytest.fixture
def mock_worker_metrics():
    """Create mock worker metrics registry."""
    metrics = MagicMock()

    # Basic metrics
    metrics.worker_id = "test-worker-0"
    metrics.get_pod_ordinal.return_value = "0"

    # Mock get_metrics_summary
    metrics.get_metrics_summary = AsyncMock(
        return_value={
            "worker_id": "test-worker-0",
            "uptime_seconds": 3600.5,
            "active_activities_count": 3,
            "active_sync_jobs": [str(uuid4()), str(uuid4())],
            "active_activities": [
                {
                    "activity_name": "run_sync_activity",
                    "sync_job_id": str(uuid4()),
                    "sync_id": str(uuid4()),
                    "organization_id": str(uuid4()),
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "duration_seconds": 45.2,
                    "metadata": {
                        "connection_name": "Test Connection",
                        "collection_name": "Test Collection",
                        "source_type": "slack",
                        "org_name": "Test Org",
                    },
                }
            ],
        }
    )

    # Mock connector metrics (aggregated by connector type)
    metrics.get_per_connector_metrics = AsyncMock(
        return_value={
            "slack": {
                "active_syncs": 2,
                "active_and_pending_workers": 15,
            },
            "notion": {
                "active_syncs": 1,
                "active_and_pending_workers": 5,
            },
        }
    )

    # Mock total active and pending workers
    metrics.get_total_active_and_pending_workers = AsyncMock(return_value=20)

    # Mock detailed sync metrics
    metrics.get_detailed_sync_metrics = AsyncMock(
        return_value=[
            {
                "sync_id": str(uuid4()),
                "sync_job_id": str(uuid4()),
                "org_name": "Test Org",
                "source_type": "slack",
            },
            {
                "sync_id": str(uuid4()),
                "sync_job_id": str(uuid4()),
                "org_name": "Another Org",
                "source_type": "notion",
            },
        ]
    )

    # Mock per-sync worker counts
    sync_id_1 = str(uuid4())
    sync_id_2 = str(uuid4())
    metrics.get_per_sync_worker_counts = AsyncMock(
        return_value=[
            {"sync_id": sync_id_1, "active_and_pending_worker_count": 15},
            {"sync_id": sync_id_2, "active_and_pending_worker_count": 5},
        ]
    )

    return metrics


@pytest.fixture
def test_worker_config():
    """Create test worker config."""
    return WorkerConfig(
        task_queue="test-queue",
        metrics_port=9090,
        graceful_shutdown_timeout_seconds=30,
    )


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch("airweave.platform.temporal.worker.control_server.settings") as mock:
        mock.TEMPORAL_TASK_QUEUE = "test-queue"
        mock.SYNC_MAX_WORKERS = 20
        mock.SYNC_THREAD_POOL_SIZE = 100
        yield mock


def create_control_server(config: WorkerConfig, running: bool = True, draining: bool = False):
    """Helper to create a control server with state."""
    state = WorkerState(running=running, draining=draining)
    return WorkerControlServer(state, config), state


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_running_state(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /metrics endpoint returns Prometheus format when worker is running."""
    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=25
        ):
            with patch(
                "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
            ) as mock_update:
                with patch(
                    "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                    return_value=b"# Prometheus metrics\nairweave_worker_info{version=\"1.0\"} 1\n",
                ):
                    control_server, state = create_control_server(
                        test_worker_config, running=True, draining=False
                    )

                    request = MagicMock()
                    response = await control_server._handle_metrics(request)

                    # Verify response format
                    assert response.status == 200
                    assert "text/plain" in response.content_type
                    assert b"Prometheus metrics" in response.body

                    # Verify metrics were updated with correct parameters
                    mock_update.assert_called_once()
                    call_kwargs = mock_update.call_args.kwargs
                    assert call_kwargs["worker_id"] == "0"  # Pod ordinal
                    assert call_kwargs["status"] == "running"
                    assert call_kwargs["uptime_seconds"] == 3600.5
                    assert call_kwargs["active_activities_count"] == 3
                    assert call_kwargs["active_sync_jobs_count"] == 2
                    assert call_kwargs["task_queue"] == "test-queue"
                    assert call_kwargs["worker_pool_active_and_pending_count"] == 20
                    assert call_kwargs["sync_max_workers"] == 20
                    assert call_kwargs["thread_pool_size"] == 100
                    assert call_kwargs["thread_pool_active"] == 25

                    # Verify connector metrics passed correctly
                    connector_metrics = call_kwargs["connector_metrics"]
                    assert "slack" in connector_metrics
                    assert connector_metrics["slack"]["active_syncs"] == 2
                    assert connector_metrics["slack"]["active_and_pending_workers"] == 15


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_draining_state(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /metrics endpoint shows draining status when worker is draining."""
    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=10
        ):
            with patch(
                "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
            ) as mock_update:
                with patch(
                    "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                    return_value=b"# Prometheus metrics\n",
                ):
                    control_server, state = create_control_server(
                        test_worker_config, running=True, draining=True
                    )

                    request = MagicMock()
                    await control_server._handle_metrics(request)

                    # Verify status is draining
                    call_kwargs = mock_update.call_args.kwargs
                    assert call_kwargs["status"] == "draining"


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_error_handling(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /metrics endpoint handles errors gracefully."""
    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        mock_worker_metrics.get_metrics_summary.side_effect = Exception("Test error")

        control_server, state = create_control_server(test_worker_config, running=True)

        request = MagicMock()
        response = await control_server._handle_metrics(request)

        # Verify error response
        assert response.status == 500
        assert "Test error" in response.text


@pytest.mark.asyncio
async def test_json_status_endpoint_complete_response(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /status endpoint returns complete JSON with all metrics."""
    # Mock psutil in sys.modules
    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 75.3
    mock_memory = MagicMock()
    mock_memory.rss = 512 * 1024 * 1024  # 512 MB
    mock_process.memory_info.return_value = mock_memory
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=42
        ):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                control_server, state = create_control_server(
                    test_worker_config, running=True, draining=False
                )

                request = MagicMock()
                response = await control_server._handle_status(request)

                # Verify response is JSON
                assert response.status == 200
                # Parse JSON response
                import json

                data = json.loads(response.body.decode("utf-8"))

                # Verify basic worker info
                assert data["worker_id"] == "test-worker-0"
                assert data["status"] == "running"
                assert data["uptime_seconds"] == 3600.5
                assert data["task_queue"] == "test-queue"
                assert data["active_activities_count"] == 3

                # Verify capacity info
                assert data["capacity"]["max_workflow_polls"] == 8
                assert data["capacity"]["max_activity_polls"] == 16

                # Verify active_syncs structure
                assert "active_syncs" in data
                assert len(data["active_syncs"]) == 2
                for sync in data["active_syncs"]:
                    assert "sync_id" in sync
                    assert "sync_job_id" in sync
                    assert "org_name" in sync
                    assert "source_type" in sync
                    assert "workers_allocated" in sync
                    assert "duration_seconds" in sync

                # Verify metrics structure (new in commit 9527bc63)
                assert "metrics" in data
                metrics = data["metrics"]
                assert metrics["total_workers"] == 20
                assert metrics["active_and_pending_workers"] == 20
                assert metrics["total_threads"] == 100
                assert metrics["active_threads"] == 42
                assert metrics["cpu_percent"] == 75.3
                assert metrics["memory_mb"] == 512


@pytest.mark.asyncio
async def test_json_status_endpoint_psutil_fallback(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /status endpoint falls back gracefully when psutil unavailable."""
    # Mock psutil to raise ImportError
    mock_psutil = MagicMock()
    mock_psutil.Process.side_effect = ImportError("psutil not available")

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=10
        ):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                control_server, state = create_control_server(test_worker_config, running=True)

                request = MagicMock()
                response = await control_server._handle_status(request)

                # Verify fallback values
                assert response.status == 200
                import json

                data = json.loads(response.body.decode("utf-8"))
                assert data["metrics"]["cpu_percent"] == 0.0
                assert data["metrics"]["memory_mb"] == 0


@pytest.mark.asyncio
async def test_json_status_endpoint_handles_missing_sync_id(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /status endpoint handles syncs without matching worker counts."""
    orphan_sync_id = str(uuid4())

    mock_worker_metrics.get_detailed_sync_metrics = AsyncMock(
        return_value=[
            {
                "sync_id": orphan_sync_id,
                "sync_job_id": str(uuid4()),
                "org_name": "Orphan Org",
                "source_type": "slack",
            }
        ]
    )

    # No matching worker count
    mock_worker_metrics.get_per_sync_worker_counts = AsyncMock(return_value=[])

    mock_worker_metrics.get_metrics_summary = AsyncMock(
        return_value={
            "worker_id": "test-worker-0",
            "uptime_seconds": 50.0,
            "active_activities_count": 0,
            "active_sync_jobs": [],
            "active_activities": [],
        }
    )

    # Mock psutil
    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 0.0
    mock_process.memory_info.return_value = MagicMock(rss=0)
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=0
        ):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                control_server, state = create_control_server(test_worker_config, running=True)

                request = MagicMock()
                response = await control_server._handle_status(request)

                # Verify defaults are applied
                import json

                data = json.loads(response.body.decode("utf-8"))
                assert len(data["active_syncs"]) == 1
                assert data["active_syncs"][0]["workers_allocated"] == 0
                assert data["active_syncs"][0]["duration_seconds"] == 0


@pytest.mark.asyncio
async def test_json_status_endpoint_error_handling(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /status endpoint handles errors gracefully."""
    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        mock_worker_metrics.get_metrics_summary.side_effect = Exception("Test error")

        control_server, state = create_control_server(test_worker_config, running=True)

        request = MagicMock()
        response = await control_server._handle_status(request)

        # Verify error response
        assert response.status == 500
        # Parse JSON from response body
        import json

        data = json.loads(response.body.decode("utf-8"))
        assert data["error"] == "Failed to generate status"
        assert "Test error" in data["detail"]


@pytest.mark.asyncio
async def test_worker_pool_active_and_pending_count_property():
    """Test AsyncWorkerPool.active_and_pending_count property (commit 6b7cae789)."""
    # Test with 8 tasks (5 active + 3 pending)
    pool = MockAsyncWorkerPool(active_count=5, pending_count=3)
    assert pool.active_and_pending_count == 8

    # Test with 20 tasks (all slots filled)
    pool = MockAsyncWorkerPool(active_count=20, pending_count=0)
    assert pool.active_and_pending_count == 20

    # Test with 25 tasks (20 active + 5 pending)
    pool = MockAsyncWorkerPool(active_count=20, pending_count=5)
    assert pool.active_and_pending_count == 25


@pytest.mark.asyncio
async def test_connector_metrics_aggregation(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test connector-type aggregated metrics (low cardinality)."""
    # Test that connector metrics are aggregated by type, not by individual sync
    mock_worker_metrics.get_per_connector_metrics = AsyncMock(
        return_value={
            "slack": {"active_syncs": 5, "active_and_pending_workers": 50},
            "notion": {"active_syncs": 3, "active_and_pending_workers": 30},
            "google_drive": {"active_syncs": 2, "active_and_pending_workers": 20},
        }
    )

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=0
        ):
            with patch(
                "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
            ) as mock_update:
                with patch(
                    "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                    return_value=b"",
                ):
                    control_server, state = create_control_server(
                        test_worker_config, running=True
                    )

                    request = MagicMock()
                    await control_server._handle_metrics(request)

                    # Verify connector metrics are passed correctly
                    call_kwargs = mock_update.call_args.kwargs
                    connector_metrics = call_kwargs["connector_metrics"]

                    # Should have 3 connector types
                    assert len(connector_metrics) == 3
                    assert all(
                        key in connector_metrics for key in ["slack", "notion", "google_drive"]
                    )

                    # Verify structure includes both syncs and workers
                    for connector, metrics in connector_metrics.items():
                        assert "active_syncs" in metrics
                        assert "active_and_pending_workers" in metrics


@pytest.mark.asyncio
async def test_thread_pool_metrics_integration(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test thread pool metrics are correctly tracked and reported."""
    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        # Test various thread pool activity levels
        for thread_count in [0, 25, 50, 100]:
            with patch(
                "airweave.platform.sync.async_helpers.get_active_thread_count",
                return_value=thread_count,
            ):
                with patch(
                    "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
                ) as mock_update:
                    with patch(
                        "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                        return_value=b"",
                    ):
                        control_server, state = create_control_server(
                            test_worker_config, running=True
                        )

                        request = MagicMock()
                        await control_server._handle_metrics(request)

                        # Verify thread pool count is passed
                        call_kwargs = mock_update.call_args.kwargs
                        assert call_kwargs["thread_pool_active"] == thread_count
                        assert call_kwargs["thread_pool_size"] == 100  # From settings


@pytest.mark.asyncio
async def test_pod_ordinal_extraction_for_low_cardinality():
    """Test worker_id uses pod ordinal for low-cardinality metrics (commit 9527bc63)."""
    from airweave.platform.temporal.worker_metrics import WorkerMetricsRegistry

    with patch.dict(
        "os.environ",
        {
            "HOSTNAME": "airweave-worker-0",
        },
    ):
        registry = WorkerMetricsRegistry()
        assert registry.get_pod_ordinal() == "0"

    with patch.dict(
        "os.environ",
        {
            "HOSTNAME": "airweave-worker-12",
        },
    ):
        registry = WorkerMetricsRegistry()
        assert registry.get_pod_ordinal() == "12"

    with patch.dict(
        "os.environ",
        {
            "HOSTNAME": "random-hostname",
        },
    ):
        registry = WorkerMetricsRegistry()
        assert registry.get_pod_ordinal() == "random-hostname"


@pytest.mark.asyncio
async def test_metrics_endpoint_uses_pod_ordinal(
    mock_worker_metrics, mock_settings, test_worker_config
):
    """Test /metrics endpoint uses pod ordinal instead of full worker_id."""
    mock_worker_metrics.get_pod_ordinal.return_value = "3"

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=0
        ):
            with patch(
                "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
            ) as mock_update:
                with patch(
                    "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                    return_value=b"",
                ):
                    control_server, state = create_control_server(
                        test_worker_config, running=True
                    )

                    request = MagicMock()
                    await control_server._handle_metrics(request)

                    # Verify pod ordinal is used (low cardinality)
                    call_kwargs = mock_update.call_args.kwargs
                    assert call_kwargs["worker_id"] == "3"


@pytest.mark.asyncio
async def test_zero_active_syncs_scenario(mock_worker_metrics, mock_settings, test_worker_config):
    """Test endpoints handle zero active syncs correctly."""
    # Mock empty state
    mock_worker_metrics.get_metrics_summary = AsyncMock(
        return_value={
            "worker_id": "test-worker-0",
            "uptime_seconds": 1000.0,
            "active_activities_count": 0,
            "active_sync_jobs": [],
            "active_activities": [],
        }
    )
    mock_worker_metrics.get_per_connector_metrics = AsyncMock(return_value={})
    mock_worker_metrics.get_total_active_and_pending_workers = AsyncMock(return_value=0)
    mock_worker_metrics.get_detailed_sync_metrics = AsyncMock(return_value=[])
    mock_worker_metrics.get_per_sync_worker_counts = AsyncMock(return_value=[])

    # Mock psutil
    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 5.0
    mock_process.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.worker_metrics", mock_worker_metrics
    ):
        with patch(
            "airweave.platform.sync.async_helpers.get_active_thread_count", return_value=0
        ):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                control_server, state = create_control_server(test_worker_config, running=True)

                # Test JSON status
                request = MagicMock()
                response = await control_server._handle_status(request)

                import json

                data = json.loads(response.body.decode("utf-8"))
                assert data["active_activities_count"] == 0
                assert len(data["active_syncs"]) == 0
                assert data["metrics"]["active_and_pending_workers"] == 0
                assert data["metrics"]["active_threads"] == 0

                # Test Prometheus metrics
                with patch(
                    "airweave.platform.temporal.worker.control_server.update_prometheus_metrics"
                ) as mock_update:
                    with patch(
                        "airweave.platform.temporal.worker.control_server.get_prometheus_metrics",
                        return_value=b"",
                    ):
                        await control_server._handle_metrics(request)

                        call_kwargs = mock_update.call_args.kwargs
                        assert call_kwargs["active_activities_count"] == 0
                        assert call_kwargs["active_sync_jobs_count"] == 0
                        assert call_kwargs["worker_pool_active_and_pending_count"] == 0
                        assert call_kwargs["connector_metrics"] == {}
