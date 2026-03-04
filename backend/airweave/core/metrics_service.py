"""Prometheus-backed MetricsService implementation.

Composes the metrics adapters, the sidecar HTTP server, and the DB pool
sampler behind a single lifecycle API so callers (main.py, tests) only
deal with one object instead of four adapters + two background services.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from airweave.api.metrics import MetricsServer
from airweave.core.db_pool_sampler import DbPoolSampler
from airweave.core.protocols.metrics import (
    AgenticSearchMetrics,
    DbPool,
    DbPoolMetrics,
    HttpMetrics,
    MetricsRenderer,
    MetricsService,
)


class PrometheusMetricsService(MetricsService):
    """Prometheus-backed facade that owns all metrics adapters and background services.

    Satisfies the ``MetricsService`` protocol structurally.

    Public attributes (``http``, ``agentic_search``, ``db_pool``) are
    typed with their respective protocols so ``Inject()`` in deps.py can
    resolve them via nested attribute lookup.

    ``_renderer`` is private to prevent accidental injection — it is an
    implementation detail of the sidecar server.
    """

    http: HttpMetrics
    agentic_search: AgenticSearchMetrics
    db_pool: DbPoolMetrics

    def __init__(
        self,
        http: HttpMetrics,
        agentic_search: AgenticSearchMetrics,
        db_pool: DbPoolMetrics,
        renderer: MetricsRenderer,
        host: str,
        port: int,
    ) -> None:
        self.http = http
        self.agentic_search = agentic_search
        self.db_pool = db_pool
        self._renderer = renderer
        self._host = host
        self._port = port
        self._server: MetricsServer | None = None
        self._sampler: DbPoolSampler | None = None

    async def start(self, *, pool: DbPool) -> None:
        """Start the sidecar metrics server and the DB pool sampler."""
        self._server = MetricsServer(self._renderer, self._port, self._host)
        await self._server.start()
        self._sampler = DbPoolSampler(pool=pool, metrics=self.db_pool)
        await self._sampler.start()

    async def stop(self) -> None:
        """Stop sampler then sidecar (reverse start order)."""
        try:
            if self._sampler:
                await self._sampler.stop()
        finally:
            if self._server:
                await self._server.stop()


@asynccontextmanager
async def metrics_lifespan(
    app: FastAPI,
    metrics: MetricsService,
    pool: DbPool,
) -> AsyncGenerator[None, None]:
    """Wire HTTP metrics onto ``app.state`` and manage the metrics lifecycle.

    Intended for use inside ``main.py``'s lifespan context manager so the
    FastAPI-specific wiring stays outside the ``MetricsService`` protocol.
    """
    app.state.http_metrics = metrics.http
    await metrics.start(pool=pool)
    try:
        yield
    finally:
        await metrics.stop()
