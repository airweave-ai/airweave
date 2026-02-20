"""Unit tests for HTTP metrics middleware."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.adapters.metrics import FakeHttpMetrics


class TestHttpMetricsMiddleware:
    """Tests for http_metrics_middleware using FakeHttpMetrics."""

    @pytest.fixture
    def fake_metrics(self):
        return FakeHttpMetrics()

    @pytest.fixture
    def _make_request(self, fake_metrics):
        """Factory for mock Starlette Request objects with fake metrics."""

        def factory(path: str = "/api/v1/sources", method: str = "GET"):
            request = MagicMock()
            request.url.path = path
            request.method = method
            request.app.state.http_metrics = fake_metrics
            route = MagicMock()
            route.path = path
            request.scope = {"route": route}
            return request

        return factory

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        ["/health", "/metrics", "/docs", "/openapi.json", "/favicon.ico", "/redoc"],
    )
    async def test_skips_metrics_exempt_path(self, _make_request, fake_metrics, path):
        """Middleware should pass through every _METRICS_SKIP_PATHS entry without recording."""
        from airweave.api.middleware import http_metrics_middleware

        request = _make_request(path=path)
        sentinel = MagicMock()
        call_next = AsyncMock(return_value=sentinel)

        response = await http_metrics_middleware(request, call_next)

        assert response is sentinel
        call_next.assert_awaited_once_with(request)
        assert len(fake_metrics.requests) == 0

    @pytest.mark.asyncio
    async def test_records_metrics_for_normal_request(self, _make_request, fake_metrics):
        """Middleware should record request via the HttpMetrics protocol."""
        from airweave.api.middleware import http_metrics_middleware

        request = _make_request(path="/api/v1/sources", method="GET")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "1234"}
        call_next = AsyncMock(return_value=mock_response)

        response = await http_metrics_middleware(request, call_next)

        assert response is mock_response
        assert len(fake_metrics.requests) == 1

        rec = fake_metrics.requests[0]
        assert rec.method == "GET"
        assert rec.endpoint == "/api/v1/sources"
        assert rec.status_code == "200"
        assert rec.duration > 0

        assert len(fake_metrics.response_sizes) == 1
        assert fake_metrics.response_sizes[0].size == 1234

    @pytest.mark.asyncio
    async def test_decrements_in_progress_on_exception(self, _make_request, fake_metrics):
        """In-progress gauge must be decremented even when call_next raises."""
        from airweave.api.middleware import http_metrics_middleware

        request = _make_request(path="/api/v1/fail", method="POST")
        call_next = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            await http_metrics_middleware(request, call_next)

        # inc was called once, dec was called once → net zero
        assert fake_metrics.in_progress.get("POST", 0) == 0

    @pytest.mark.asyncio
    async def test_unmatched_route_uses_fallback(self, fake_metrics):
        """When no route is matched, endpoint label should be 'unmatched'."""
        from airweave.api.middleware import http_metrics_middleware

        request = MagicMock()
        request.url.path = "/random-bot-path"
        request.method = "GET"
        request.scope = {}  # No route matched
        request.app.state.http_metrics = fake_metrics

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-length": "0"}
        call_next = AsyncMock(return_value=mock_response)

        await http_metrics_middleware(request, call_next)

        assert len(fake_metrics.requests) == 1
        assert fake_metrics.requests[0].endpoint == "unmatched"
        assert fake_metrics.requests[0].status_code == "404"

    @pytest.mark.asyncio
    async def test_streaming_branch_when_content_length_absent(self, _make_request, fake_metrics):
        """Missing content-length enters the streaming branch; no metrics until consumed."""
        from airweave.api.middleware import http_metrics_middleware

        request = _make_request(path="/api/v1/items", method="GET")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        await http_metrics_middleware(request, call_next)

        # No metrics recorded yet — body iterator hasn't been consumed
        assert len(fake_metrics.requests) == 0
        assert len(fake_metrics.response_sizes) == 0


class TestHttpMetricsMiddlewareStreaming:
    """Tests for streaming-response handling in http_metrics_middleware."""

    @pytest.fixture
    def fake_metrics(self):
        return FakeHttpMetrics()

    @pytest.fixture
    def _make_streaming_request(self, fake_metrics):
        """Factory for mock requests that return a streaming response (no content-length)."""

        def factory(path: str = "/api/v1/stream", method: str = "GET", chunks=None):
            request = MagicMock()
            request.url.path = path
            request.method = method
            request.app.state.http_metrics = fake_metrics
            route = MagicMock()
            route.path = path
            request.scope = {"route": route}

            if chunks is None:
                chunks = [b"chunk1", b"chunk2"]

            async def body_iter():
                for chunk in chunks:
                    yield chunk

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}  # No content-length → streaming
            mock_response.body_iterator = body_iter()

            call_next = AsyncMock(return_value=mock_response)
            return request, call_next, mock_response

        return factory

    @pytest.mark.asyncio
    async def test_streaming_defers_metrics_until_body_consumed(
        self, _make_streaming_request, fake_metrics
    ):
        """Metrics should NOT be recorded when middleware returns; only after iteration."""
        from airweave.api.middleware import http_metrics_middleware

        request, call_next, response = _make_streaming_request()

        result = await http_metrics_middleware(request, call_next)

        # Middleware returned but body not consumed yet — no request recorded
        assert len(fake_metrics.requests) == 0
        assert fake_metrics.in_progress.get("GET", 0) == 1  # Still in-flight

        # Now consume the stream
        chunks = []
        async for chunk in result.body_iterator:
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]
        assert len(fake_metrics.requests) == 1
        assert fake_metrics.requests[0].status_code == "200"
        assert fake_metrics.requests[0].duration > 0
        assert fake_metrics.in_progress.get("GET", 0) == 0  # Decremented

    @pytest.mark.asyncio
    async def test_streaming_records_total_bytes(self, _make_streaming_request, fake_metrics):
        """Streaming wrapper should accumulate and record total response bytes."""
        from airweave.api.middleware import http_metrics_middleware

        chunks = [b"hello", b" ", b"world"]
        request, call_next, _ = _make_streaming_request(chunks=chunks)

        result = await http_metrics_middleware(request, call_next)
        async for _ in result.body_iterator:
            pass

        assert len(fake_metrics.response_sizes) == 1
        assert fake_metrics.response_sizes[0].size == 11  # len("hello world")

    @pytest.mark.asyncio
    async def test_streaming_handles_str_chunks(self, _make_streaming_request, fake_metrics):
        """SSE responses yield str chunks; bytes should be counted via UTF-8 encoding."""
        from airweave.api.middleware import http_metrics_middleware

        str_chunks = ["data: hello\n\n", "data: world\n\n"]

        request = MagicMock()
        request.url.path = "/api/v1/stream"
        request.method = "GET"
        request.app.state.http_metrics = fake_metrics
        route = MagicMock()
        route.path = "/api/v1/stream"
        request.scope = {"route": route}

        async def body_iter():
            for chunk in str_chunks:
                yield chunk

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.body_iterator = body_iter()
        call_next = AsyncMock(return_value=mock_response)

        result = await http_metrics_middleware(request, call_next)
        async for _ in result.body_iterator:
            pass

        assert len(fake_metrics.response_sizes) == 1
        expected = sum(len(c.encode("utf-8")) for c in str_chunks)
        assert fake_metrics.response_sizes[0].size == expected

    @pytest.mark.asyncio
    async def test_streaming_records_on_client_disconnect(
        self, _make_streaming_request, fake_metrics
    ):
        """Metrics should still be recorded if iteration is interrupted."""
        from airweave.api.middleware import http_metrics_middleware

        async def interrupted_body():
            yield b"first"
            raise GeneratorExit()

        request = MagicMock()
        request.url.path = "/api/v1/stream"
        request.method = "POST"
        request.app.state.http_metrics = fake_metrics
        route = MagicMock()
        route.path = "/api/v1/stream"
        request.scope = {"route": route}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.body_iterator = interrupted_body()
        call_next = AsyncMock(return_value=mock_response)

        result = await http_metrics_middleware(request, call_next)

        # Consume until interruption
        chunks = []
        with pytest.raises(GeneratorExit):
            async for chunk in result.body_iterator:
                chunks.append(chunk)

        # Metrics still recorded via aclose
        assert len(fake_metrics.requests) == 1
        assert fake_metrics.in_progress.get("POST", 0) == 0

    @pytest.mark.asyncio
    async def test_streaming_records_on_task_cancellation(self, fake_metrics):
        """Metrics should be recorded when asyncio.CancelledError interrupts iteration."""
        from airweave.api.middleware import http_metrics_middleware

        async def cancelled_body():
            yield b"first"
            raise asyncio.CancelledError()

        request = MagicMock()
        request.url.path = "/api/v1/stream"
        request.method = "PUT"
        request.app.state.http_metrics = fake_metrics
        route = MagicMock()
        route.path = "/api/v1/stream"
        request.scope = {"route": route}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.body_iterator = cancelled_body()
        call_next = AsyncMock(return_value=mock_response)

        result = await http_metrics_middleware(request, call_next)

        # Consume until cancellation
        with pytest.raises(asyncio.CancelledError):
            async for _ in result.body_iterator:
                pass

        # Metrics still recorded via aclose
        assert len(fake_metrics.requests) == 1
        assert fake_metrics.in_progress.get("PUT", 0) == 0

    @pytest.mark.asyncio
    async def test_streaming_double_close_is_idempotent(
        self, _make_streaming_request, fake_metrics
    ):
        """Calling aclose() twice must not record metrics a second time."""
        from airweave.api.middleware import http_metrics_middleware

        request, call_next, _ = _make_streaming_request()

        result = await http_metrics_middleware(request, call_next)

        # Consume the full stream (triggers first aclose via StopAsyncIteration)
        async for _ in result.body_iterator:
            pass

        assert len(fake_metrics.requests) == 1

        # Explicitly call aclose again — should be a no-op
        await result.body_iterator.aclose()

        assert len(fake_metrics.requests) == 1
        assert fake_metrics.in_progress.get("GET", 0) == 0

    @pytest.mark.asyncio
    async def test_nonstreaming_still_records_immediately(self, fake_metrics):
        """Non-streaming (content-length present) should record immediately as before."""
        from airweave.api.middleware import http_metrics_middleware

        request = MagicMock()
        request.url.path = "/api/v1/items"
        request.method = "GET"
        request.app.state.http_metrics = fake_metrics
        route = MagicMock()
        route.path = "/api/v1/items"
        request.scope = {"route": route}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "42"}
        call_next = AsyncMock(return_value=mock_response)

        await http_metrics_middleware(request, call_next)

        # Recorded immediately, no body iteration needed
        assert len(fake_metrics.requests) == 1
        assert fake_metrics.in_progress.get("GET", 0) == 0
        assert fake_metrics.response_sizes[0].size == 42
