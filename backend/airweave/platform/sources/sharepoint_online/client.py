"""Microsoft Graph API client for SharePoint Online.

Handles all HTTP communication with the Graph API:
- OAuth2 bearer token auth
- OData v4 pagination (@odata.nextLink)
- Delta queries for incremental sync
- Site, drive, and item discovery
- Drive item permissions
- File content download
"""

from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt

from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphClient:
    """Client for Microsoft Graph API with OAuth2 bearer auth.

    Args:
        access_token_provider: Async callable that returns a valid access token.
        logger: Logger instance.
    """

    def __init__(
        self,
        access_token_provider: Callable,
        logger: Any,
    ):
        """Initialize the Graph client with an OAuth2 token provider."""
        self._get_token = access_token_provider
        self.logger = logger

    async def _headers(self) -> Dict[str, str]:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def get(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute a GET request against the Graph API with retry logic."""
        headers = await self._headers()
        self.logger.debug(f"GET {url}")
        response = await client.get(url, headers=headers, params=params, timeout=30.0)

        if response.status_code == 401:
            self.logger.warning("Got 401, token may need refresh")
            response.raise_for_status()

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            self.logger.warning(f"Rate limited, retry after {retry_after}s")
            response.raise_for_status()

        if response.status_code >= 400:
            try:
                error_body = response.json()
                self.logger.error(f"Graph API error {response.status_code}: {error_body}")
            except Exception:
                self.logger.error(f"Graph API error {response.status_code}: {response.text[:500]}")

        response.raise_for_status()
        return response.json()

    async def get_paginated(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict] = None,
        page_size: int = 200,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield items from OData v4 paginated endpoints.

        Follows @odata.nextLink for pagination.
        """
        current_url = url
        current_params = params or {}
        if "$top" not in current_params:
            current_params["$top"] = str(page_size)

        while current_url:
            data = await self.get(client, current_url, current_params)
            items = data.get("value", [])
            for item in items:
                yield item

            current_url = data.get("@odata.nextLink")
            current_params = None  # nextLink includes all params

    # -- Site Discovery --

    async def get_root_site(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Get the tenant root SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/root"
        return await self.get(client, url)

    async def get_site(self, client: httpx.AsyncClient, site_id: str) -> Dict[str, Any]:
        """Get a SharePoint site by its ID."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}"
        return await self.get(client, url)

    async def get_site_by_url(
        self, client: httpx.AsyncClient, hostname: str, site_path: str
    ) -> Dict[str, Any]:
        """Get site by hostname and server-relative path."""
        url = f"{GRAPH_BASE_URL}/sites/{hostname}:/{site_path}"
        return await self.get(client, url)

    async def search_sites(
        self, client: httpx.AsyncClient, query: str = "*"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Search for SharePoint sites matching a query string."""
        url = f"{GRAPH_BASE_URL}/sites"
        params = {"search": query}
        async for site in self.get_paginated(client, url, params):
            yield site

    async def get_subsites(
        self, client: httpx.AsyncClient, site_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get subsites of a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/sites"
        async for site in self.get_paginated(client, url):
            yield site

    # -- Drive Discovery --

    async def get_drives(
        self, client: httpx.AsyncClient, site_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all document library drives for a site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/drives"
        async for drive in self.get_paginated(client, url):
            yield drive

    async def get_drive(self, client: httpx.AsyncClient, drive_id: str) -> Dict[str, Any]:
        """Get a single drive by its ID."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}"
        return await self.get(client, url)

    # -- Drive Items --

    async def get_drive_items_recursive(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        folder_id: str = "root",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively yield all items in a drive using BFS."""
        folders_to_process = [folder_id]
        processed_folders: set = set()

        while folders_to_process:
            current_folder = folders_to_process.pop(0)
            if current_folder in processed_folders:
                continue
            processed_folders.add(current_folder)

            url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{current_folder}/children"

            async for item in self.get_paginated(client, url):
                yield item

                if item.get("folder"):
                    child_id = item.get("id")
                    if child_id and child_id not in processed_folders:
                        folders_to_process.append(child_id)

    # -- Delta Query (Incremental Sync) --

    async def get_drive_delta(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        delta_token: str = "",
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Get changes since the last delta token.

        Returns (changed_items, new_delta_token).
        If delta_token is empty, returns all items (initial sync).
        """
        if delta_token:
            url = delta_token  # Delta tokens are full URLs
        else:
            url = f"{GRAPH_BASE_URL}/drives/{drive_id}/root/delta"

        all_items: List[Dict[str, Any]] = []
        current_url: Optional[str] = url
        delta_link = ""

        while current_url:
            data = await self.get(client, current_url)
            items = data.get("value", [])
            all_items.extend(items)

            next_link = data.get("@odata.nextLink")
            delta_link = data.get("@odata.deltaLink", delta_link)

            current_url = next_link

        new_token = delta_link if delta_link else ""
        self.logger.info(
            f"Delta query for drive {drive_id}: {len(all_items)} items, "
            f"has_new_token={bool(new_token)}"
        )
        return all_items, new_token

    # -- Permissions --

    async def get_item_permissions(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        item_id: str,
    ) -> List[Dict[str, Any]]:
        """Get permissions for a drive item."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/permissions"
        try:
            data = await self.get(client, url)
            return data.get("value", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise

    # -- Lists --

    async def get_lists(
        self, client: httpx.AsyncClient, site_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get non-hidden lists for a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/lists"
        params = {"$filter": "list/hidden eq false"}
        async for lst in self.get_paginated(client, url, params):
            yield lst

    async def get_list_items(
        self, client: httpx.AsyncClient, site_id: str, list_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all items from a SharePoint list with expanded fields."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/lists/{list_id}/items"
        params = {"$expand": "fields"}
        async for item in self.get_paginated(client, url, params):
            yield item

    # -- Pages --

    async def get_pages(
        self, client: httpx.AsyncClient, site_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get site pages for a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/pages"
        try:
            async for page in self.get_paginated(client, url):
                yield page
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                self.logger.debug(f"Pages not available for site {site_id}: {e}")
                return
            raise

    # -- Site Groups --

    async def get_site_groups(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> List[Dict[str, Any]]:
        """Get SharePoint site groups.

        Graph doesn't expose SP groups directly — this is a placeholder
        for future SP REST API integration through the Graph proxy.
        """
        return []

    # -- File Download --

    async def get_file_content_url(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        item_id: str,
    ) -> str:
        """Get the download URL for a file."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}"
        params = {"$select": "@microsoft.graph.downloadUrl"}
        data = await self.get(client, url, params)
        return data.get("@microsoft.graph.downloadUrl", "")

    # -- Groups (Entra ID) --

    async def get_groups(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict[str, Any], None]:
        """Get security and mail-enabled Entra ID groups."""
        url = f"{GRAPH_BASE_URL}/groups"
        params = {
            "$filter": "securityEnabled eq true or mailEnabled eq true",
            "$top": "200",
        }
        async for group in self.get_paginated(client, url, params):
            yield group

    async def get_group_members(
        self, client: httpx.AsyncClient, group_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get transitive members of an Entra ID group."""
        url = f"{GRAPH_BASE_URL}/groups/{group_id}/transitiveMembers"
        params = {"$top": "200"}
        async for member in self.get_paginated(client, url, params):
            yield member
