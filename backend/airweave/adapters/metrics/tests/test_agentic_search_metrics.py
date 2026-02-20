"""Unit tests for agentic search metrics adapter."""

import pytest
from prometheus_client import generate_latest

from airweave.adapters.metrics import FakeAgenticSearchMetrics, PrometheusAgenticSearchMetrics


class TestFakeAgenticSearchMetrics:
    """Tests for the FakeAgenticSearchMetrics test helper."""

    def test_inc_search_requests(self):
        fake = FakeAgenticSearchMetrics()
        fake.inc_search_requests("thinking", True)
        fake.inc_search_requests("fast", False)
        assert fake.search_requests == [("thinking", True), ("fast", False)]

    def test_inc_search_errors(self):
        fake = FakeAgenticSearchMetrics()
        fake.inc_search_errors("thinking", True)
        assert fake.search_errors == [("thinking", True)]

    def test_observe_iterations(self):
        fake = FakeAgenticSearchMetrics()
        fake.observe_iterations("thinking", 3)
        assert fake.iterations == [("thinking", 3)]

    def test_observe_step_duration(self):
        fake = FakeAgenticSearchMetrics()
        fake.observe_step_duration("plan", 0.5)
        fake.observe_step_duration("search", 1.2)
        assert len(fake.step_durations) == 2
        assert fake.step_durations[0].step == "plan"
        assert fake.step_durations[0].duration == 0.5

    def test_observe_results_per_search(self):
        fake = FakeAgenticSearchMetrics()
        fake.observe_results_per_search(10)
        assert fake.results_counts == [10]

    def test_observe_duration(self):
        fake = FakeAgenticSearchMetrics()
        fake.observe_duration("thinking", 1.5)
        fake.observe_duration("fast", 0.3)
        assert fake.durations == [("thinking", 1.5), ("fast", 0.3)]

    def test_clear_resets_all_state(self):
        fake = FakeAgenticSearchMetrics()
        fake.inc_search_requests("fast", False)
        fake.inc_search_errors("fast", False)
        fake.observe_iterations("fast", 1)
        fake.observe_step_duration("plan", 0.1)
        fake.observe_results_per_search(5)
        fake.observe_duration("fast", 0.5)

        fake.clear()

        assert fake.search_requests == []
        assert fake.search_errors == []
        assert fake.iterations == []
        assert fake.step_durations == []
        assert fake.results_counts == []
        assert fake.durations == []


class TestPrometheusAgenticSearchMetrics:
    """Tests for the Prometheus adapter."""

    def test_registry_is_separate_from_default(self):
        from prometheus_client import REGISTRY

        adapter = PrometheusAgenticSearchMetrics()
        assert adapter._registry is not REGISTRY

    def test_accepts_custom_registry(self):
        from prometheus_client import CollectorRegistry

        registry = CollectorRegistry()
        adapter = PrometheusAgenticSearchMetrics(registry=registry)
        assert adapter._registry is registry

    def test_generate_contains_expected_families(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.inc_search_requests("thinking", True)
        adapter.observe_step_duration("plan", 0.1)

        output = generate_latest(adapter._registry).decode()
        assert "airweave_agentic_search_requests_total" in output
        assert "airweave_agentic_search_errors_total" in output
        assert "airweave_agentic_search_iterations" in output
        assert "airweave_agentic_search_step_duration_seconds" in output
        assert "airweave_agentic_search_results_per_search" in output
        assert "airweave_agentic_search_duration_seconds" in output

    def test_inc_search_requests_increments_counter(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.inc_search_requests("thinking", True)
        adapter.inc_search_requests("thinking", True)

        output = generate_latest(adapter._registry).decode()
        assert (
            'airweave_agentic_search_requests_total'
            '{mode="thinking",streaming="true"} 2.0' in output
        )

    def test_inc_search_errors_increments_counter(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.inc_search_errors("fast", False)

        output = generate_latest(adapter._registry).decode()
        assert (
            'airweave_agentic_search_errors_total'
            '{mode="fast",streaming="false"} 1.0' in output
        )

    def test_observe_iterations(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.observe_iterations("thinking", 3)

        output = generate_latest(adapter._registry).decode()
        assert 'airweave_agentic_search_iterations_count{mode="thinking"} 1.0' in output

    def test_observe_step_duration(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.observe_step_duration("plan", 0.05)

        output = generate_latest(adapter._registry).decode()
        assert 'airweave_agentic_search_step_duration_seconds_count{step="plan"} 1.0' in output

    def test_observe_results_per_search(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.observe_results_per_search(25)

        output = generate_latest(adapter._registry).decode()
        assert "airweave_agentic_search_results_per_search_count 1.0" in output

    def test_observe_duration(self):
        adapter = PrometheusAgenticSearchMetrics()
        adapter.observe_duration("thinking", 2.5)

        output = generate_latest(adapter._registry).decode()
        assert (
            'airweave_agentic_search_duration_seconds_count{mode="thinking"} 1.0'
            in output
        )

    def test_shared_registry_merges_metrics(self):
        """Both HTTP and agentic search metrics appear in a shared registry."""
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusHttpMetrics

        registry = CollectorRegistry()
        http = PrometheusHttpMetrics(registry=registry)
        agentic = PrometheusAgenticSearchMetrics(registry=registry)

        http.observe_request("GET", "/test", "200", 0.01)
        agentic.inc_search_requests("fast", False)

        output = generate_latest(registry).decode()
        assert "airweave_http_requests_total" in output
        assert "airweave_agentic_search_requests_total" in output
