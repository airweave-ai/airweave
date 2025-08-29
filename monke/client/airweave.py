"""Airweave API client for monke."""

import os
from typing import Any, Dict, List, Optional

import httpx
from monke.utils.logging import get_logger


class AirweaveClient:
    """Client for interacting with Airweave backend API."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the Airweave client.

        Args:
            base_url: Base URL for Airweave API (default: from env or localhost:8001)
        """
        self.base_url = base_url or os.getenv("AIRWEAVE_API_URL", "http://localhost:8001")
        self.logger = get_logger("airweave_client")

        # For now, we'll use system authentication (local development)
        # In production, this would use proper API keys or OAuth
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

        self.logger.info(f"🔗 Initialized Airweave client for {self.base_url}")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Airweave API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/collections')
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            Exception: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        self.logger.debug(f"🌐 {method} {url}")
        if data:
            self.logger.debug(f"📤 Request data: {data}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    params=params,
                    timeout=30.0,
                )

                self.logger.debug(f"📥 Response status: {response.status_code}")

                if response.status_code >= 400:
                    error_msg = f"API request failed: {response.status_code} - {response.text}"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)

                # Try to parse JSON response
                try:
                    return response.json()
                except Exception:
                    # If not JSON, return text
                    return {"text": response.text}

            except httpx.RequestError as e:
                error_msg = f"Request failed: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return await self._make_request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a POST request."""
        return await self._make_request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        return await self._make_request("PUT", endpoint, data=data)

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        return await self._make_request("DELETE", endpoint)

    # Collection management
    async def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new collection."""
        return await self.post("/collections", data=collection_data)

    async def delete_collection(self, collection_id: str) -> Dict[str, Any]:
        """Delete a collection."""
        return await self.delete(f"/collections/{collection_id}")

    async def search_collection(self, collection_id: str, query: str, **kwargs) -> Dict[str, Any]:
        """Search a collection."""
        params = {"query": query, **kwargs}
        return await self.get(f"/collections/{collection_id}/search", params=params)

    # Source connection management
    async def create_source_connection(self, connection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new source connection."""
        return await self.post("/source-connections", data=connection_data)

    # Auth provider management
    async def connect_auth_provider(self, connection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new auth provider connection (e.g., Composio service key)."""
        return await self.post("/auth-providers", data=connection_data)

    # Sync management
    async def create_sync(self, sync_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new sync."""
        return await self.post("/syncs", data=sync_data)

    async def run_sync(self, sync_id: str) -> Dict[str, Any]:
        """Run a sync."""
        return await self.post(f"/syncs/{sync_id}/run")

    async def get_sync_status(self, sync_id: str) -> Dict[str, Any]:
        """Get sync status."""
        return await self.get(f"/syncs/{sync_id}")

    async def run_source_connection_sync(self, source_connection_id: str) -> Dict[str, Any]:
        """Trigger a sync for a source connection."""
        return await self.post(f"/source-connections/{source_connection_id}/run")

    async def get_source_connection_jobs(self, source_connection_id: str) -> List[Dict[str, Any]]:
        """Get sync jobs for a source connection."""
        return await self.get(f"/source-connections/{source_connection_id}/jobs")

    async def delete_source_connection(self, source_connection_id: str) -> Dict[str, Any]:
        """Delete a source connection."""
        return await self.delete(f"/source-connections/{source_connection_id}")
