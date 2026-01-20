"""SharePoint 2019 REST API client.

This module provides a client class for interacting with SharePoint 2019
On-Premise REST API using NTLM authentication.

Features:
- NTLM authentication
- Automatic retry with backoff
- OData pagination support
- Discovery methods for sites, lists, and items
- File content download
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from httpx_ntlm import HttpNtlmAuth
from tenacity import retry, stop_after_attempt

from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)


class SharePointClient:
    """Client for SharePoint 2019 REST API with NTLM authentication.

    This client handles all HTTP communication with SharePoint, including:
    - NTLM authentication setup
    - Paginated OData requests
    - Resource discovery (sites, lists, items)
    - File content download

    Args:
        username: SharePoint username
        password: SharePoint password
        domain: Optional Windows domain for NTLM
        logger: Logger instance for debug/error output
    """

    # Headers for SharePoint OData v3 API
    ODATA_HEADERS = {
        "Accept": "application/json;odata=verbose",
        "Content-Type": "application/json;odata=verbose",
    }

    # Standard expansions for role assignments
    ROLE_EXPAND = "RoleAssignments/Member,RoleAssignments/RoleDefinitionBindings"

    def __init__(
        self,
        username: str,
        password: str,
        domain: Optional[str] = None,
        logger: Optional[Any] = None,
    ):
        """Initialize SharePoint client."""
        self.username = username
        self.password = password
        self.domain = domain
        self._logger = logger

    @property
    def logger(self):
        """Get logger, falling back to print if not set."""
        if self._logger:
            return self._logger
        # Minimal fallback logger
        from airweave.core.logging import logger

        return logger

    def _create_ntlm_auth(self) -> HttpNtlmAuth:
        """Create NTLM authentication object."""
        username = f"{self.domain}\\{self.username}" if self.domain else self.username
        return HttpNtlmAuth(username, self.password)

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
        """Make authenticated GET request to SharePoint REST API.

        Args:
            client: httpx AsyncClient instance
            url: Full URL to request
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On non-2xx response
        """
        auth = self._create_ntlm_auth()
        self.logger.debug(f"GET {url} params={params}")
        response = await client.get(
            url, auth=auth, headers=self.ODATA_HEADERS, params=params, timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    async def get_paginated(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield items from OData paginated endpoints.

        Automatically follows __next links for pagination.

        Args:
            client: httpx AsyncClient instance
            url: Initial URL to request
            params: Optional query parameters (only used for first request)

        Yields:
            Individual items from the results array
        """
        current_url = url
        current_params = params

        while current_url:
            data = await self.get(client, current_url, current_params)

            d = data.get("d", {})
            results = d.get("results", [])

            for item in results:
                yield item

            # Follow pagination link if present
            current_url = d.get("__next")
            current_params = None  # Params are embedded in __next URL

    # -------------------------------------------------------------------------
    # Discovery Methods
    # -------------------------------------------------------------------------

    async def get_site(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> Dict[str, Any]:
        """Fetch site (web) metadata with role assignments.

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site

        Returns:
            Site metadata dict from "d" key of response
        """
        endpoint = f"{site_url}/_api/web"
        params = {"$expand": self.ROLE_EXPAND}
        data = await self.get(client, endpoint, params)
        return data.get("d", data)

    async def discover_subsites(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Discover subsites (webs) under a site.

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the parent site

        Yields:
            Subsite metadata dicts with role assignments
        """
        endpoint = f"{site_url}/_api/web/webs"
        params = {"$expand": self.ROLE_EXPAND}
        async for web in self.get_paginated(client, endpoint, params):
            yield web

    async def discover_lists(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Discover lists in a site, filtering out hidden/system lists.

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site

        Yields:
            List metadata dicts with role assignments
        """
        endpoint = f"{site_url}/_api/web/lists"
        params = {
            "$filter": "Hidden eq false",
            "$expand": self.ROLE_EXPAND,
        }
        async for lst in self.get_paginated(client, endpoint, params):
            yield lst

    async def discover_items(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        list_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Discover items in a list with necessary expansions.

        Expands:
        - File: For document library files
        - RoleAssignments: For access control
        - FieldValuesAsText: For human-readable field values

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site
            list_id: GUID of the list

        Yields:
            Item metadata dicts with expanded properties
        """
        endpoint = f"{site_url}/_api/web/lists(guid'{list_id}')/items"
        params = {
            "$expand": f"File,{self.ROLE_EXPAND},FieldValuesAsText",
            "$top": 500,  # Increased from 100 for better batch efficiency
        }
        async for item in self.get_paginated(client, endpoint, params):
            yield item

    # -------------------------------------------------------------------------
    # Site Groups (for Access Graph)
    # -------------------------------------------------------------------------

    async def get_site_groups(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all SharePoint groups in a site.

        SharePoint groups are site-level containers for users and AD groups.
        Each group has an Id, Title, and members.

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site

        Yields:
            Group metadata dicts with Id, Title, etc.
        """
        endpoint = f"{site_url}/_api/web/sitegroups"
        async for group in self.get_paginated(client, endpoint):
            yield group

    async def get_group_members(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        group_id: int,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get members of a SharePoint group.

        Members can be:
        - PrincipalType 1: Individual users
        - PrincipalType 4: AD security groups
        - PrincipalType 8: SharePoint groups (nested)

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site
            group_id: SharePoint group ID (integer)

        Yields:
            Member metadata dicts with LoginName, PrincipalType, etc.
        """
        endpoint = f"{site_url}/_api/web/sitegroups/getbyid({group_id})/users"
        async for member in self.get_paginated(client, endpoint):
            yield member

    # -------------------------------------------------------------------------
    # Change Tracking (Incremental Sync)
    # -------------------------------------------------------------------------

    async def _get_request_digest(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> str:
        """Get request digest for POST operations (CSRF protection).

        SharePoint 2019 on-premises requires X-RequestDigest header for POST requests.

        Args:
            client: httpx AsyncClient instance
            site_url: Base site URL

        Returns:
            Request digest value for X-RequestDigest header
        """
        auth = self._create_ntlm_auth()
        contextinfo_url = f"{site_url.rstrip('/')}/_api/contextinfo"
        self.logger.debug(f"Fetching request digest from {contextinfo_url}")
        response = await client.post(
            contextinfo_url,
            auth=auth,
            headers=self.ODATA_HEADERS,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        # Extract digest from response - structure varies by SharePoint version
        digest = data.get("d", {}).get("GetContextWebInformation", {}).get("FormDigestValue")
        if not digest:
            raise ValueError(f"Could not extract FormDigestValue from contextinfo: {data}")
        return digest

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def post(
        self,
        client: httpx.AsyncClient,
        url: str,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated POST request to SharePoint REST API.

        Args:
            client: httpx AsyncClient instance
            url: Full URL to request
            json_data: JSON body to send

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On non-2xx response
        """
        auth = self._create_ntlm_auth()

        # Extract site URL from the full URL for contextinfo
        # URL format: http://site/_api/... -> http://site
        url_parts = url.split("/_api/")
        site_url = url_parts[0] if len(url_parts) > 1 else url.rsplit("/", 1)[0]

        # Get request digest for CSRF protection
        request_digest = await self._get_request_digest(client, site_url)

        # Merge headers with request digest
        headers = {
            **self.ODATA_HEADERS,
            "X-RequestDigest": request_digest,
        }

        self.logger.debug(f"POST {url}")
        response = await client.post(
            url,
            auth=auth,
            headers=headers,
            json=json_data,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()

    async def get_site_collection_changes(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        change_token: Optional[str] = None,
        include_deletes: bool = True,
    ) -> tuple[list[Dict[str, Any]], str]:
        """Get changes for entire site collection since the specified token.

        Uses /_api/site/getChanges which covers:
        - All subsites (webs)
        - All lists in all subsites
        - All items in all lists

        This is the RECOMMENDED scope for incremental sync as it provides
        ONE change token that covers the entire site collection.

        Change Types:
        - 1: Add
        - 2: Update
        - 3: Delete
        - 4: Rename
        - 5: Move

        Args:
            client: HTTP client
            site_url: Site collection root URL
            change_token: Previous change token (None for first sync)
            include_deletes: Whether to include deletion events

        Returns:
            Tuple of (changes, new_change_token):
            - changes: List of change event dicts
            - new_change_token: Token for next incremental sync
        """
        query = {
            "__metadata": {"type": "SP.ChangeQuery"},
            "Add": True,
            "Update": True,
            "DeleteObject": include_deletes,
            "Move": True,
            "Rename": True,
            "Item": True,
            "File": True,
            "Folder": True,
            "Web": True,
            "List": True,
            "Site": True,
        }

        if change_token:
            query["ChangeTokenStart"] = {"StringValue": change_token}

        # Use /_api/site/getChanges for site collection scope
        endpoint = f"{site_url}/_api/site/getChanges"
        response = await self.post(client, endpoint, json_data={"query": query})

        # Parse changes
        changes = []
        d = response.get("d", {})
        results = d.get("results", [])

        for item in results:
            changes.append(
                {
                    "change_type": item.get("ChangeType"),  # 1=Add, 2=Update, 3=Delete
                    "item_id": item.get("ItemId"),
                    "list_id": item.get("ListId"),
                    "web_id": item.get("WebId"),
                    "site_id": item.get("SiteId"),
                    "time": item.get("Time"),
                    "change_token": item.get("ChangeToken", {}).get("StringValue"),
                }
            )

        # Get new token from last change or current token
        new_token = await self.get_current_change_token(client, site_url)

        self.logger.debug(f"Got {len(changes)} changes since last sync")
        return changes, new_token

    async def get_current_change_token(
        self,
        client: httpx.AsyncClient,
        site_url: str,
    ) -> str:
        """Get the current change token for initial cursor setup.

        Called during first sync to establish baseline token.
        Retrieves token directly from site properties.

        Args:
            client: HTTP client
            site_url: Site collection root URL

        Returns:
            Current change token string
        """
        # Get current change token directly from site properties
        site_endpoint = f"{site_url}/_api/site"
        params = {"$select": "CurrentChangeToken"}
        site_data = await self.get(client, site_endpoint, params)

        token_data = site_data.get("d", {}).get("CurrentChangeToken", {})
        return token_data.get("StringValue", "")

    async def get_item_by_id(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        list_id: str,
        item_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a specific list item by ID.

        Used during incremental sync to fetch changed items.

        Args:
            client: HTTP client
            site_url: Base URL of the site
            list_id: GUID of the list
            item_id: Integer ID of the item

        Returns:
            Item metadata dict or None if not found
        """
        endpoint = f"{site_url}/_api/web/lists(guid'{list_id}')/items({item_id})"
        params = {
            "$expand": f"File,{self.ROLE_EXPAND},FieldValuesAsText",
        }
        try:
            data = await self.get(client, endpoint, params)
            return data.get("d", data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_list_by_id(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        list_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a specific list by ID.

        Used during incremental sync to fetch changed lists.

        Args:
            client: HTTP client
            site_url: Base URL of the site
            list_id: GUID of the list

        Returns:
            List metadata dict or None if not found
        """
        endpoint = f"{site_url}/_api/web/lists(guid'{list_id}')"
        params = {"$expand": self.ROLE_EXPAND}
        try:
            data = await self.get(client, endpoint, params)
            return data.get("d", data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # -------------------------------------------------------------------------
    # File Download
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def get_file_content(
        self,
        client: httpx.AsyncClient,
        site_url: str,
        server_relative_url: str,
    ) -> bytes:
        """Download file content from SharePoint.

        Args:
            client: httpx AsyncClient instance
            site_url: Base URL of the site
            server_relative_url: Server-relative path to the file

        Returns:
            File content as bytes

        Raises:
            httpx.HTTPStatusError: On non-2xx response
        """
        base_url = site_url.rstrip("/")
        url = f"{base_url}/_api/web/GetFileByServerRelativeUrl('{server_relative_url}')/$value"

        auth = self._create_ntlm_auth()
        response = await client.get(url, auth=auth, timeout=60.0)
        response.raise_for_status()
        return response.content
