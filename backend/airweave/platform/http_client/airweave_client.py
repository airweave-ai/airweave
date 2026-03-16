"""AirweaveHttpClient - Universal HTTP client wrapper with rate limiting.

This client wraps any httpx-compatible client (httpx.AsyncClient or PipedreamProxyClient)
and adds source rate limiting to prevent exhausting customer API quotas.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Union
from uuid import UUID

import httpx

from airweave.core.exceptions import SourceRateLimitExceededException
from airweave.core.logging import ContextualLogger
from airweave.core.source_rate_limiter_service import source_rate_limiter
from airweave.platform.utils.ssrf import SSRFViolation, validate_url

if TYPE_CHECKING:
    from airweave.platform.http_client.pipedream_proxy import PipedreamProxyClient


class AirweaveHttpClient:
    """Universal HTTP client wrapper for Airweave sources.

    Wraps any httpx-compatible client and adds rate limiting before requests.
    Works with both httpx.AsyncClient and PipedreamProxyClient via composition.

    The client checks:
    1. Is SOURCE_RATE_LIMITING feature enabled? → No = skip check
    2. Is rate_limit_level set? → No = skip check
    3. Is limit configured in DB? → No = skip check
    4. Otherwise → enforce limit

    When limit is exceeded, converts SourceRateLimitExceededException to
    httpx.HTTPStatusError with 429 status so sources see identical behavior
    to actual API rate limits.
    """

    def __init__(
        self,
        wrapped_client: Union[httpx.AsyncClient, PipedreamProxyClient],
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
        feature_flag_enabled: bool = True,
        logger: Optional[ContextualLogger] = None,
    ):
        """Initialize wrapper around an existing HTTP client.

        Args:
            wrapped_client: The client to wrap (httpx.AsyncClient or PipedreamProxyClient)
            org_id: Organization ID for rate limiting
            source_short_name: Source identifier (e.g., "google_drive", "notion")
            source_connection_id: Source connection ID (used for connection-level sources)
            feature_flag_enabled: Whether SOURCE_RATE_LIMITING feature is enabled
            logger: Contextual logger with sync/search metadata (required)
        """
        self._client = wrapped_client
        self._org_id = org_id
        self._source_short_name = source_short_name
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
        """Check rate limits and convert exceptions to HTTP 429 if exceeded.

        Checks TWO limits when using Pipedream proxy:
        1. Pipedream proxy limit (1000 req/5min org-wide) - checked first
        2. Source-specific limit (if configured in DB)

        Args:
            method: HTTP method
            url: Request URL

        Raises:
            httpx.HTTPStatusError: With 429 status if any limit exceeded
        """
        # Skip if feature flag is disabled
        if not self._feature_flag_enabled:
            return

        try:
            # Step 1: Check Pipedream proxy limit FIRST (if using proxy)
            from airweave.platform.http_client.pipedream_proxy import PipedreamProxyClient

            if isinstance(self._client, PipedreamProxyClient):
                if self._logger:
                    self._logger.debug(
                        "[AirweaveHttpClient] Using Pipedream proxy - checking proxy limit first"
                    )
                await source_rate_limiter.check_pipedream_proxy_limit(self._org_id)
            else:
                if self._logger:
                    self._logger.debug(
                        "[AirweaveHttpClient] Using regular HTTP client (not Pipedream proxy)"
                    )

            # Step 2: Check source-specific limit
            await source_rate_limiter.check_and_increment(
                org_id=self._org_id,
                source_short_name=self._source_short_name,
                source_connection_id=self._source_connection_id,
            )
        except SourceRateLimitExceededException as e:
            # Convert to HTTP 429 so sources treat it like API rate limit
            fake_response = httpx.Response(
                status_code=429,
                headers={"Retry-After": str(int(e.retry_after))},
                request=httpx.Request(method, url),
            )

            # Different message for Pipedream vs source limits
            if e.source_short_name == "pipedream_proxy":
                message = "Pipedream proxy rate limit exceeded (1000 req/5min org-wide)"
            else:
                message = f"Source rate limit exceeded for {e.source_short_name}"

            raise httpx.HTTPStatusError(
                message,
                request=fake_response.request,
                response=fake_response,
            )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
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
    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make GET request through wrapper."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make POST request through wrapper."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make PUT request through wrapper."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make DELETE request through wrapper."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make PATCH request through wrapper."""
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make HEAD request through wrapper."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make OPTIONS request through wrapper."""
        return await self.request("OPTIONS", url, **kwargs)

    def stream(
        self, method: str, url: str, **kwargs: Any,
    ) -> AbstractAsyncContextManager[httpx.Response]:
        """Stream request through wrapper (returns async context manager).

        This mimics httpx.AsyncClient.stream() for compatibility.
        Note: This is not an async method because httpx.AsyncClient.stream()
        returns a context manager directly, not a coroutine.
        """
        return self._stream_context_manager(method, url, **kwargs)

    @asynccontextmanager
    async def _stream_context_manager(
        self, method: str, url: str, **kwargs: Any
    ) -> AsyncIterator[httpx.Response]:
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
    async def __aenter__(self) -> "AirweaveHttpClient":
        """Enter async context manager."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self._client.__aexit__(*args)

    # Additional httpx compatibility methods
    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @property
    def is_closed(self) -> bool:
        """Check if client is closed."""
        return self._client.is_closed

    @property
    def timeout(self) -> httpx.Timeout:
        """Get timeout configuration."""
        return self._client.timeout

    @timeout.setter
    def timeout(self, value: httpx.Timeout) -> None:
        """Set timeout configuration."""
        self._client.timeout = value
