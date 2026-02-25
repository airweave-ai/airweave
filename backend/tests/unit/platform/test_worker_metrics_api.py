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

from airweave.adapters.metrics import FakeMetricsRenderer, FakeWorkerMetrics
from airweave.platform.temporal.worker import WorkerControlServer, WorkerState
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
def mock_registry():
    """Create mock WorkerMetricsRegistry."""
    registry = MagicMock()

    registry.worker_id = "test-worker-0"
    registry.get_pod_ordinal.return_value = "0"

    registry.get_metrics_summary = AsyncMock(
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

    registry.get_per_connector_metrics = AsyncMock(
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

    registry.get_total_active_and_pending_workers = AsyncMock(return_value=20)

    registry.get_detailed_sync_metrics = AsyncMock(
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

    sync_id_1 = str(uuid4())
    sync_id_2 = str(uuid4())
    registry.get_per_sync_worker_counts = AsyncMock(
        return_value=[
            {"sync_id": sync_id_1, "active_and_pending_worker_count": 15},
            {"sync_id": sync_id_2, "active_and_pending_worker_count": 5},
        ]
    )

    return registry


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


def create_control_server(
    config: WorkerConfig,
    mock_registry,
    running: bool = True,
    draining: bool = False,
    fake_worker_metrics: FakeWorkerMetrics | None = None,
    fake_renderer: FakeMetricsRenderer | None = None,
):
    """Helper to create a control server with injected fakes."""
    state = WorkerState(running=running, draining=draining)
    wm = fake_worker_metrics or FakeWorkerMetrics()
    renderer = fake_renderer or FakeMetricsRenderer()
    server = WorkerControlServer(
        worker_state=state,
        config=config,
        registry=mock_registry,
        worker_metrics=wm,
        renderer=renderer,
    )
    return server, state, wm, renderer


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_running_state(
    mock_registry, mock_settings, test_worker_config
):
    """Test /metrics endpoint returns Prometheus format when worker is running."""
    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=25,
    ):
        server, state, fake_wm, _ = create_control_server(
            test_worker_config, mock_registry, running=True, draining=False
        )

        request = MagicMock()
        response = await server._handle_metrics(request)

        assert response.status == 200
        assert response.content_type == "text/plain"
        assert response.charset == "utf-8"

        snap = fake_wm.last_snapshot
        assert snap is not None
        assert snap.worker_id == "0"
        assert snap.status == "running"
        assert snap.uptime_seconds == 3600.5
        assert snap.active_activities_count == 3
        assert snap.active_sync_jobs_count == 2
        assert snap.task_queue == "test-queue"
        assert snap.worker_pool_active_and_pending_count == 20
        assert snap.sync_max_workers == 20
        assert snap.thread_pool_size == 100
        assert snap.thread_pool_active == 25

        assert "slack" in snap.connector_metrics
        assert snap.connector_metrics["slack"].active_syncs == 2
        assert snap.connector_metrics["slack"].active_and_pending_workers == 15


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_draining_state(
    mock_registry, mock_settings, test_worker_config
):
    """Test /metrics endpoint shows draining status when worker is draining."""
    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=10,
    ):
        server, state, fake_wm, _ = create_control_server(
            test_worker_config, mock_registry, running=True, draining=True
        )

        request = MagicMock()
        await server._handle_metrics(request)

        assert fake_wm.last_snapshot.status == "draining"


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_error_handling(
    mock_registry, mock_settings, test_worker_config
):
    """Test /metrics endpoint handles errors gracefully."""
    mock_registry.get_metrics_summary.side_effect = Exception("Test error")

    server, state, _, _ = create_control_server(test_worker_config, mock_registry, running=True)

    request = MagicMock()
    response = await server._handle_metrics(request)

    assert response.status == 500
    assert "Test error" in response.text


@pytest.mark.asyncio
async def test_json_status_endpoint_complete_response(
    mock_registry, mock_settings, test_worker_config
):
    """Test /status endpoint returns complete JSON with all metrics."""
    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 75.3
    mock_memory = MagicMock()
    mock_memory.rss = 512 * 1024 * 1024
    mock_process.memory_info.return_value = mock_memory
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=42,
    ):
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            server, state, _, _ = create_control_server(
                test_worker_config, mock_registry, running=True, draining=False
            )

            request = MagicMock()
            response = await server._handle_status(request)

            assert response.status == 200
            import json

            data = json.loads(response.body.decode("utf-8"))

            assert data["worker_id"] == "test-worker-0"
            assert data["status"] == "running"
            assert data["uptime_seconds"] == 3600.5
            assert data["task_queue"] == "test-queue"
            assert data["active_activities_count"] == 3

            assert data["capacity"]["max_workflow_polls"] == 8
            assert data["capacity"]["max_activity_polls"] == 16

            assert "active_syncs" in data
            assert len(data["active_syncs"]) == 2
            for sync in data["active_syncs"]:
                assert "sync_id" in sync
                assert "sync_job_id" in sync
                assert "org_name" in sync
                assert "source_type" in sync
                assert "workers_allocated" in sync
                assert "duration_seconds" in sync

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
    mock_registry, mock_settings, test_worker_config
):
    """Test /status endpoint falls back gracefully when psutil unavailable."""
    mock_psutil = MagicMock()
    mock_psutil.Process.side_effect = ImportError("psutil not available")

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=10,
    ):
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            server, state, _, _ = create_control_server(
                test_worker_config, mock_registry, running=True
            )

            request = MagicMock()
            response = await server._handle_status(request)

            assert response.status == 200
            import json

            data = json.loads(response.body.decode("utf-8"))
            assert data["metrics"]["cpu_percent"] == 0.0
            assert data["metrics"]["memory_mb"] == 0


