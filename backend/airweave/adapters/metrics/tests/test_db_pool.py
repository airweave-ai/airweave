"""Unit tests for DB pool metrics adapters."""

from airweave.adapters.metrics import FakeDbPoolMetrics, PrometheusDbPoolMetrics


# ---------------------------------------------------------------------------
# FakeDbPoolMetrics
# ---------------------------------------------------------------------------


class TestFakeDbPoolMetrics:
    """Tests for the FakeDbPoolMetrics test helper."""

    def test_update_records_values(self):
        fake = FakeDbPoolMetrics()
        fake.update(pool_size=20, checked_out=5, checked_in=15, overflow=0)

        assert fake.pool_size == 20
        assert fake.checked_out == 5
        assert fake.checked_in == 15
        assert fake.overflow == 0
        assert fake.update_count == 1

    def test_clear_resets_all_state(self):
        fake = FakeDbPoolMetrics()
        fake.update(pool_size=20, checked_out=5, checked_in=15, overflow=0)
        fake.clear()

        assert fake.pool_size is None
        assert fake.checked_out is None
        assert fake.checked_in is None
        assert fake.overflow is None
        assert fake.update_count == 0


# ---------------------------------------------------------------------------
# PrometheusDbPoolMetrics
# ---------------------------------------------------------------------------


class TestPrometheusDbPoolMetrics:
    """Tests for the Prometheus adapter."""

    def test_registry_is_separate_from_default(self):
        from prometheus_client import REGISTRY

        adapter = PrometheusDbPoolMetrics()
        assert adapter._registry is not REGISTRY

    def test_update_sets_gauges(self):
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        adapter = PrometheusDbPoolMetrics(registry=registry, max_overflow=40)

        adapter.update(pool_size=20, checked_out=5, checked_in=15, overflow=2)
        output = generate_latest(registry).decode()

        assert "airweave_db_pool_size 20.0" in output
        assert "airweave_db_pool_checked_out 5.0" in output
        assert "airweave_db_pool_checked_in 15.0" in output
        assert "airweave_db_pool_overflow 2.0" in output
        assert "airweave_db_pool_max_overflow 40.0" in output

    def test_max_overflow_set_once(self):
        """max_overflow gauge should reflect the constructor arg."""
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        PrometheusDbPoolMetrics(registry=registry, max_overflow=99)

        output = generate_latest(registry).decode()
        assert "airweave_db_pool_max_overflow 99.0" in output

    def test_update_overwrites_previous(self):
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        adapter = PrometheusDbPoolMetrics(registry=registry)

        adapter.update(pool_size=10, checked_out=1, checked_in=9, overflow=0)
        adapter.update(pool_size=20, checked_out=8, checked_in=12, overflow=3)

        output = generate_latest(registry).decode()
        assert "airweave_db_pool_size 20.0" in output
        assert "airweave_db_pool_checked_out 8.0" in output
