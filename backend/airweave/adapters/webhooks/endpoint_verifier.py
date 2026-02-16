"""HTTP endpoint verifier for webhooks.

Sends a lightweight test ping to a URL and expects a 2xx response.
Implements the EndpointVerifier protocol.
"""

from datetime import datetime, timezone

import httpx

from airweave.domains.webhooks.types import WebhooksError


class HttpEndpointVerifier:
    """Verify webhook endpoints by sending a test HTTP POST.

    Sends a ``webhook_endpoint.ping`` payload directly from Airweave
    (not via Svix) and checks for a 2xx response.
    """

    async def verify(self, url: str, timeout: float = 5.0) -> None:
        """Send a test ping to verify the endpoint is reachable.

        Args:
            url: The webhook endpoint URL to verify.
            timeout: Seconds to wait for a response before giving up.

        Raises:
            WebhooksError: If the endpoint is unreachable, times out, or
                returns a non-2xx status code.
        """
        test_payload = {
            "event_type": "webhook_endpoint.ping",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Endpoint verification ping from Airweave",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=test_payload)
                if response.status_code < 200 or response.status_code >= 300:
                    raise WebhooksError(
                        f"Endpoint returned HTTP {response.status_code}. Expected a 2xx response.",
                        400,
                    )
            except httpx.TimeoutException as exc:
                raise WebhooksError("Endpoint did not respond within 5 seconds.", 400) from exc
            except httpx.ConnectError as exc:
                raise WebhooksError(
                    "Could not connect to endpoint. Please check the URL is correct "
                    "and the server is running.",
                    400,
                ) from exc
            except WebhooksError:
                raise
            except httpx.HTTPError as exc:
                raise WebhooksError(f"Failed to reach endpoint: {exc}", 400) from exc