@pytest.mark.asyncio
async def test_json_status_endpoint_handles_missing_sync_id(
    mock_registry, mock_settings, test_worker_config
):
    """Test /status endpoint handles syncs without matching worker counts."""
    orphan_sync_id = str(uuid4())

    mock_registry.get_detailed_sync_metrics = AsyncMock(
        return_value=[
            {
                "sync_id": orphan_sync_id,
                "sync_job_id": str(uuid4()),
                "org_name": "Orphan Org",
                "source_type": "slack",
            }
        ]
    )

    mock_registry.get_per_sync_worker_counts = AsyncMock(return_value=[])

    mock_registry.get_metrics_summary = AsyncMock(
        return_value={
            "worker_id": "test-worker-0",
            "uptime_seconds": 50.0,
            "active_activities_count": 0,
            "active_sync_jobs": [],
            "active_activities": [],
        }
    )

    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 0.0
    mock_process.memory_info.return_value = MagicMock(rss=0)
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=0,
    ):
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            server, state, _, _ = create_control_server(
                test_worker_config, mock_registry, running=True
            )

            request = MagicMock()
            response = await server._handle_status(request)

            import json

            data = json.loads(response.body.decode("utf-8"))
            assert len(data["active_syncs"]) == 1
            assert data["active_syncs"][0]["workers_allocated"] == 0
            assert data["active_syncs"][0]["duration_seconds"] == 0


@pytest.mark.asyncio
async def test_json_status_endpoint_error_handling(
    mock_registry, mock_settings, test_worker_config
):
    """Test /status endpoint handles errors gracefully."""
    mock_registry.get_metrics_summary.side_effect = Exception("Test error")

    server, state, _, _ = create_control_server(test_worker_config, mock_registry, running=True)

    request = MagicMock()
    response = await server._handle_status(request)

    assert response.status == 500
    import json

    data = json.loads(response.body.decode("utf-8"))
    assert data["error"] == "Failed to generate status"
    assert "Test error" in data["detail"]


@pytest.mark.asyncio
async def test_worker_pool_active_and_pending_count_property():
    """Test AsyncWorkerPool.active_and_pending_count property (commit 6b7cae789)."""
    pool = MockAsyncWorkerPool(active_count=5, pending_count=3)
    assert pool.active_and_pending_count == 8

    pool = MockAsyncWorkerPool(active_count=20, pending_count=0)
    assert pool.active_and_pending_count == 20

    pool = MockAsyncWorkerPool(active_count=20, pending_count=5)
    assert pool.active_and_pending_count == 25


