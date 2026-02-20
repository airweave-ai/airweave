"""Coda source implementation.

Syncs docs, pages, and tables from Coda (https://coda.io) using the Coda API v1.
Supports Personal API Token (DIRECT) and OAuth via Packs.
API reference: https://coda.io/developers/apis/v1
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from airweave.platform.configs.auth import CodaAuthConfig
from airweave.platform.configs.config import CodaConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.coda import (
    CodaDocEntity,
    CodaPageEntity,
    CodaRowEntity,
    CodaTableEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import wait_rate_limit_with_backoff
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

CODA_API_BASE = "https://coda.io/apis/v1"

# Rate limits per Coda API: 100 read/6s, 4 list docs/6s — use conservative pacing
RATE_LIMIT_REQUESTS = 15
RATE_LIMIT_PERIOD = 6.0
TIMEOUT_SECONDS = 30.0


@source(
    name="Coda",
    short_name="coda",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=CodaAuthConfig,
    config_class=CodaConfig,
    labels=["Knowledge Base", "Productivity"],
    supports_continuous=False,
)
class CodaSource(BaseSource):
    """Coda source connector.

    Syncs docs, pages (with content), and tables/rows from Coda.
    Auth: Personal API Token or OAuth (via Packs).
    """

    def __init__(self):
        """Initialize rate limiting state."""
        super().__init__()
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "CodaSource":
        """Create and configure the Coda source.

        Args:
            access_token: Personal API Token (string), or CodaAuthConfig instance
                with api_key (when using DIRECT auth; Pipedream maps api_token to api_key).
            config: Optional config (doc_id filter, folder_id, etc.).

        Returns:
            Configured CodaSource instance.
        """
        instance = cls()
        # DIRECT auth passes CodaAuthConfig; token injection passes a string
        if isinstance(access_token, str):
            instance.access_token = access_token
        elif hasattr(access_token, "api_key"):
            instance.access_token = access_token.api_key
        else:
            raise ValueError(
                "credentials must be a string (API token) or CodaAuthConfig with api_key"
            )
        if config:
            instance.doc_id_filter = config.get("doc_id") or ""
            instance.folder_id_filter = config.get("folder_id") or ""
        else:
            instance.doc_id_filter = ""
            instance.folder_id_filter = ""
        return instance

    async def validate(self) -> bool:
        """Validate credentials by calling the whoami endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{CODA_API_BASE}/whoami",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    async def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting (conservative vs Coda limits)."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            self._request_times = [t for t in self._request_times if now - t < RATE_LIMIT_PERIOD]
            if len(self._request_times) >= RATE_LIMIT_REQUESTS:
                sleep_time = self._request_times[0] + RATE_LIMIT_PERIOD - now
                if sleep_time > 0:
                    self.logger.debug(f"Rate limit: waiting {sleep_time:.2f}s before next request")
                    await asyncio.sleep(sleep_time)
                now = asyncio.get_event_loop().time()
                self._request_times = [
                    t for t in self._request_times if now - t < RATE_LIMIT_PERIOD
                ]
            self._request_times.append(asyncio.get_event_loop().time())

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        stop=stop_after_attempt(5),
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Coda API."""
        await self._wait_for_rate_limit()
        token = await self.get_access_token()
        if not token:
            raise ValueError("No access token available")
        url = f"{CODA_API_BASE}{path}" if path.startswith("/") else f"{CODA_API_BASE}/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await client.get(
            url, headers=headers, params=params or {}, timeout=TIMEOUT_SECONDS
        )
        if response.status_code == 429:
            self.logger.warning("Coda API rate limit (429); retrying after backoff")
            response.raise_for_status()
        response.raise_for_status()
        return response.json()

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string to timezone-naive UTC datetime."""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            return None

    async def _list_docs(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict[str, Any], None]:
        """List all docs the user has access to (with optional filters)."""
        params: Dict[str, Any] = {"limit": 25}
        if self.folder_id_filter:
            params["folderId"] = self.folder_id_filter
        while True:
            data = await self._get(client, "/docs", params=params)
            for item in data.get("items", []):
                if self.doc_id_filter and item.get("id") != self.doc_id_filter:
                    continue
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _list_pages(
        self, client: httpx.AsyncClient, doc_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all pages in a doc."""
        params: Dict[str, Any] = {"limit": 25}
        path = f"/docs/{doc_id}/pages"
        while True:
            data = await self._get(client, path, params=params)
            for item in data.get("items", []):
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _get_page_content(self, client: httpx.AsyncClient, doc_id: str, page_id: str) -> str:
        """Fetch page content as plain text (list content items)."""
        parts: List[str] = []
        params: Dict[str, Any] = {"limit": 100, "contentFormat": "plainText"}
        path = f"/docs/{doc_id}/pages/{page_id}/content"
        while True:
            try:
                data = await self._get(client, path, params=params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404, 410):
                    self.logger.debug(f"Page content not available for {doc_id}/{page_id}: {e}")
                    return ""
                raise
            for item in data.get("items", []):
                content = item.get("itemContent", {})
                if isinstance(content, dict):
                    text = content.get("content", "")
                    if text:
                        parts.append(str(text).strip())
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}
        return "\n\n".join(parts) if parts else ""

    async def _list_tables(
        self, client: httpx.AsyncClient, doc_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all tables in a doc."""
        params: Dict[str, Any] = {"limit": 25}
        path = f"/docs/{doc_id}/tables"
        while True:
            data = await self._get(client, path, params=params)
            for item in data.get("items", []):
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _list_rows(
        self,
        client: httpx.AsyncClient,
        doc_id: str,
        table_id: str,
        value_format: str = "simple",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all rows in a table."""
        params: Dict[str, Any] = {"limit": 25, "valueFormat": value_format}
        path = f"/docs/{doc_id}/tables/{table_id}/rows"
        while True:
            data = await self._get(client, path, params=params)
            for item in data.get("items", []):
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    def _row_values_to_text(self, values: Dict[str, Any]) -> str:
        """Turn row values dict into a single searchable string."""
        if not values:
            return ""
        parts = []
        for _, v in values.items():
            if v is None:
                continue
            if isinstance(v, list):
                parts.append(" ".join(str(x) for x in v))
            else:
                parts.append(str(v))
        return " | ".join(parts)

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all Coda entities: docs, pages (with content), tables, rows."""
        self.logger.info("Starting Coda sync")
        async with self.http_client() as client:
            async for doc_data in self._list_docs(client):
                doc_id = doc_data.get("id") or ""
                doc_name = doc_data.get("name") or "Untitled"
                doc_link = doc_data.get("browserLink") or ""
                workspace = doc_data.get("workspace", {}) or {}
                folder = doc_data.get("folder", {}) or {}
                doc_entity = CodaDocEntity(
                    entity_id=doc_id,
                    breadcrumbs=[],
                    doc_id=doc_id,
                    name=doc_name,
                    owner=doc_data.get("owner"),
                    owner_name=doc_data.get("ownerName"),
                    created_at=self._parse_datetime(doc_data.get("createdAt")),
                    updated_at=self._parse_datetime(doc_data.get("updatedAt")),
                    workspace_name=workspace.get("name") if isinstance(workspace, dict) else None,
                    folder_name=folder.get("name") if isinstance(folder, dict) else None,
                    browser_link=doc_link,
                )
                yield doc_entity

                doc_breadcrumb = Breadcrumb(
                    entity_id=doc_id,
                    name=doc_name,
                    entity_type=CodaDocEntity.__name__,
                )

                # Pages
                async for page_data in self._list_pages(client, doc_id):
                    page_id = page_data.get("id") or ""
                    page_name = page_data.get("name") or "Untitled"
                    page_link = page_data.get("browserLink") or ""
                    if page_data.get("isEffectivelyHidden") or page_data.get("isHidden"):
                        self.logger.debug(f"Skipping hidden page: {page_name}")
                        continue
                    content = await self._get_page_content(client, doc_id, page_id)
                    page_entity = CodaPageEntity(
                        entity_id=page_id,
                        breadcrumbs=[doc_breadcrumb],
                        page_id=page_id,
                        name=page_name,
                        subtitle=page_data.get("subtitle"),
                        doc_id=doc_id,
                        doc_name=doc_name,
                        content=content or None,
                        content_type=page_data.get("contentType"),
                        created_at=self._parse_datetime(page_data.get("createdAt")),
                        updated_at=self._parse_datetime(page_data.get("updatedAt")),
                        browser_link=page_link,
                    )
                    yield page_entity

                # Tables and rows
                async for table_data in self._list_tables(client, doc_id):
                    table_id = table_data.get("id") or ""
                    table_name = table_data.get("name") or "Untitled"
                    table_link = table_data.get("browserLink") or ""
                    parent = table_data.get("parent", {}) or {}
                    parent_name = parent.get("name") if isinstance(parent, dict) else None
                    try:
                        full_table = await self._get(client, f"/docs/{doc_id}/tables/{table_id}")
                        row_count = full_table.get("rowCount", 0)
                        created_at = self._parse_datetime(full_table.get("createdAt"))
                        updated_at = self._parse_datetime(full_table.get("updatedAt"))
                    except Exception as e:
                        self.logger.warning(f"Could not fetch table {table_id}: {e}")
                        row_count = 0
                        created_at = None
                        updated_at = None

                    table_entity = CodaTableEntity(
                        entity_id=table_id,
                        breadcrumbs=[doc_breadcrumb],
                        table_id=table_id,
                        name=table_name,
                        table_type=table_data.get("tableType"),
                        doc_id=doc_id,
                        doc_name=doc_name,
                        page_name=parent_name,
                        row_count=row_count,
                        created_at=created_at,
                        updated_at=updated_at,
                        browser_link=table_link,
                    )
                    yield table_entity

                    table_breadcrumb = Breadcrumb(
                        entity_id=table_id,
                        name=table_name,
                        entity_type=CodaTableEntity.__name__,
                    )
                    row_breadcrumbs = [doc_breadcrumb, table_breadcrumb]

                    async for row_data in self._list_rows(client, doc_id, table_id):
                        row_id = row_data.get("id") or ""
                        row_name = row_data.get("name") or "Untitled"
                        values = row_data.get("values") or {}
                        row_link = row_data.get("browserLink") or ""
                        values_text = self._row_values_to_text(values)
                        row_entity = CodaRowEntity(
                            entity_id=row_id,
                            breadcrumbs=row_breadcrumbs,
                            row_id=row_id,
                            name=row_name,
                            table_id=table_id,
                            table_name=table_name,
                            doc_id=doc_id,
                            values=values,
                            values_text=values_text or None,
                            created_at=self._parse_datetime(row_data.get("createdAt")),
                            updated_at=self._parse_datetime(row_data.get("updatedAt")),
                            browser_link=row_link,
                        )
                        yield row_entity

        self.logger.info("Coda sync completed")
