"""HTTP endpoint verifier for webhooks.

Sends a lightweight HEAD request to check that a URL is reachable.
Implements the EndpointVerifier protocol.
"""

import httpx

from airweave.core.protocols.webhooks import EndpointVerifier
from airweave.domains.webhooks.types import WebhooksError


class HttpEndpointVerifier(EndpointVerifier):
    """Verify webhook endpoints exist by checking reachability.

    Sends a HEAD request and accepts any HTTP response. The goal is only
    to confirm the URL resolves and a server is listening -- status codes
    are irrelevant since the endpoint may reject unauthenticated requests.
    """

    async def verify(self, url: str, timeout: float = 5.0) -> None:
        """Check that the endpoint URL is reachable.

        Args:
            url: The webhook endpoint URL to verify.
            timeout: Seconds to wait for a response before giving up.

        Raises:
            WebhooksError: If the endpoint is unreachable or times out.
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                await client.head(url)
            except httpx.TimeoutException as exc:
                raise WebhooksError("Endpoint did not respond within 5 seconds.", 400) from exc
            except httpx.ConnectError as exc:
                raise WebhooksError(
                    "Could not connect to endpoint. Please check the URL is correct "
                    "and the server is running.",
                    400,
                ) from exc
            except httpx.HTTPError as exc:
                raise WebhooksError(f"Failed to reach endpoint: {exc}", 400) from exc