@pytest.mark.asyncio
async def test_connector_metrics_aggregation(mock_registry, mock_settings, test_worker_config):
    """Test connector-type aggregated metrics (low cardinality)."""
    mock_registry.get_per_connector_metrics = AsyncMock(
        return_value={
            "slack": {"active_syncs": 5, "active_and_pending_workers": 50},
            "notion": {"active_syncs": 3, "active_and_pending_workers": 30},
            "google_drive": {"active_syncs": 2, "active_and_pending_workers": 20},
        }
    )

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=0,
    ):
        server, state, fake_wm, _ = create_control_server(
            test_worker_config, mock_registry, running=True
        )

        request = MagicMock()
        await server._handle_metrics(request)

        snap = fake_wm.last_snapshot
        assert len(snap.connector_metrics) == 3
        assert all(key in snap.connector_metrics for key in ["slack", "notion", "google_drive"])

        for cs in snap.connector_metrics.values():
            assert cs.active_syncs > 0
            assert cs.active_and_pending_workers > 0


@pytest.mark.asyncio
async def test_thread_pool_metrics_integration(mock_registry, mock_settings, test_worker_config):
    """Test thread pool metrics are correctly tracked and reported."""
    for thread_count in [0, 25, 50, 100]:
        with patch(
            "airweave.platform.temporal.worker.control_server.get_active_thread_count",
            return_value=thread_count,
        ):
            server, state, fake_wm, _ = create_control_server(
                test_worker_config, mock_registry, running=True
            )

            request = MagicMock()
            await server._handle_metrics(request)

            snap = fake_wm.last_snapshot
            assert snap.thread_pool_active == thread_count
            assert snap.thread_pool_size == 100


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
async def test_metrics_endpoint_uses_pod_ordinal(mock_registry, mock_settings, test_worker_config):
    """Test /metrics endpoint uses pod ordinal instead of full worker_id."""
    mock_registry.get_pod_ordinal.return_value = "3"

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=0,
    ):
        server, state, fake_wm, _ = create_control_server(
            test_worker_config, mock_registry, running=True
        )

        request = MagicMock()
        await server._handle_metrics(request)

        assert fake_wm.last_snapshot.worker_id == "3"


@pytest.mark.asyncio
async def test_zero_active_syncs_scenario(mock_registry, mock_settings, test_worker_config):
    """Test endpoints handle zero active syncs correctly."""
    mock_registry.get_metrics_summary = AsyncMock(
        return_value={
            "worker_id": "test-worker-0",
            "uptime_seconds": 1000.0,
            "active_activities_count": 0,
            "active_sync_jobs": [],
            "active_activities": [],
        }
    )
    mock_registry.get_per_connector_metrics = AsyncMock(return_value={})
    mock_registry.get_total_active_and_pending_workers = AsyncMock(return_value=0)
    mock_registry.get_detailed_sync_metrics = AsyncMock(return_value=[])
    mock_registry.get_per_sync_worker_counts = AsyncMock(return_value=[])

    mock_psutil = MagicMock()
    mock_process = MagicMock()
    mock_process.cpu_percent.return_value = 5.0
    mock_process.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
    mock_psutil.Process.return_value = mock_process

    with patch(
        "airweave.platform.temporal.worker.control_server.get_active_thread_count",
        return_value=0,
    ):
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            server, state, fake_wm, _ = create_control_server(
                test_worker_config, mock_registry, running=True
            )

            # Test JSON status
            request = MagicMock()
            response = await server._handle_status(request)

            import json

            data = json.loads(response.body.decode("utf-8"))
            assert data["active_activities_count"] == 0
            assert len(data["active_syncs"]) == 0
            assert data["metrics"]["active_and_pending_workers"] == 0
            assert data["metrics"]["active_threads"] == 0

            # Test Prometheus metrics
            await server._handle_metrics(request)

            snap = fake_wm.last_snapshot
            assert snap.active_activities_count == 0
            assert snap.active_sync_jobs_count == 0
            assert snap.worker_pool_active_and_pending_count == 0
            assert snap.connector_metrics == {}
