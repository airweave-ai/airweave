"""Internal HTTP server that exposes Prometheus metrics on a separate port.

This keeps the /metrics endpoint off the public API surface. In Kubernetes
only a ServiceMonitor targets this port — the public ingress never sees it.

Follows the same aiohttp pattern as the Temporal worker control server
(platform/temporal/worker/control_server.py).
"""

from aiohttp import web

from airweave.core.logging import logger
from airweave.core.protocols.metrics import MetricsRenderer


class MetricsServer:
    """Lightweight aiohttp server serving /metrics for Prometheus scraping."""

    def __init__(self, renderer: MetricsRenderer, port: int, host: str = "0.0.0.0") -> None:
        """Initialize the metrics server on the given host and port."""
        self._renderer = renderer
        self._port = port
        self._host = host
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Start the metrics server."""
        app = web.Application()
        app.router.add_get("/metrics", self._handle_metrics)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("Metrics server started on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        """Stop the metrics server."""
        if self._runner:
            await self._runner.cleanup()

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Return Prometheus metrics in text exposition format."""
        return web.Response(
            body=self._renderer.generate(),
            content_type=self._renderer.content_type,
        )
