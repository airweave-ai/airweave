"""Tests for PrometheusWorkerMetrics adapter.

Each test creates a fresh adapter with its own CollectorRegistry, so tests
are fully isolated (no shared module-level gauges).
"""

from prometheus_client import CollectorRegistry, ProcessCollector

from airweave.adapters.metrics import PrometheusWorkerMetrics
from airweave.platform.temporal.worker_metrics_snapshot import (
    ConnectorSnapshot,
    WorkerMetricsSnapshot,
)


def _make_adapter() -> tuple[PrometheusWorkerMetrics, CollectorRegistry]:
    registry = CollectorRegistry()
    adapter = PrometheusWorkerMetrics(registry=registry)
    return adapter, registry


def _render(registry: CollectorRegistry) -> str:
    from prometheus_client import generate_latest

    return generate_latest(registry).decode("utf-8")


def _make_snapshot(**overrides) -> WorkerMetricsSnapshot:
    defaults = dict(
        worker_id="0",
        status="running",
        uptime_seconds=100.0,
        active_activities_count=5,
        active_sync_jobs_count=3,
        task_queue="test-queue",
        worker_pool_active_and_pending_count=15,
        connector_metrics={},
        sync_max_workers=20,
        thread_pool_size=100,
        thread_pool_active=25,
    )
    defaults.update(overrides)
    return WorkerMetricsSnapshot(**defaults)


def test_basic_metrics_update():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot())

    text = _render(registry)
    assert "airweave_worker_status" in text
    assert "airweave_worker_uptime_seconds" in text
    assert "airweave_worker_active_activities" in text
    assert "airweave_worker_active_sync_jobs" in text
    assert "airweave_worker_pool_active_and_pending_workers" in text
    assert "airweave_worker_sync_max_workers_config" in text
    assert "airweave_worker_thread_pool_size_config" in text
    assert "airweave_worker_thread_pool_active" in text


def test_status_values():
    adapter, registry = _make_adapter()

    for status_str, expected_value in [("running", "1.0"), ("draining", "2.0"), ("stopped", "0.0")]:
        adapter.update(_make_snapshot(status=status_str))
        text = _render(registry)
        assert f'airweave_worker_status{{worker_id="0"}} {expected_value}' in text


def test_connector_metrics():
    adapter, registry = _make_adapter()
    adapter.update(
        _make_snapshot(
            connector_metrics={
                "slack": ConnectorSnapshot(active_syncs=5, active_and_pending_workers=50),
                "notion": ConnectorSnapshot(active_syncs=3, active_and_pending_workers=30),
            }
        )
    )

    text = _render(registry)
    assert "airweave_worker_pool_active_and_pending_by_connector" in text
    assert "airweave_worker_active_syncs_by_connector" in text
    assert 'connector_type="slack"' in text
    assert 'connector_type="notion"' in text


def test_finished_connectors_zeroed_out():
    adapter, registry = _make_adapter()

    # First scrape: slack + notion active
    adapter.update(
        _make_snapshot(
            connector_metrics={
                "slack": ConnectorSnapshot(active_syncs=3, active_and_pending_workers=30),
                "notion": ConnectorSnapshot(active_syncs=2, active_and_pending_workers=20),
            }
        )
    )

    # Second scrape: only slack (notion finished)
    adapter.update(
        _make_snapshot(
            connector_metrics={
                "slack": ConnectorSnapshot(active_syncs=3, active_and_pending_workers=30),
            }
        )
    )

    text = _render(registry)
    lines = text.split("\n")
    notion_lines = [
        line for line in lines if 'connector_type="notion"' in line and not line.startswith("#")
    ]
    for line in notion_lines:
        assert line.endswith(" 0.0")


def test_multiple_workers():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(worker_id="0", uptime_seconds=100.0))
    adapter.update(_make_snapshot(worker_id="1", uptime_seconds=200.0))

    text = _render(registry)
    assert 'worker_id="0"' in text
    assert 'worker_id="1"' in text


def test_config_value_gauges():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(sync_max_workers=25, thread_pool_size=150))

    text = _render(registry)
    assert 'airweave_worker_sync_max_workers_config{worker_id="0"} 25.0' in text
    assert 'airweave_worker_thread_pool_size_config{worker_id="0"} 150.0' in text


def test_thread_pool_active():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(thread_pool_active=42))

    text = _render(registry)
    assert 'airweave_worker_thread_pool_active{worker_id="0"} 42.0' in text


def test_worker_pool_active_and_pending():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(worker_pool_active_and_pending_count=35))

    text = _render(registry)
    assert 'airweave_worker_pool_active_and_pending_workers{worker_id="0"} 35.0' in text


def test_process_collector_registered():
    adapter, registry = _make_adapter()
    collectors = list(registry._collector_to_names.keys())
    assert any(isinstance(c, ProcessCollector) for c in collectors)


def test_worker_info_metric():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot())

    text = _render(registry)
    assert "airweave_worker_info" in text


def test_empty_connector_metrics():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(connector_metrics={}))

    text = _render(registry)
    assert "airweave_worker" in text


def test_zero_values():
    adapter, registry = _make_adapter()
    adapter.update(
        _make_snapshot(
            uptime_seconds=0.0,
            active_activities_count=0,
            active_sync_jobs_count=0,
            worker_pool_active_and_pending_count=0,
            thread_pool_active=0,
        )
    )

    text = _render(registry)
    assert 'airweave_worker_active_activities{worker_id="0"} 0.0' in text
    assert 'airweave_worker_active_sync_jobs{worker_id="0"} 0.0' in text


def test_no_high_cardinality_labels():
    adapter, registry = _make_adapter()
    adapter.update(
        _make_snapshot(
            connector_metrics={
                "slack": ConnectorSnapshot(active_syncs=50, active_and_pending_workers=500),
            }
        )
    )

    text = _render(registry)
    assert "sync_job_id=" not in text
    assert "sync_id=" not in text
    assert "worker_id=" in text
    assert "connector_type=" in text


def test_special_characters_in_connector_names():
    adapter, registry = _make_adapter()
    adapter.update(
        _make_snapshot(
            connector_metrics={
                "google_drive": ConnectorSnapshot(active_syncs=1, active_and_pending_workers=10),
                "microsoft-365": ConnectorSnapshot(active_syncs=1, active_and_pending_workers=5),
            }
        )
    )

    text = _render(registry)
    assert "google_drive" in text


def test_registry_isolation():
    from prometheus_client import REGISTRY as default_registry

    adapter, registry = _make_adapter()
    assert registry is not default_registry


def test_metrics_format_is_prometheus_compliant():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot())

    text = _render(registry)
    assert "# HELP" in text
    assert "# TYPE" in text

    lines = text.split("\n")
    metric_lines = [line for line in lines if line and not line.startswith("#")]
    for line in metric_lines:
        assert "{" in line or " " in line


def test_fractional_uptime_precision():
    adapter, registry = _make_adapter()
    adapter.update(_make_snapshot(uptime_seconds=3600.123456))

    text = _render(registry)
    assert "airweave_worker_uptime_seconds" in text
    assert "3600.12" in text or "3600.123" in text
