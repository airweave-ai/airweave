"""HTTP metrics adapters (Prometheus + Fake).

Prometheus implementation creates a dedicated CollectorRegistry so API
metrics are isolated from the default global registry.
"""

from dataclasses import dataclass

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)

from airweave.core.protocols.metrics import HttpMetrics

_RESPONSE_SIZE_BUCKETS = (
    100,
    500,
    1_000,
    5_000,
    10_000,
    50_000,
    100_000,
    500_000,
    1_000_000,
)


class PrometheusHttpMetrics(HttpMetrics):
    """Prometheus-backed HTTP metrics collection."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or CollectorRegistry()

        self._requests_total = Counter(
            "airweave_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self._registry,
        )

        self._request_duration = Histogram(
            "airweave_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            registry=self._registry,
        )

        self._in_progress = Gauge(
            "airweave_http_requests_in_progress",
            "Number of HTTP requests currently in progress",
            ["method"],
            registry=self._registry,
        )

        self._response_size = Histogram(
            "airweave_http_response_size_bytes",
            "HTTP response size in bytes",
            ["method", "endpoint"],
            buckets=_RESPONSE_SIZE_BUCKETS,
            registry=self._registry,
        )

    # -- HttpMetrics protocol methods --

    def inc_in_progress(self, method: str) -> None:
        self._in_progress.labels(method=method).inc()

    def dec_in_progress(self, method: str) -> None:
        self._in_progress.labels(method=method).dec()

    def observe_request(
        self,
        method: str,
        endpoint: str,
        status_code: str,
        duration: float,
    ) -> None:
        self._requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        ).inc()
        self._request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def observe_response_size(self, method: str, endpoint: str, size: int) -> None:
        self._response_size.labels(method=method, endpoint=endpoint).observe(size)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------


@dataclass
class RequestRecord:
    """Single observed request."""

    method: str
    endpoint: str
    status_code: str
    duration: float


@dataclass
class ResponseSizeRecord:
    """Single observed response size."""

    method: str
    endpoint: str
    size: int


class FakeHttpMetrics(HttpMetrics):
    """In-memory spy implementing the HttpMetrics protocol."""

    def __init__(self) -> None:
        self.in_progress: dict[str, int] = {}
        self.requests: list[RequestRecord] = []
        self.response_sizes: list[ResponseSizeRecord] = []

    def inc_in_progress(self, method: str) -> None:
        self.in_progress[method] = self.in_progress.get(method, 0) + 1

    def dec_in_progress(self, method: str) -> None:
        self.in_progress[method] = self.in_progress.get(method, 0) - 1

    def observe_request(
        self,
        method: str,
        endpoint: str,
        status_code: str,
        duration: float,
    ) -> None:
        self.requests.append(RequestRecord(method, endpoint, status_code, duration))

    def observe_response_size(self, method: str, endpoint: str, size: int) -> None:
        self.response_sizes.append(ResponseSizeRecord(method, endpoint, size))

    # -- test helpers --

    def clear(self) -> None:
        """Reset all recorded state."""
        self.in_progress.clear()
        self.requests.clear()
        self.response_sizes.clear()
