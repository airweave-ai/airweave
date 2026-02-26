"""Unit tests for the MetricsServer handler."""

import pytest

from airweave.adapters.metrics import FakeMetricsRenderer


class TestMetricsServer:
    """Tests for the MetricsServer handler."""

    @pytest.mark.asyncio
    async def test_handle_metrics_returns_fake_body_and_content_type(self):
        """Handler should delegate to MetricsRenderer.generate() and content_type."""
        from aiohttp.test_utils import make_mocked_request

        from airweave.api.metrics import MetricsServer

        fake = FakeMetricsRenderer()
        server = MetricsServer(fake, port=0)

        request = make_mocked_request("GET", "/metrics")
        response = await server._handle_metrics(request)

        assert response.body == b"# fake metrics\n"
        assert response.content_type == "text/plain"
        assert response.charset == "utf-8"
        assert fake.generate_calls == 1

    @pytest.mark.asyncio
    async def test_start_and_stop_serves_metrics(self):
        """A started server should respond with metrics on /metrics."""
        import aiohttp

        from airweave.api.metrics import MetricsServer

        fake = FakeMetricsRenderer()
        server = MetricsServer(fake, port=0)
        await server.start()

        try:
            # Extract the OS-assigned port from the runner's sites.
            site = list(server._runner.sites)[0]
            sock = site._server.sockets[0]
            port = sock.getsockname()[1]

            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/metrics") as resp:
                    assert resp.status == 200
                    body = await resp.read()
                    assert body == b"# fake metrics\n"
                    ct = resp.headers["Content-Type"]
                    assert ct.count("charset") == 1
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_prometheus_renderer_serves_without_duplicate_charset(self):
        """Real PrometheusMetricsRenderer must not cause a 500."""
        import aiohttp
        from prometheus_client import CollectorRegistry

        from airweave.adapters.metrics import PrometheusMetricsRenderer
        from airweave.api.metrics import MetricsServer

        registry = CollectorRegistry()
        renderer = PrometheusMetricsRenderer(registry=registry)
        server = MetricsServer(renderer, port=0)
        await server.start()

        try:
            site = list(server._runner.sites)[0]
            port = site._server.sockets[0].getsockname()[1]

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{port}/metrics"
                ) as resp:
                    assert resp.status == 200
                    ct = resp.headers["Content-Type"]
                    assert ct.count("charset") == 1
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_not_started(self):
        """Calling stop() before start() must not raise."""
        from airweave.api.metrics import MetricsServer

        fake = FakeMetricsRenderer()
        server = MetricsServer(fake, port=0)
        await server.stop()  # Should be a no-op
