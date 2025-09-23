"""Pipedream proxy HTTP client that mimics httpx.AsyncClient interface."""

import base64
import urllib
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx


class PipedreamProxyClient:
    """HTTP client that routes through Pipedream proxy.

    Mimics httpx.AsyncClient interface for drop-in compatibility.
    """

    # Auth headers to strip (Pipedream will inject the real ones)
    AUTH_HEADERS_TO_STRIP = {
        "authorization",
        "x-api-key",
        "api-key",
        "apikey",
        "x-shopify-access-token",
        "stripe-account",
        "x-github-token",
        "x-slack-token",
        "bearer",
    }

    def __init__(
        self,
        project_id: str,
        account_id: str,
        external_user_id: str,
        environment: str,
        pipedream_token: Optional[str] = None,  # Can be None, will fetch dynamically
        token_provider: Optional[Any] = None,  # Callable that returns fresh token
        app_info: Dict[str, Any] = None,
        **httpx_kwargs,  # Accept standard httpx params for compatibility
    ):
        """Initialize Pipedream proxy client.

        Args:
            project_id: Pipedream project ID
            account_id: Pipedream account ID for the end user
            external_user_id: External user ID
            environment: Environment (production/development)
            pipedream_token: Static Pipedream API access token (deprecated, use token_provider)
            token_provider: Async callable that returns a fresh token
            app_info: App information from Pipedream API
            **httpx_kwargs: Additional kwargs to pass to underlying httpx client
        """
        self._config = {
            "project_id": project_id,
            "account_id": account_id,
            "external_user_id": external_user_id,
            "environment": environment,
        }
        self._static_token = pipedream_token  # Fallback static token
        self._token_provider = token_provider  # Dynamic token provider
        self._app_info = app_info or {}
        self._client = httpx.AsyncClient(**httpx_kwargs)

    async def __aenter__(self):
        """Enter async context manager."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        """Exit async context manager."""
        await self._client.__aexit__(*args)

    # Mimic httpx.AsyncClient methods
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request through proxy."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Make POST request through proxy."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """Make PUT request through proxy."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request through proxy."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> httpx.Response:
        """Make PATCH request through proxy."""
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs) -> httpx.Response:
        """Make HEAD request through proxy."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs) -> httpx.Response:
        """Make OPTIONS request through proxy."""
        return await self.request("OPTIONS", url, **kwargs)

    async def _prepare_proxy_request(self, url: str, **kwargs) -> tuple[str, dict]:
        """Prepare URL and kwargs for proxy request.

        Handles:
        - Building full URL with query params
        - Converting to proxy URL format
        - Adding Pipedream required params
        - Transforming headers

        Returns:
            Tuple of (proxy_url, modified_kwargs)
        """
        # Build full target URL with query params if provided
        if "params" in kwargs:
            # Build the full URL with query params for encoding
            params = kwargs.pop("params")
            parsed = urllib.parse.urlparse(url)
            # Handle None params gracefully
            if params:
                query = urllib.parse.urlencode(params)
                full_url = f"{url}?{query}" if not parsed.query else f"{url}&{query}"
            else:
                full_url = url
        else:
            full_url = url

        # Transform to proxy URL (with full URL including params encoded)
        proxy_url = self._build_proxy_url(full_url)

        # Add Pipedream required params as query params to the proxy URL
        kwargs["params"] = {
            "external_user_id": self._config["external_user_id"],
            "account_id": self._config["account_id"],
        }

        # Transform headers
        if "headers" in kwargs:
            kwargs["headers"] = await self._transform_headers(kwargs["headers"])
        else:
            kwargs["headers"] = await self._get_proxy_headers()

        return proxy_url, kwargs

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Route request through Pipedream proxy.

        Args:
            method: HTTP method
            url: Target URL (can be relative or absolute)
            **kwargs: Additional request parameters (headers, params, json, etc.)

        Returns:
            httpx.Response from the proxied request
        """
        proxy_url, kwargs = await self._prepare_proxy_request(url, **kwargs)
        return await self._client.request(method, proxy_url, **kwargs)

    async def _transform_headers(self, source_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Transform source headers for proxy request.

        Strips auth headers (Pipedream will inject them) and forwards
        other headers with x-pd-proxy prefix.
        """
        proxy_headers = await self._get_proxy_headers()

        if source_headers:
            # Forward non-auth headers with x-pd-proxy prefix
            for key, value in source_headers.items():
                if key.lower() not in self.AUTH_HEADERS_TO_STRIP:
                    # Use x-pd-proxy prefix for forwarding
                    proxy_headers[f"x-pd-proxy-{key}"] = value

        return proxy_headers

    async def _get_proxy_headers(self) -> Dict[str, str]:
        """Get base proxy headers for Pipedream with fresh token.

        The token provider (_ensure_valid_token) already implements smart refresh:
        - Checks if current token is still valid (with 5-minute buffer)
        - Only refreshes when needed (not on every request)
        - Returns cached token if still valid
        """
        # Get token - provider handles refresh logic internally
        if self._token_provider:
            token = await self._token_provider()
        else:
            token = self._static_token

        if not token:
            raise ValueError("No Pipedream token available")

        return {
            "Authorization": f"Bearer {token}",
            "x-pd-environment": self._config["environment"],
            "Content-Type": "application/json",  # Default content type
        }

    def _build_proxy_url(self, url: str) -> str:
        """Convert URL to Pipedream proxy format.

        Args:
            url: Target URL (relative or absolute)

        Returns:
            Pipedream proxy URL with encoded target
        """
        # Base64 encode the URL for proxy
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

        # Build proxy URL - Pipedream expects external_user_id and account_id in the path
        proxy_url = (
            f"https://api.pipedream.com/v1/connect/{self._config['project_id']}/proxy/{encoded_url}"
        )

        return proxy_url

    def stream(self, method: str, url: str, **kwargs):
        """Stream request through proxy (returns async context manager).

        This mimics httpx.AsyncClient.stream() for compatibility.
        Note: This is not an async method because httpx.AsyncClient.stream()
        returns a context manager directly, not a coroutine.
        """
        return self._stream_context_manager(method, url, **kwargs)

    @asynccontextmanager
    async def _stream_context_manager(self, method: str, url: str, **kwargs):
        """Internal async context manager for streaming requests.

        This allows us to do async preparation (like getting fresh tokens)
        before creating the actual stream.
        """
        proxy_url, prepared_kwargs = await self._prepare_proxy_request(url, **kwargs)
        # Now delegate to the actual stream context manager
        async with self._client.stream(method, proxy_url, **prepared_kwargs) as response:
            yield response

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
