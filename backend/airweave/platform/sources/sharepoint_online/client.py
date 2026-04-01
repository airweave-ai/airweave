"""Microsoft Graph API client for SharePoint Online.

Handles all HTTP communication with the Graph API:
- OAuth2 bearer token auth
- OData v4 pagination (@odata.nextLink)
- Delta queries for incremental sync
- Site, drive, and item discovery
- Drive item permissions
- File content download
"""

from __future__ import annotations

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
        http_client: Pre-built AirweaveHttpClient with rate limiting.
        logger: Logger instance.
    """

    def __init__(
        self,
        access_token_provider: Callable,
        http_client: Any,
        logger: Any,
    ):
        """Initialize the Graph client with an OAuth2 token provider."""
        self._get_token = access_token_provider
        self._http_client = http_client
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
        url: str,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute a GET request against the Graph API with retry logic."""
        headers = await self._headers()
        self.logger.debug(f"GET {url}")
        response = await self._http_client.get(url, headers=headers, params=params, timeout=30.0)

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
                error_info = error_body.get("error", {})
                self.logger.warning(
                    f"Graph API error {response.status_code}: "
                    f"code={error_info.get('code')}, "
                    f"message={error_info.get('message')}"
                )
            except Exception:
                self.logger.warning(
                    f"Graph API error {response.status_code}: "
                    f"<redacted, {len(response.text)} bytes>"
                )

        response.raise_for_status()
        return response.json()

    async def get_paginated(
        self,
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
            data = await self.get(current_url, current_params)
            items = data.get("value", [])
            for item in items:
                yield item

            current_url = data.get("@odata.nextLink")
            current_params = None  # nextLink includes all params

    # -- Site Discovery --

    async def get_root_site(self) -> Dict[str, Any]:
        """Get the tenant root SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/root"
        return await self.get(url)

    async def get_site(self, site_id: str) -> Dict[str, Any]:
        """Get a SharePoint site by its ID."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}"
        return await self.get(url)

    async def get_site_by_url(self, hostname: str, site_path: str) -> Dict[str, Any]:
        """Get site by hostname and server-relative path."""
        url = f"{GRAPH_BASE_URL}/sites/{hostname}:/{site_path}"
        return await self.get(url)

    async def search_sites(self, query: str = "*") -> AsyncGenerator[Dict[str, Any], None]:
        """Search for SharePoint sites matching a query string."""
        url = f"{GRAPH_BASE_URL}/sites"
        params = {"search": query}
        async for site in self.get_paginated(url, params):
            yield site

    async def get_subsites(self, site_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Get subsites of a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/sites"
        async for site in self.get_paginated(url):
            yield site

    # -- Drive Discovery --

    async def get_drives(self, site_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all document library drives for a site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/drives"
        async for drive in self.get_paginated(url):
            yield drive

    async def get_drive(self, drive_id: str) -> Dict[str, Any]:
        """Get a single drive by its ID."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}"
        return await self.get(url)

    # -- Drive Items --

    async def get_drive_items_recursive(
        self,
        drive_id: str,
        folder_id: str = "root",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively yield all items in a drive using BFS."""
        folders_to_process = [folder_id]
        processed_folders: set = set()

        self.logger.info(f"BFS start: drive={drive_id}, root_folder={folder_id}")

        while folders_to_process:
            current_folder = folders_to_process.pop(0)
            if current_folder in processed_folders:
                self.logger.debug(f"BFS skip (already processed): {current_folder}")
                continue
            processed_folders.add(current_folder)

            url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{current_folder}/children"
            self.logger.info(
                f"BFS processing folder={current_folder} | "
                f"queue={len(folders_to_process)} remaining | "
                f"processed={len(processed_folders)}"
            )

            item_count = 0
            folder_count = 0
            async for item in self.get_paginated(url):
                item_count += 1
                item_name = item.get("name", "?")
                is_folder = bool(item.get("folder"))

                if is_folder:
                    folder_count += 1
                    child_id = item.get("id")
                    if child_id and child_id not in processed_folders:
                        folders_to_process.append(child_id)
                        self.logger.info(
                            f"BFS enqueue folder: {item_name} (id={child_id}) | "
                            f"queue now={len(folders_to_process)}"
                        )

                yield item

            self.logger.info(
                f"BFS folder done: {current_folder} | "
                f"items={item_count}, subfolders={folder_count} | "
                f"queue={len(folders_to_process)} remaining"
            )

    # -- Drive Children (Browse Tree) --

    async def get_drive_children(
        self,
        drive_id: str,
        folder_id: str = "root",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield immediate children of a drive folder (non-recursive).

        Used by the browse tree for lazy-loaded folder expansion.

        Args:
            drive_id: Drive ID.
            folder_id: Folder item ID, or "root" for drive root.
        """
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}/children"
        async for item in self.get_paginated(url):
            yield item

    # -- Delta Query (Incremental Sync) --

    async def get_drive_delta(
        self,
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
            data = await self.get(current_url)
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
        drive_id: str,
        item_id: str,
    ) -> List[Dict[str, Any]]:
        """Get permissions for a drive item."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/permissions"
        try:
            data = await self.get(url)
            return data.get("value", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise

    # -- Lists --

    async def get_lists(self, site_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Get non-hidden lists for a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/lists"
        params = {"$filter": "list/hidden eq false"}
        async for lst in self.get_paginated(url, params):
            yield lst

    async def get_list_items(
        self, site_id: str, list_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all items from a SharePoint list with expanded fields."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/lists/{list_id}/items"
        params = {"$expand": "fields"}
        async for item in self.get_paginated(url, params):
            yield item

    # -- Pages --

    async def get_pages(self, site_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Get site pages for a SharePoint site."""
        url = f"{GRAPH_BASE_URL}/sites/{site_id}/pages"
        try:
            async for page in self.get_paginated(url):
                yield page
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                self.logger.debug(f"Pages not available for site {site_id}: {e}")
                return
            raise

    # -- Site Groups (SP REST API — requires SharePoint-scoped token) --

    async def _sp_headers(self, sp_token_provider: Optional[Callable] = None) -> Dict[str, str]:
        """Build headers for SP REST API calls using a SharePoint-scoped token."""
        if sp_token_provider:
            token = await sp_token_provider()
        else:
            token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;odata=verbose",
        }

    async def _sp_get_with_retry(
        self,
        url: str,
        headers: Dict[str, str],
        max_attempts: int = 3,
    ) -> httpx.Response:
        """Execute a SP REST GET with simple retry on transient errors."""
        import asyncio

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._http_client.get(url, headers=headers, timeout=30.0)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    self.logger.warning(f"SP REST rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt == max_attempts:
                    raise
                self.logger.warning(f"SP REST transient error (attempt {attempt}): {e}")
                await asyncio.sleep(2**attempt)
        raise httpx.TimeoutException("SP REST max retries exhausted")

    async def get_site_groups(
        self,
        site_url: str,
        sp_token_provider: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Get SharePoint site groups via the SP REST API.

        Args:
            site_url: Full site URL (e.g. https://tenant.sharepoint.com/sites/MySite).
            sp_token_provider: Async callable returning a SharePoint-scoped token.
                If None, falls back to the Graph token (will likely 401).
        """
        url = f"{site_url}/_api/web/sitegroups"
        headers = await self._sp_headers(sp_token_provider)
        try:
            response = await self._sp_get_with_retry(url, headers)
            data = response.json()
            return data.get("d", {}).get("results", [])
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"SP site groups not available: {e}")
            return []

    async def get_site_group_users(
        self,
        site_url: str,
        group_id: int,
        sp_token_provider: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Get users in a SharePoint site group via SP REST API.

        Args:
            site_url: Full site URL.
            group_id: SP site group ID (integer).
            sp_token_provider: Async callable returning a SharePoint-scoped token.
        """
        url = f"{site_url}/_api/web/sitegroups/getbyid({group_id})/users"
        headers = await self._sp_headers(sp_token_provider)
        try:
            response = await self._sp_get_with_retry(url, headers)
            data = response.json()
            return data.get("d", {}).get("results", [])
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"SP group {group_id} users not available: {e}")
            return []

    # -- User Resolution --

    async def resolve_user_ids(
        self,
        user_ids: List[str],
    ) -> Dict[str, str]:
        """Resolve Entra user object IDs to email addresses.

        Uses asyncio.gather with concurrency limits to avoid sequential
        one-per-user API calls that bottleneck on large tenants.

        Returns a mapping of user_id -> email (lowercase).
        IDs that cannot be resolved are omitted from the result.
        """
        import asyncio

        CONCURRENCY = 10
        semaphore = asyncio.Semaphore(CONCURRENCY)
        result: Dict[str, str] = {}

        async def _resolve_one(uid: str) -> None:
            async with semaphore:
                try:
                    url = f"{GRAPH_BASE_URL}/users/{uid}"
                    data = await self.get(url, {"$select": "userPrincipalName,mail"})
                    email = data.get("mail") or data.get("userPrincipalName", "")
                    if email and "@" in email:
                        result[uid] = email.lower()
                    else:
                        self.logger.warning(f"User {uid} has no resolvable email")
                except Exception as e:
                    self.logger.warning(f"Could not resolve user {uid}: {e}")

        await asyncio.gather(*[_resolve_one(uid) for uid in user_ids])
        return result

    # -- File Download --

    async def get_file_content_url(
        self,
        drive_id: str,
        item_id: str,
    ) -> str:
        """Get the download URL for a file."""
        url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}"
        params = {"$select": "@microsoft.graph.downloadUrl"}
        data = await self.get(url, params)
        return data.get("@microsoft.graph.downloadUrl", "")

    # -- Groups (Entra ID) --

    async def get_groups(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Get security and mail-enabled Entra ID groups."""
        url = f"{GRAPH_BASE_URL}/groups"
        params = {
            "$filter": "securityEnabled eq true or mailEnabled eq true",
            "$top": "200",
        }
        async for group in self.get_paginated(url, params):
            yield group

    async def get_group_members(self, group_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Get transitive members of an Entra ID group."""
        url = f"{GRAPH_BASE_URL}/groups/{group_id}/transitiveMembers"
        params = {"$top": "200"}
        async for member in self.get_paginated(url, params):
            yield member
