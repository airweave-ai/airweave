"""Coda source implementation.

Syncs docs, pages, and tables from Coda (https://coda.io) using the Coda API v1.
Supports Personal API Token (DIRECT) and OAuth via Packs.
API reference: https://coda.io/developers/apis/v1
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import CodaAuthConfig
from airweave.platform.configs.config import CodaConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.coda import (
    CodaDocEntity,
    CodaPageEntity,
    CodaRowEntity,
    CodaTableEntity,
    _parse_dt,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

CODA_API_BASE = "https://coda.io/apis/v1"
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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: CodaConfig,
    ) -> CodaSource:
        """Create and configure the Coda source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._doc_id_filter = (config.doc_id or "") if config else ""
        instance._folder_id_filter = (config.folder_id or "") if config else ""
        return instance

    async def validate(self) -> None:
        """Validate credentials by pinging Coda's whoami endpoint."""
        await self._get("/whoami")

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Coda API."""
        if self.auth.provider_kind == AuthProviderKind.CREDENTIAL:
            token = self.auth.credentials.api_key
        else:
            token = await self.auth.get_token()
        url = f"{CODA_API_BASE}{path}" if path.startswith("/") else f"{CODA_API_BASE}/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(
            url, headers=headers, params=params or {}, timeout=TIMEOUT_SECONDS
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Pagination helpers
    # ------------------------------------------------------------------

    async def _list_docs(self) -> AsyncGenerator[Dict[str, Any], None]:
        """List all docs the user has access to (with optional filters)."""
        params: Dict[str, Any] = {"limit": 25}
        if self._folder_id_filter:
            params["folderId"] = self._folder_id_filter
        while True:
            data = await self._get("/docs", params=params)
            for item in data.get("items", []):
                if self._doc_id_filter and item.get("id") != self._doc_id_filter:
                    continue
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _list_pages(self, doc_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """List all pages in a doc."""
        params: Dict[str, Any] = {"limit": 25}
        path = f"/docs/{doc_id}/pages"
        while True:
            data = await self._get(path, params=params)
            for item in data.get("items", []):
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _get_page_content(self, doc_id: str, page_id: str) -> str:
        """Fetch page content as plain text (list content items)."""
        from airweave.domains.sources.exceptions import (
            SourceEntityForbiddenError,
            SourceEntityNotFoundError,
        )

        parts: List[str] = []
        params: Dict[str, Any] = {"limit": 100, "contentFormat": "plainText"}
        path = f"/docs/{doc_id}/pages/{page_id}/content"
        while True:
            try:
                data = await self._get(path, params=params)
            except (SourceEntityForbiddenError, SourceEntityNotFoundError):
                self.logger.debug(f"Page content not available for {doc_id}/{page_id}")
                return ""
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

    async def _list_tables(self, doc_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """List all tables in a doc."""
        params: Dict[str, Any] = {"limit": 25}
        path = f"/docs/{doc_id}/tables"
        while True:
            data = await self._get(path, params=params)
            for item in data.get("items", []):
                yield item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params = {"pageToken": page_token}

    async def _list_rows(
        self,
        doc_id: str,
        table_id: str,
        value_format: str = "simple",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all rows in a table."""
        params: Dict[str, Any] = {"limit": 25, "valueFormat": value_format}
        path = f"/docs/{doc_id}/tables/{table_id}/rows"
        while True:
            data = await self._get(path, params=params)
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

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Generate all Coda entities: docs, pages (with content), tables, rows."""
        self.logger.info("Starting Coda sync")

        async for doc_data in self._list_docs():
            doc_entity = CodaDocEntity.from_api(doc_data)
            yield doc_entity

            doc_id = doc_entity.doc_id
            doc_name = doc_entity.name

            doc_breadcrumb = Breadcrumb(
                entity_id=doc_id,
                name=doc_name,
                entity_type=CodaDocEntity.__name__,
            )

            async for page_data in self._list_pages(doc_id):
                if page_data.get("isEffectivelyHidden") or page_data.get("isHidden"):
                    self.logger.debug(f"Skipping hidden page: {page_data.get('name')}")
                    continue

                page_id = page_data.get("id") or ""
                content = await self._get_page_content(doc_id, page_id)

                yield CodaPageEntity.from_api(
                    page_data,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    breadcrumbs=[doc_breadcrumb],
                    content=content,
                )

            async for table_data in self._list_tables(doc_id):
                table_id = table_data.get("id") or ""
                table_name = table_data.get("name") or "Untitled"
                table_link = table_data.get("browserLink") or ""
                parent = table_data.get("parent", {}) or {}
                parent_name = parent.get("name") if isinstance(parent, dict) else None
                try:
                    full_table = await self._get(f"/docs/{doc_id}/tables/{table_id}")
                    row_count = full_table.get("rowCount", 0)
                    created_at = _parse_dt(full_table.get("createdAt"))
                    updated_at = _parse_dt(full_table.get("updatedAt"))
                except SourceAuthError:
                    raise
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

                async for row_data in self._list_rows(doc_id, table_id):
                    row_id = row_data.get("id") or ""
                    row_name = row_data.get("name") or "Untitled"
                    values = row_data.get("values") or {}
                    row_link = row_data.get("browserLink") or ""
                    values_text = self._row_values_to_text(values)
                    yield CodaRowEntity(
                        entity_id=row_id,
                        breadcrumbs=row_breadcrumbs,
                        row_id=row_id,
                        name=row_name,
                        table_id=table_id,
                        table_name=table_name,
                        doc_id=doc_id,
                        values=values,
                        values_text=values_text or None,
                        created_at=_parse_dt(row_data.get("createdAt")),
                        updated_at=_parse_dt(row_data.get("updatedAt")),
                        browser_link=row_link,
                    )

        self.logger.info("Coda sync completed")
