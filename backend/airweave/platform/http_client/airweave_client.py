"""AirweaveHttpClient - Universal HTTP client wrapper with rate limiting.

This client wraps an httpx.AsyncClient and adds source rate limiting to prevent
exhausting customer API quotas.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

import httpx

from airweave.core.logging import ContextualLogger
from airweave.domains.sources.rate_limiting.exceptions import InternalRateLimitExceeded
from airweave.domains.sources.rate_limiting.service import SourceRateLimiter
from airweave.platform.utils.ssrf import SSRFViolation, validate_url


class AirweaveHttpClient:
    """Universal HTTP client wrapper for Airweave sources.

    Wraps an httpx.AsyncClient and adds rate limiting before requests.
    Rate limiter is injected at construction — no global singleton access.
    """

    def __init__(
        self,
        wrapped_client: httpx.AsyncClient,
        org_id: UUID,
        source_short_name: str,
        rate_limiter: Optional[SourceRateLimiter] = None,
        source_connection_id: Optional[UUID] = None,
        feature_flag_enabled: bool = True,
        logger: Optional[ContextualLogger] = None,
    ):
        """Initialize wrapper around an existing HTTP client.

        Args:
            wrapped_client: The httpx.AsyncClient to wrap.
            org_id: Organization ID for rate limiting.
            source_short_name: Source identifier (e.g., "google_drive", "notion").
            rate_limiter: Injected SourceRateLimiter instance.
            source_connection_id: Source connection ID (for connection-level sources).
            feature_flag_enabled: Whether SOURCE_RATE_LIMITING feature is enabled.
            logger: Contextual logger with sync/search metadata.
        """
        self._client = wrapped_client
        self._org_id = org_id
        self._source_short_name = source_short_name
        self._rate_limiter = rate_limiter
        self._source_connection_id = source_connection_id
        self._feature_flag_enabled = feature_flag_enabled
        self._logger = logger

        # Install SSRF redirect hook on httpx clients
        if isinstance(wrapped_client, httpx.AsyncClient):
            self._install_ssrf_hook(wrapped_client)

    def _check_ssrf(self, url: str) -> None:
        """Validate URL against SSRF blocklist before making a request."""
        try:
            validate_url(url)
        except SSRFViolation as exc:
            if self._logger:
                self._logger.warning(f"[SSRF] Blocked: {exc} (source={self._source_short_name})")
            raise

    def _install_ssrf_hook(self, client: httpx.AsyncClient) -> None:
        """Install an httpx event hook that validates redirect targets."""
        logger = self._logger
        source = self._source_short_name

        async def ssrf_hook(request: httpx.Request) -> None:
            try:
                validate_url(str(request.url))
            except SSRFViolation as exc:
                if logger:
                    logger.warning(f"[SSRF] Blocked redirect: {exc} (source={source})")
                raise

        client.event_hooks.setdefault("request", []).append(ssrf_hook)

    async def _check_rate_limit_and_convert_to_429(self, method: str, url: str) -> None:
        """Check source-specific rate limit and convert exceptions to HTTP 429 if exceeded.

        Args:
            method: HTTP method
            url: Request URL

        Raises:
            httpx.HTTPStatusError: With 429 status if limit exceeded
        """
        if not self._feature_flag_enabled or not self._rate_limiter:
            return

        try:
            await self._rate_limiter.check_and_increment(
                org_id=self._org_id,
                source_short_name=self._source_short_name,
                source_connection_id=self._source_connection_id,
            )
        except InternalRateLimitExceeded as e:
            fake_response = httpx.Response(
                status_code=429,
                headers={"Retry-After": str(int(e.retry_after))},
                request=httpx.Request(method, url),
            )

            raise httpx.HTTPStatusError(
                f"Source rate limit exceeded for {e.source_short_name}",
                request=fake_response.request,
                response=fake_response,
            )

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with rate limiting check.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            httpx.Response from the wrapped client

        Raises:
            httpx.HTTPStatusError: With 429 status if rate limit exceeded
        """
        # SSRF check BEFORE anything else
        self._check_ssrf(url)

        # Check rate limit BEFORE request
        await self._check_rate_limit_and_convert_to_429(method, url)

        # Delegate to wrapped client (httpx or Pipedream)
        response = await self._client.request(method, url, **kwargs)

        # Log full response details on HTTP errors (4xx/5xx)
        if response.status_code >= 400:
            await self._log_error_response(method, url, response)

        return response

    async def _log_error_response(self, method: str, url: str, response: httpx.Response) -> None:
        """Log full HTTP error response for debugging.

        Args:
            method: HTTP method used
            url: Request URL
            response: The error response from the API
        """
        if not self._logger:
            return

        try:
            # Try to read response body - may already be consumed
            response_body = response.text
        except Exception:
            response_body = "<unable to read response body>"

        self._logger.debug(
            f"[AirweaveHttpClient] HTTP {response.status_code} error\n"
            f"  Source: {self._source_short_name}\n"
            f"  Method: {method}\n"
            f"  URL: {url}\n"
            f"  Response Headers: {dict(response.headers)}\n"
            f"  Response Body: {response_body}"
        )

    # Mimic httpx.AsyncClient methods
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request through wrapper."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Make POST request through wrapper."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """Make PUT request through wrapper."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request through wrapper."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> httpx.Response:
        """Make PATCH request through wrapper."""
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs) -> httpx.Response:
        """Make HEAD request through wrapper."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs) -> httpx.Response:
        """Make OPTIONS request through wrapper."""
        return await self.request("OPTIONS", url, **kwargs)

    def stream(self, method: str, url: str, **kwargs):
        """Stream request through wrapper (returns async context manager).

        This mimics httpx.AsyncClient.stream() for compatibility.
        Note: This is not an async method because httpx.AsyncClient.stream()
        returns a context manager directly, not a coroutine.
        """
        return self._stream_context_manager(method, url, **kwargs)

    @asynccontextmanager
    async def _stream_context_manager(self, method: str, url: str, **kwargs):
        """Internal async context manager for streaming requests.

        Checks SSRF and rate limit before creating the stream.
        """
        # SSRF check before streaming
        self._check_ssrf(url)

        # Check rate limit before streaming
        await self._check_rate_limit_and_convert_to_429(method, url)

        # Delegate to wrapped client's stream
        async with self._client.stream(method, url, **kwargs) as response:
            # Log error responses for streaming requests too
            if response.status_code >= 400:
                await self._log_error_response(method, url, response)
            yield response

    # Context manager support (delegate to wrapped client)
    async def __aenter__(self):
        """Enter async context manager."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        """Exit async context manager."""
        await self._client.__aexit__(*args)

    # Additional httpx compatibility methods
    async def aclose(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @property
    def is_closed(self) -> bool:
        """Check if client is closed."""
        return self._client.is_closed

    @property
    def timeout(self):
        """Get timeout configuration."""
        return self._client.timeout

    @timeout.setter
    def timeout(self, value):
        """Set timeout configuration."""
        self._client.timeout = value
