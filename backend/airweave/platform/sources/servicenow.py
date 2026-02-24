"""ServiceNow source implementation.

Syncs Incidents, Knowledge Base Articles, Change Requests, Problem Records,
and Service Catalog Items from a ServiceNow instance via the Table API.

Reference:
    ServiceNow Table API: https://www.servicenow.com/docs/r/washingtondc/api-reference/rest-apis/api-rest.html
"""

import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.configs.auth import ServiceNowAuthConfig
from airweave.platform.configs.config import ServiceNowConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.servicenow import (
    ServiceNowCatalogItemEntity,
    ServiceNowChangeRequestEntity,
    ServiceNowIncidentEntity,
    ServiceNowKnowledgeArticleEntity,
    ServiceNowProblemEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Table API base path (v1)
TABLE_API_PATH = "/api/now/table"
# Page size for pagination (ServiceNow default max is 10k; use 1k for stability)
PAGE_LIMIT = 1000


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ServiceNow datetime string (ISO-like) to datetime."""
    if not value:
        return None
    try:
        # ServiceNow returns 'yyyy-MM-dd HH:mm:ss' or ISO format
        s = value.strip().replace("Z", "+00:00")
        if "T" in s:
            return datetime.fromisoformat(s)
        # No T: assume space-separated date time
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _display_value(record: Dict[str, Any], key: str) -> Optional[str]:
    """Get display value from record; ServiceNow can return {value, display_value}."""
    raw = record.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("display_value") or raw.get("value")
    return str(raw) if raw else None


def _raw_value(record: Dict[str, Any], key: str) -> Optional[str]:
    """Get raw value from record."""
    raw = record.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("value") or raw.get("display_value")
    return str(raw) if raw else None


def _parse_bool(value: Any) -> Optional[bool]:
    """Parse ServiceNow boolean-like value (bool, str 'true'/'false', 0/1) to bool or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return None


@source(
    name="ServiceNow",
    short_name="servicenow",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=ServiceNowAuthConfig,
    config_class=ServiceNowConfig,
    labels=["ITSM", "Service Management", "IT Operations"],
    supports_continuous=False,
)
class ServiceNowSource(BaseSource):
    """ServiceNow source connector.

    Syncs Incidents, Knowledge Base Articles, Change Requests, Problem Records,
    and Service Catalog Items from a ServiceNow instance using the Table API
    with Basic Auth (instance URL, username, password).
    """

    def __init__(self) -> None:
        """Initialize ServiceNow source."""
        super().__init__()
        self._base_url: str = ""
        self._auth_header: str = ""

    @classmethod
    async def create(
        cls,
        credentials: ServiceNowAuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "ServiceNowSource":
        """Create a new ServiceNow source instance.

        Args:
            credentials: ServiceNowAuthConfig with url, username, password
            config: Optional configuration (unused for MVP)

        Returns:
            Configured ServiceNowSource instance
        """
        instance = cls()
        base = credentials.url.rstrip("/")
        instance._base_url = base
        token = base64.b64encode(f"{credentials.username}:{credentials.password}".encode()).decode()
        instance._auth_header = f"Basic {token}"
        return instance

    def _table_url(self, table: str) -> str:
        """Build full Table API URL for a table."""
        return f"{self._base_url}{TABLE_API_PATH}/{table}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request to ServiceNow Table API."""
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        response = await client.get(url, headers=headers, params=params, timeout=60.0)
        response.raise_for_status()
        return response.json()

    async def _fetch_table_paginated(
        self,
        client: httpx.AsyncClient,
        table: str,
        fields: List[str],
        order_by: str = "sys_created_on",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all records from a table with pagination."""
        url = self._table_url(table)
        offset = 0
        params_base: Dict[str, Any] = {
            "sysparm_limit": PAGE_LIMIT,
            "sysparm_display_value": "true",
            "sysparm_fields": ",".join(fields),
            "sysparm_order_by": order_by,
        }
        while True:
            params = {**params_base, "sysparm_offset": offset}
            data = await self._get_with_auth(client, url, params=params)
            results = data.get("result") or []
            for rec in results:
                yield rec
            if len(results) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT

    def _build_record_url(self, table: str, sys_id: str) -> str:
        """Build user-facing URL for a record (UI navigates to list with sys_id)."""
        # Standard UI pattern: /now/nav/ui/classic/params/target/<table>.do%3Fsys_id=<sys_id>
        return f"{self._base_url}/now/nav/ui/classic/params/target/{table}.do%3Fsys_id={sys_id}"

    async def _generate_incidents(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Incident entities (table: incident)."""
        fields = [
            "sys_id",
            "number",
            "short_description",
            "description",
            "state",
            "priority",
            "category",
            "assigned_to",
            "caller_id",
            "sys_created_on",
            "sys_updated_on",
        ]
        async for rec in self._fetch_table_paginated(client, "incident", fields):
            sys_id = _raw_value(rec, "sys_id") or rec.get("sys_id", "")
            number = _display_value(rec, "number") or _raw_value(rec, "number") or sys_id
            created = _parse_datetime(_raw_value(rec, "sys_created_on"))
            updated = _parse_datetime(_raw_value(rec, "sys_updated_on"))
            assigned_to = rec.get("assigned_to")
            assigned_to_name = None
            if isinstance(assigned_to, dict):
                assigned_to_name = assigned_to.get("display_value") or assigned_to.get("value")
            elif assigned_to:
                assigned_to_name = str(assigned_to)
            caller_id = rec.get("caller_id")
            caller_id_name = None
            if isinstance(caller_id, dict):
                caller_id_name = caller_id.get("display_value") or caller_id.get("value")
            elif caller_id:
                caller_id_name = str(caller_id)
            yield ServiceNowIncidentEntity(
                entity_id=sys_id,
                breadcrumbs=[],
                name=number,
                sys_id=sys_id,
                number=number,
                short_description=_display_value(rec, "short_description")
                or _raw_value(rec, "short_description"),
                description=_display_value(rec, "description") or _raw_value(rec, "description"),
                state=_display_value(rec, "state") or _raw_value(rec, "state"),
                priority=_display_value(rec, "priority") or _raw_value(rec, "priority"),
                category=_display_value(rec, "category") or _raw_value(rec, "category"),
                assigned_to_name=assigned_to_name,
                caller_id_name=caller_id_name,
                created_at=created,
                updated_at=updated,
                web_url_value=self._build_record_url("incident", sys_id),
            )

    async def _generate_kb_articles(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Knowledge Base Article entities (table: kb_knowledge)."""
        fields = [
            "sys_id",
            "number",
            "short_description",
            "text",
            "author",
            "kb_knowledge_base",
            "category",
            "workflow_state",
            "sys_created_on",
            "sys_updated_on",
        ]
        async for rec in self._fetch_table_paginated(client, "kb_knowledge", fields):
            sys_id = _raw_value(rec, "sys_id") or rec.get("sys_id", "")
            number = _display_value(rec, "number") or _raw_value(rec, "number") or sys_id
            short_desc = _display_value(rec, "short_description") or _raw_value(
                rec, "short_description"
            )
            created = _parse_datetime(_raw_value(rec, "sys_created_on"))
            updated = _parse_datetime(_raw_value(rec, "sys_updated_on"))
            author = rec.get("author")
            author_name = None
            if isinstance(author, dict):
                author_name = author.get("display_value") or author.get("value")
            elif author:
                author_name = str(author)
            kb_base = rec.get("kb_knowledge_base")
            kb_base_name = None
            if isinstance(kb_base, dict):
                kb_base_name = kb_base.get("display_value") or kb_base.get("value")
            elif kb_base:
                kb_base_name = str(kb_base)
            cat = rec.get("category")
            category_name = None
            if isinstance(cat, dict):
                category_name = cat.get("display_value") or cat.get("value")
            elif cat:
                category_name = str(cat)
            yield ServiceNowKnowledgeArticleEntity(
                entity_id=sys_id,
                breadcrumbs=[],
                name=number,
                sys_id=sys_id,
                number=number,
                short_description=short_desc,
                text=_display_value(rec, "text") or _raw_value(rec, "text"),
                author_name=author_name,
                kb_knowledge_base_name=kb_base_name,
                category_name=category_name,
                workflow_state=_display_value(rec, "workflow_state")
                or _raw_value(rec, "workflow_state"),
                created_at=created,
                updated_at=updated,
                web_url_value=self._build_record_url("kb_knowledge", sys_id),
            )

    async def _generate_change_requests(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Change Request entities (table: change_request)."""
        fields = [
            "sys_id",
            "number",
            "short_description",
            "description",
            "state",
            "phase",
            "priority",
            "type",
            "assigned_to",
            "requested_by",
            "sys_created_on",
            "sys_updated_on",
        ]
        async for rec in self._fetch_table_paginated(client, "change_request", fields):
            sys_id = _raw_value(rec, "sys_id") or rec.get("sys_id", "")
            number = _display_value(rec, "number") or _raw_value(rec, "number") or sys_id
            created = _parse_datetime(_raw_value(rec, "sys_created_on"))
            updated = _parse_datetime(_raw_value(rec, "sys_updated_on"))
            assigned_to = rec.get("assigned_to")
            assigned_to_name = None
            if isinstance(assigned_to, dict):
                assigned_to_name = assigned_to.get("display_value") or assigned_to.get("value")
            elif assigned_to:
                assigned_to_name = str(assigned_to)
            requested_by = rec.get("requested_by")
            requested_by_name = None
            if isinstance(requested_by, dict):
                requested_by_name = requested_by.get("display_value") or requested_by.get("value")
            elif requested_by:
                requested_by_name = str(requested_by)
            yield ServiceNowChangeRequestEntity(
                entity_id=sys_id,
                breadcrumbs=[],
                name=number,
                sys_id=sys_id,
                number=number,
                short_description=_display_value(rec, "short_description")
                or _raw_value(rec, "short_description"),
                description=_display_value(rec, "description") or _raw_value(rec, "description"),
                state=_display_value(rec, "state") or _raw_value(rec, "state"),
                phase=_display_value(rec, "phase") or _raw_value(rec, "phase"),
                priority=_display_value(rec, "priority") or _raw_value(rec, "priority"),
                type=_display_value(rec, "type") or _raw_value(rec, "type"),
                assigned_to_name=assigned_to_name,
                requested_by_name=requested_by_name,
                created_at=created,
                updated_at=updated,
                web_url_value=self._build_record_url("change_request", sys_id),
            )

    async def _generate_problems(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Problem entities (table: problem)."""
        fields = [
            "sys_id",
            "number",
            "short_description",
            "description",
            "state",
            "priority",
            "category",
            "assigned_to",
            "sys_created_on",
            "sys_updated_on",
        ]
        async for rec in self._fetch_table_paginated(client, "problem", fields):
            sys_id = _raw_value(rec, "sys_id") or rec.get("sys_id", "")
            number = _display_value(rec, "number") or _raw_value(rec, "number") or sys_id
            created = _parse_datetime(_raw_value(rec, "sys_created_on"))
            updated = _parse_datetime(_raw_value(rec, "sys_updated_on"))
            assigned_to = rec.get("assigned_to")
            assigned_to_name = None
            if isinstance(assigned_to, dict):
                assigned_to_name = assigned_to.get("display_value") or assigned_to.get("value")
            elif assigned_to:
                assigned_to_name = str(assigned_to)
            yield ServiceNowProblemEntity(
                entity_id=sys_id,
                breadcrumbs=[],
                name=number,
                sys_id=sys_id,
                number=number,
                short_description=_display_value(rec, "short_description")
                or _raw_value(rec, "short_description"),
                description=_display_value(rec, "description") or _raw_value(rec, "description"),
                state=_display_value(rec, "state") or _raw_value(rec, "state"),
                priority=_display_value(rec, "priority") or _raw_value(rec, "priority"),
                category=_display_value(rec, "category") or _raw_value(rec, "category"),
                assigned_to_name=assigned_to_name,
                created_at=created,
                updated_at=updated,
                web_url_value=self._build_record_url("problem", sys_id),
            )

    async def _generate_catalog_items(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Service Catalog Item entities (table: sc_cat_item)."""
        fields = [
            "sys_id",
            "name",
            "short_description",
            "description",
            "category",
            "price",
            "active",
            "sys_created_on",
            "sys_updated_on",
        ]
        async for rec in self._fetch_table_paginated(client, "sc_cat_item", fields):
            sys_id = _raw_value(rec, "sys_id") or rec.get("sys_id", "")
            name = _display_value(rec, "name") or _raw_value(rec, "name") or sys_id
            created = _parse_datetime(_raw_value(rec, "sys_created_on"))
            updated = _parse_datetime(_raw_value(rec, "sys_updated_on"))
            cat = rec.get("category")
            category_name = None
            if isinstance(cat, dict):
                category_name = cat.get("display_value") or cat.get("value")
            elif cat:
                category_name = str(cat)
            active_val = rec.get("active")
            if isinstance(active_val, dict):
                active_val = active_val.get("value") if active_val else None
            yield ServiceNowCatalogItemEntity(
                entity_id=sys_id,
                breadcrumbs=[],
                name=name,
                sys_id=sys_id,
                short_description=_display_value(rec, "short_description")
                or _raw_value(rec, "short_description"),
                description=_display_value(rec, "description") or _raw_value(rec, "description"),
                category_name=category_name,
                price=_display_value(rec, "price") or _raw_value(rec, "price"),
                active=_parse_bool(active_val),
                created_at=created,
                updated_at=updated,
                web_url_value=self._build_record_url("sc_cat_item", sys_id),
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all MVP entities from the ServiceNow instance."""
        self.logger.info("Starting ServiceNow sync")
        async with self.http_client() as client:
            async for entity in self._generate_incidents(client):
                yield entity
            async for entity in self._generate_kb_articles(client):
                yield entity
            async for entity in self._generate_change_requests(client):
                yield entity
            async for entity in self._generate_problems(client):
                yield entity
            async for entity in self._generate_catalog_items(client):
                yield entity
        self.logger.info("ServiceNow sync completed")

    async def validate(self) -> bool:
        """Validate credentials by querying the instance (minimal table read)."""
        try:
            async with self.http_client() as client:
                url = self._table_url("incident")
                params = {"sysparm_limit": 1, "sysparm_fields": "sys_id"}
                await self._get_with_auth(client, url, params=params)
            return True
        except Exception as e:
            self.logger.warning(f"ServiceNow validation failed: {e}")
            return False
