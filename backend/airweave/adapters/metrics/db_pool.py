"""DB pool metrics adapters (Prometheus + Fake).

Prometheus implementation exposes five gauges on the shared
CollectorRegistry for connection pool state.
"""

from prometheus_client import CollectorRegistry, Gauge

from airweave.core.protocols.metrics import DbPoolMetrics


class PrometheusDbPoolMetrics(DbPoolMetrics):
    """Prometheus-backed DB connection pool metrics."""

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        max_overflow: int = 0,
    ) -> None:
        self._registry = registry or CollectorRegistry()

        self._pool_size = Gauge(
            "airweave_db_pool_size",
            "Current size of the connection pool",
            registry=self._registry,
        )

        self._max_overflow = Gauge(
            "airweave_db_pool_max_overflow",
            "Maximum overflow connections allowed",
            registry=self._registry,
        )

        self._checked_out = Gauge(
            "airweave_db_pool_checked_out",
            "Connections currently checked out from the pool",
            registry=self._registry,
        )

        self._checked_in = Gauge(
            "airweave_db_pool_checked_in",
            "Idle connections available in the pool",
            registry=self._registry,
        )

        self._overflow = Gauge(
            "airweave_db_pool_overflow",
            "Connections currently in overflow",
            registry=self._registry,
        )

        # Static value — set once.
        self._max_overflow.set(max_overflow)

    # -- DbPoolMetrics protocol method --

    def update(
        self,
        *,
        pool_size: int,
        checked_out: int,
        checked_in: int,
        overflow: int,
    ) -> None:
        self._pool_size.set(pool_size)
        self._checked_out.set(checked_out)
        self._checked_in.set(checked_in)
        self._overflow.set(overflow)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------


class FakeDbPoolMetrics(DbPoolMetrics):
    """In-memory spy implementing the DbPoolMetrics protocol."""

    def __init__(self) -> None:
        self.pool_size: int | None = None
        self.checked_out: int | None = None
        self.checked_in: int | None = None
        self.overflow: int | None = None
        self.update_count: int = 0

    def update(
        self,
        *,
        pool_size: int,
        checked_out: int,
        checked_in: int,
        overflow: int,
    ) -> None:
        self.pool_size = pool_size
        self.checked_out = checked_out
        self.checked_in = checked_in
        self.overflow = overflow
        self.update_count += 1

    # -- test helpers --

    def clear(self) -> None:
        """Reset all recorded state."""
        self.pool_size = None
        self.checked_out = None
        self.checked_in = None
        self.overflow = None
        self.update_count = 0
