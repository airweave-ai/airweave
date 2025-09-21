"""Airtable source implementation for Airweave platform."""

from __future__ import annotations

import asyncio
import io
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import AirtableAuthConfig
from airweave.platform.configs.config import AirtableConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.airtable import (
    AirtableAttachmentEntity,
    AirtableBaseEntity,
    AirtableRecordEntity,
    AirtableTableEntity,
)
from airweave.platform.sources._base import BaseSource

API = "https://api.airtable.com/v0"


@source(
    name="Airtable",
    short_name="airtable",
    auth_type=AuthType.oauth2_with_refresh,  # OAuth 2.0 with refresh
    auth_config_class="AirtableAuthConfig",  # BYOC client credentials
    config_class="AirtableConfig",
    labels=["Database", "Spreadsheet"],
)
class AirtableSource(BaseSource):
    """Airtable connector (OAuth 2.0; full sync; attachments supported; no incremental)."""

    @classmethod
    async def create(
        cls,
        credentials: AirtableAuthConfig | None = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "AirtableSource":
        """Create an AirtableSource instance with the given credentials and config.

        Args:
            credentials: OAuth credentials for Airtable API access
            config: Optional configuration dictionary for behavior settings

        Returns:
            Configured AirtableSource instance
        """
        inst = cls()
        inst.cfg = AirtableConfig(**(config or {}))
        # Access tokens are obtained from the token manager (BaseSource handles it).
        return inst

    # ----------------------------- HTTP helpers -----------------------------

    async def _bearer_headers(self) -> Dict[str, str]:
        token = await self.get_access_token()
        if not token:
            raise ValueError("No OAuth access token available for Airtable")
        return {"Authorization": f"Bearer {token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPError)),
        reraise=True,
    )
    async def _get(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ):
        """GET with OAuth bearer and polite 429 handling."""
        for _ in range(4):
            headers = await self._bearer_headers()
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 401 and self.token_manager:
                # attempt refresh then retry once
                await self.token_manager.refresh_on_unauthorized()
                headers = await self._bearer_headers()
                resp = await client.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 429:
                # 5 rps per base; obey Retry-After or wait up to ~30s
                ra = resp.headers.get("Retry-After")
                delay = float(ra) if ra else 30.0
                self.logger.warning(f"Airtable 429 on {url}. Sleeping {delay}s…")
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()  # type: ignore[misc]
        return {}

    # ----------------------------- Meta API (bases & tables) -----------------------------

    async def _list_bases(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """List all accessible bases via Meta API."""
        url = f"{API}/meta/bases"
        out: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {}
        while True:
            data = await self._get(client, url, params=params)
            bases = data.get("bases") or data.get("data") or data.get("results") or []
            for base_data in bases:
                if isinstance(base_data, dict):
                    out.append(base_data)
            offset = data.get("offset")
            if not offset:
                break
            params["offset"] = offset
        return out

    async def _get_base_tables(
        self, client: httpx.AsyncClient, base_id: str
    ) -> List[Dict[str, Any]]:
        """Return schema tables for a base."""
        url = f"{API}/meta/bases/{base_id}/tables"
        data = await self._get(client, url)
        tables = data.get("tables") or []
        return [table for table in tables if isinstance(table, dict)]

    # ----------------------------- Records listing -----------------------------

    async def _iter_records(
        self,
        client: httpx.AsyncClient,
        base_id: str,
        table_id_or_name: str,
        page_size: Optional[int],
        max_records: Optional[int],
        view: Optional[str],
        filter_by_formula: Optional[str],
        fields: List[str],
    ):
        """Stream all records from a table, honoring pagination and caps."""
        url = f"{API}/{base_id}/{table_id_or_name}"
        params: Dict[str, Any] = {}
        if page_size:
            params["pageSize"] = min(int(page_size), 100)
        if max_records:
            params["maxRecords"] = int(max_records)
        if view:
            params["view"] = view
        if filter_by_formula:
            params["filterByFormula"] = filter_by_formula
        for field in fields or []:
            params.setdefault("fields[]", [])
            params["fields[]"].append(field)

        while True:
            data = await self._get(client, url, params=params)
            for rec in data.get("records", []):
                yield rec
            offset = data.get("offset")
            if not offset:
                break
            params["offset"] = offset

    # ----------------------------- Builders -----------------------------

    def _base_entity(self, base_data: Dict[str, Any]) -> AirtableBaseEntity:
        url = f"https://airtable.com/{base_data.get('id')}" if base_data.get("id") else None
        content = base_data.get("name") or ""
        return AirtableBaseEntity(
            entity_id=base_data["id"],
            base_id=base_data["id"],
            name=base_data.get("name"),
            permission_level=base_data.get("permissionLevel"),
            url=url,
            content=content or None,
            breadcrumbs=[],
        )

    def _table_entity(self, table_data: Dict[str, Any], base_id: str) -> AirtableTableEntity:
        content = table_data.get("name") or ""
        return AirtableTableEntity(
            entity_id=table_data["id"],
            table_id=table_data["id"],
            base_id=base_id,
            name=table_data.get("name", ""),
            description=table_data.get("description"),
            fields_schema=table_data.get("fields"),
            content=content or None,
            breadcrumbs=[Breadcrumb(entity_id=base_id, name="", type="base")],
        )

    def _record_entity(
        self, rec: Dict[str, Any], base_id: str, table_id: str, table_name: str
    ) -> AirtableRecordEntity:
        fields = rec.get("fields") or {}
        # Concise content for search
        kv_pairs = []
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                kv_pairs.append(f"{key}: {value}")
            elif (
                isinstance(value, list) and value and isinstance(value[0], (str, int, float, bool))
            ):
                kv_pairs.append(f"{key}: {', '.join(map(str, value[:5]))}")
        content = "\n".join(kv_pairs[:30]) if kv_pairs else None

        return AirtableRecordEntity(
            entity_id=rec["id"],
            record_id=rec["id"],
            base_id=base_id,
            table_id=table_id,
            table_name=table_name,
            fields=fields,
            created_time=rec.get("createdTime"),
            content=content,
            breadcrumbs=[
                Breadcrumb(entity_id=base_id, name="", type="base"),
                Breadcrumb(entity_id=table_id, name=table_name or "", type="table"),
            ],
        )

    def _extract_attachments(
        self,
        rec: Dict[str, Any],
        base_id: str,
        table_id: str,
        table_name: str,
        record_id: str,
    ) -> List[AirtableAttachmentEntity]:
        out: List[AirtableAttachmentEntity] = []
        fields = rec.get("fields") or {}
        for field_name, val in fields.items():
            if not isinstance(val, list):
                continue
            for item in val:
                if not isinstance(item, dict):
                    continue
                url = item.get("url")
                fname = item.get("filename") or item.get("name") or "attachment"
                mime = item.get("type")
                size = item.get("size")
                att_id = item.get("id") or f"{record_id}:{field_name}:{fname}"
                if url:
                    out.append(
                        AirtableAttachmentEntity(
                            entity_id=att_id,
                            file_id=att_id,
                            name=fname,
                            mime_type=mime,
                            size=int(size) if isinstance(size, int) else None,
                            download_url=url,  # expires after a few hours
                            base_id=base_id,
                            table_id=table_id,
                            table_name=table_name,
                            record_id=record_id,
                            field_name=field_name,
                            breadcrumbs=[
                                Breadcrumb(entity_id=base_id, name="", type="base"),
                                Breadcrumb(entity_id=table_id, name=table_name or "", type="table"),
                            ],
                        )
                    )
        return out

    # ----------------------------- Processing helpers -----------------------------

    async def _fetch_bases(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Fetch bases based on configuration."""
        try:
            if self.cfg.base_ids:
                return [{"id": base_id, "name": None} for base_id in self.cfg.base_ids]
            else:
                return await self._list_bases(client)
        except Exception as e:
            self.logger.error(f"Airtable: failed to list bases: {e}")
            return []

    async def _process_base_entities(
        self, bases: List[Dict[str, Any]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process and yield base entities."""
        for base_data in bases:
            try:
                if isinstance(base_data, dict) and base_data.get("id"):
                    yield self._base_entity(base_data)
            except Exception as e:
                self.logger.error(f"Airtable: base entity error: {e}")

    def _filter_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter tables based on configuration."""
        include_by_id = set((self.cfg.table_ids or []))
        include_by_name = {x.lower() for x in (self.cfg.table_names or [])}

        use_tables: List[Dict[str, Any]] = []
        for table in tables:
            table_id = table.get("id") or ""
            table_name = table.get("name") or ""
            if include_by_id and table_id not in include_by_id:
                continue
            if include_by_name and table_name.lower() not in include_by_name:
                continue
            use_tables.append(table)
        return use_tables if use_tables else tables

    async def _process_table_entities(
        self, tables: List[Dict[str, Any]], base_id: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process and yield table entities."""
        for table in tables:
            try:
                yield self._table_entity(table, base_id=base_id)
            except Exception as e:
                self.logger.error(f"Airtable: table entity error: {e}")

    async def _process_attachment(
        self, client: httpx.AsyncClient, att: AirtableAttachmentEntity
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a single attachment."""
        # Optional size cap
        if self.cfg.attachment_max_bytes and att.size and att.size > self.cfg.attachment_max_bytes:
            self.logger.info(f"Skipping large attachment {att.name} ({att.size} bytes)")
            return

        try:
            # Download immediately (URL expires)
            response = await client.get(att.download_url, timeout=60.0)
            response.raise_for_status()
            stream = io.BytesIO(response.content)
            processed = await self.process_file_entity_with_content(
                file_entity=att, content_stream=stream
            )
            if processed:
                yield processed
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Airtable: download failed for attachment {att.file_id}: {e}")
        except Exception as e:
            self.logger.error(f"Airtable: attachment processing error: {e}")

    async def _process_table_records(
        self, client: httpx.AsyncClient, table: Dict[str, Any], base_id: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process all records for a single table."""
        table_id = table.get("id") or ""
        table_name = table.get("name") or ""
        table_key = table_id or table_name
        if not table_key:
            return

        try:
            async for rec in self._iter_records(
                client=client,
                base_id=base_id,
                table_id_or_name=table_key,
                page_size=self.cfg.page_size,
                max_records=self.cfg.max_records,
                view=self.cfg.view,
                filter_by_formula=self.cfg.filter_by_formula,
                fields=self.cfg.fields,
            ):
                try:
                    # Record chunk
                    yield self._record_entity(rec, base_id, table_id or "", table_name)

                    # Attachments
                    if self.cfg.include_attachments:
                        attachments = self._extract_attachments(
                            rec, base_id, table_id or "", table_name, rec["id"]
                        )
                        for att in attachments:
                            async for processed_att in self._process_attachment(client, att):
                                yield processed_att

                except Exception as e:
                    self.logger.error(f"Airtable: record processing error: {e}")

        except Exception as e:
            self.logger.error(f"Airtable: failed to list records for {base_id}/{table_key}: {e}")

    async def _process_base_tables_and_records(
        self, client: httpx.AsyncClient, base_data: Dict[str, Any]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process tables and records for a single base."""
        base_id = base_data.get("id")
        if not base_id:
            return

        try:
            tables = await self._get_base_tables(client, base_id)
        except Exception as e:
            self.logger.error(f"Airtable: failed to list tables for base {base_id}: {e}")
            tables = []

        # Filter tables based on config
        use_tables = self._filter_tables(tables)

        # Emit table entities
        async for table_entity in self._process_table_entities(use_tables, base_id):
            yield table_entity

        # Process records for each table
        for table in use_tables:
            async for record_entity in self._process_table_records(client, table, base_id):
                yield record_entity

    # ----------------------------- Main sync -----------------------------

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Full sync (read-only).

        Processes:
        - Bases (meta)
        - Tables per base (schema)
        - Records per table (data)
        - Optional: attachments (download & process via file manager)
        """
        async with httpx.AsyncClient() as client:
            # Fetch and yield bases
            bases = await self._fetch_bases(client)
            async for base_entity in self._process_base_entities(bases):
                yield base_entity

            # Process tables and records for each base
            for base_data in bases:
                async for entity in self._process_base_tables_and_records(client, base_data):
                    yield entity
