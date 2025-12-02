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
            "$top": 100,
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
