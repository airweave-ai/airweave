"""Base class for all Microsoft Graph API connectors.

Provides shared functionality:
- Token refresh handling with automatic retry
- Rate limiting (429) handling
- Authenticated GET requests
- DateTime parsing
- Common validation logic
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.sources._base import BaseSource


class MicrosoftGraphSource(BaseSource):
    """Base class for Microsoft Graph API connectors.

    All Microsoft Graph API connectors (PowerPoint, Word, Excel, OneNote, Teams, etc.)
    should inherit from this class to get common Graph API functionality.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Make authenticated GET request with automatic token refresh and rate limiting.

        Handles common Microsoft Graph API scenarios:
        - 401 Unauthorized: Automatically refreshes token and retries
        - 429 Rate Limit: Respects Retry-After header and waits
        - Exponential backoff on failures via tenacity decorator

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On non-retryable HTTP errors
            Exception: On other errors after retries exhausted
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401: Token expired
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                response = await client.get(url, headers=headers, params=params)

            # Handle 429: Rate limit
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "60"))
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                await asyncio.sleep(retry_after)
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse Microsoft Graph API datetime strings.

        Handles common Graph API datetime formats:
        - ISO 8601 with Z suffix (UTC): "2023-01-15T10:30:00Z"
        - ISO 8601 with timezone: "2023-01-15T10:30:00+00:00"
        - ISO 8601 without timezone: "2023-01-15T10:30:00"

        Args:
            dt_str: DateTime string from Graph API

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not dt_str:
            return None

        try:
            # Handle Z suffix (UTC)
            if dt_str.endswith("Z"):
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            # Handle standard ISO format
            return datetime.fromisoformat(dt_str)
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
            return None

    async def validate(self) -> bool:
        """Validate credentials by making a test API call to Microsoft Graph.

        Makes a simple /me request to verify:
        - Credentials are valid
        - Token works with Microsoft Graph API
        - Network connectivity is good

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with self.http_client() as client:
                await self._get_with_auth(client, f"{self.GRAPH_BASE_URL}/me")
            return True
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return False
