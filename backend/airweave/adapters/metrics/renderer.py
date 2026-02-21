"""Metrics renderer adapters (Prometheus + Fake).

Prometheus implementation wraps a CollectorRegistry so the metrics server
can serialize all registered collectors into Prometheus text exposition
format.
"""

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest

from airweave.core.protocols.metrics import MetricsRenderer


class PrometheusMetricsRenderer(MetricsRenderer):
    """Render all metrics in a shared CollectorRegistry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._registry = registry

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST

    def generate(self) -> bytes:
        return generate_latest(self._registry)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------


class FakeMetricsRenderer(MetricsRenderer):
    """In-memory spy implementing the MetricsRenderer protocol."""

    def __init__(self) -> None:
        self.generate_calls: int = 0

    @property
    def content_type(self) -> str:
        return "text/plain"

    def generate(self) -> bytes:
        self.generate_calls += 1
        return b"# fake metrics\n"
