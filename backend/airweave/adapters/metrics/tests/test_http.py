"""Unit tests for HTTP metrics adapters and renderer."""

import pytest

from airweave.adapters.metrics import FakeHttpMetrics, FakeMetricsRenderer, PrometheusHttpMetrics
from airweave.adapters.metrics.renderer import _parse_content_type


class TestParseContentType:
    """Tests for the _parse_content_type helper."""

    def test_standard_prometheus_content_type(self):
        ct, charset = _parse_content_type("text/plain; version=0.0.4; charset=utf-8")
        assert ct == "text/plain; version=0.0.4"
        assert charset == "utf-8"

    def test_no_charset_defaults_to_utf8(self):
        ct, charset = _parse_content_type("text/plain; version=0.0.4")
        assert ct == "text/plain; version=0.0.4"
        assert charset == "utf-8"

    def test_charset_is_case_insensitive(self):
        ct, charset = _parse_content_type("text/plain; Charset=UTF-8")
        assert ct == "text/plain"
        assert charset == "UTF-8"

    def test_bare_media_type(self):
        ct, charset = _parse_content_type("application/json")
        assert ct == "application/json"
        assert charset == "utf-8"


class TestFakeHttpMetrics:
    """Tests for the FakeHttpMetrics test helper."""

    def test_clear_resets_all_state(self):
        """clear() should empty every collection."""
        fake = FakeHttpMetrics()
        fake.inc_in_progress("GET")
        fake.observe_request("GET", "/test", "200", 0.01)
        fake.observe_response_size("GET", "/test", 512)

        fake.clear()

        assert fake.in_progress == {}
        assert fake.requests == []
        assert fake.response_sizes == []


class TestPrometheusHttpMetrics:
    """Tests for the Prometheus adapter."""

    def test_registry_is_separate_from_default(self):
        """Adapter registry must not be the default global registry."""
        from prometheus_client import REGISTRY

        adapter = PrometheusHttpMetrics()
        assert adapter._registry is not REGISTRY

    def test_observe_request_increments_counter(self):
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        adapter = PrometheusHttpMetrics(registry=registry)
        adapter.observe_request("POST", "/api/v1/items", "201", 0.05)
        adapter.observe_request("POST", "/api/v1/items", "201", 0.03)

        output = generate_latest(registry).decode()
        assert (
            'airweave_http_requests_total{endpoint="/api/v1/items",method="POST",status_code="201"} 2.0'
            in output
        )

    def test_in_progress_gauge(self):
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        adapter = PrometheusHttpMetrics(registry=registry)
        adapter.inc_in_progress("GET")
        adapter.inc_in_progress("GET")
        adapter.dec_in_progress("GET")

        output = generate_latest(registry).decode()
        assert 'airweave_http_requests_in_progress{method="GET"} 1.0' in output

    def test_observe_response_size(self):
        from prometheus_client import CollectorRegistry, generate_latest

        registry = CollectorRegistry()
        adapter = PrometheusHttpMetrics(registry=registry)
        adapter.observe_response_size("GET", "/api/v1/items", 1234)

        output = generate_latest(registry).decode()
        assert "airweave_http_response_size_bytes" in output


class TestPrometheusMetricsRenderer:
    """Tests for the PrometheusMetricsRenderer."""

    def test_generate_returns_bytes(self):
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer

        registry = CollectorRegistry()
        renderer = PrometheusMetricsRenderer(registry=registry)
        assert isinstance(renderer.generate(), bytes)

    def test_content_type_is_prometheus_format(self):
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer

        registry = CollectorRegistry()
        renderer = PrometheusMetricsRenderer(registry=registry)
        assert renderer.content_type == "text/plain; version=0.0.4"

    def test_charset_is_utf8(self):
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer

        registry = CollectorRegistry()
        renderer = PrometheusMetricsRenderer(registry=registry)
        assert renderer.charset == "utf-8"

    def test_content_type_excludes_charset(self):
        """content_type must not contain charset — aiohttp adds it separately."""
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer

        registry = CollectorRegistry()
        renderer = PrometheusMetricsRenderer(registry=registry)
        assert "charset" not in renderer.content_type

    def test_renders_metrics_from_shared_registry(self):
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer

        registry = CollectorRegistry()
        http = PrometheusHttpMetrics(registry=registry)
        renderer = PrometheusMetricsRenderer(registry=registry)

        http.observe_request("GET", "/test", "200", 0.01)
        output = renderer.generate().decode()
        assert "airweave_http_requests_total" in output


class TestFakeMetricsRenderer:
    """Tests for the FakeMetricsRenderer test double."""

    def test_content_type(self):
        from airweave.adapters.metrics import FakeMetricsRenderer

        renderer = FakeMetricsRenderer()
        assert renderer.content_type == "text/plain"

    def test_charset(self):
        from airweave.adapters.metrics import FakeMetricsRenderer

        renderer = FakeMetricsRenderer()
        assert renderer.charset == "utf-8"
