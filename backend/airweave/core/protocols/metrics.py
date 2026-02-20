"""Metrics protocols for dependency injection.

Consolidates all metrics-related protocols into a single module:
- HttpMetrics: HTTP request/response instrumentation
- AgenticSearchMetrics: agentic search pipeline instrumentation
- DbPoolMetrics: database connection pool gauges
- WorkerMetrics: Temporal worker gauge instrumentation
- MetricsRenderer: metrics serialization for scraping
- MetricsService: facade that owns all metrics adapters
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from airweave.platform.temporal.worker_metrics_snapshot import WorkerMetricsSnapshot


# ---------------------------------------------------------------------------
# DbPool
# ---------------------------------------------------------------------------


class DbPool(Protocol):
    """Structural protocol for a SQLAlchemy-style connection pool."""

    def size(self) -> int: ...
    def checkedout(self) -> int: ...
    def checkedin(self) -> int: ...
    def overflow(self) -> int: ...


# ---------------------------------------------------------------------------
# HttpMetrics
# ---------------------------------------------------------------------------


@runtime_checkable
class HttpMetrics(Protocol):
    """Protocol for HTTP request/response metrics collection."""

    def inc_in_progress(self, method: str) -> None:
        """Increment the in-progress gauge for the given HTTP method."""
        ...

    def dec_in_progress(self, method: str) -> None:
        """Decrement the in-progress gauge for the given HTTP method."""
        ...

    def observe_request(
        self,
        method: str,
        endpoint: str,
        status_code: str,
        duration: float,
    ) -> None:
        """Record a completed request (count + latency).

        Args:
            method: HTTP method (GET, POST, …).
            endpoint: Route path template.
            status_code: Response status code as a string.
            duration: Request duration in seconds.
        """
        ...

    def observe_response_size(
        self,
        method: str,
        endpoint: str,
        size: int,
    ) -> None:
        """Record the response body size in bytes."""
        ...


# ---------------------------------------------------------------------------
# AgenticSearchMetrics
# ---------------------------------------------------------------------------


@runtime_checkable
class AgenticSearchMetrics(Protocol):
    """Protocol for agentic search metrics collection."""

    def inc_search_requests(self, mode: str, streaming: bool) -> None:
        """Increment the search-requests counter."""
        ...

    def inc_search_errors(self, mode: str, streaming: bool) -> None:
        """Increment the search-errors counter."""
        ...

    def observe_iterations(self, mode: str, count: int) -> None:
        """Record how many iterations an agentic search took."""
        ...

    def observe_step_duration(self, step: str, duration: float) -> None:
        """Record the duration of a single pipeline step in seconds.

        Args:
            step: One of ``plan``, ``embed``, ``search``, ``evaluate``,
                ``compose``.
            duration: Duration in seconds.
        """
        ...

    def observe_results_per_search(self, count: int) -> None:
        """Record the number of results returned by a search."""
        ...

    def observe_duration(self, mode: str, duration: float) -> None:
        """Record end-to-end search duration in seconds."""
        ...


# ---------------------------------------------------------------------------
# DbPoolMetrics
# ---------------------------------------------------------------------------


@runtime_checkable
class DbPoolMetrics(Protocol):
    """Protocol for database connection pool metrics collection."""

    def update(
        self,
        *,
        pool_size: int,
        checked_out: int,
        checked_in: int,
        overflow: int,
    ) -> None:
        """Push a snapshot of pool gauges from a single sampling tick.

        Args:
            pool_size: Current pool size (``pool.size()``).
            checked_out: Connections currently checked out.
            checked_in: Idle connections available in the pool.
            overflow: Connections currently in overflow.
        """
        ...


# ---------------------------------------------------------------------------
# WorkerMetrics
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkerMetrics(Protocol):
    """Protocol for updating Temporal worker Prometheus gauges."""

    def update(self, snapshot: WorkerMetricsSnapshot) -> None:
        """Push a complete worker metrics snapshot to the gauge backend."""
        ...


# ---------------------------------------------------------------------------
# MetricsRenderer
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricsRenderer(Protocol):
    """Protocol for rendering collected metrics into a scrapeable format."""

    @property
    def content_type(self) -> str:
        """MIME type for the serialized metrics output."""
        ...

    def generate(self) -> bytes:
        """Serialize all collected metrics into the wire format."""
        ...


# ---------------------------------------------------------------------------
# MetricsService
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricsService(Protocol):
    """Protocol for the metrics facade.

    Public attributes (``http``, ``agentic_search``, ``db_pool``) are typed
    with their respective protocols so ``Inject()`` in deps.py can resolve
    them via nested attribute lookup.
    """

    http: HttpMetrics
    agentic_search: AgenticSearchMetrics
    db_pool: DbPoolMetrics

    async def start(self, *, pool: DbPool) -> None:
        """Start the metrics sidecar server and background samplers."""
        ...

    async def stop(self) -> None:
        """Stop all background services."""
        ...
