"""ServiceNow source implementation.

Syncs Incidents, Knowledge Base Articles, Change Requests, Problem Records,
and Service Catalog Items from a ServiceNow instance via the Table API.

Reference:
    ServiceNow Table API: https://www.servicenow.com/docs/r/washingtondc/api-reference/rest-apis/api-rest.html
"""

import base64
from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

TABLE_API_PATH = "/api/now/table"
PAGE_LIMIT = 1000


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

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ServiceNowConfig,
    ) -> "ServiceNowSource":
        """Create a new ServiceNow source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        creds: ServiceNowAuthConfig = auth.credentials
        instance._base_url = creds.url.rstrip("/")
        token = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
        instance._auth_header = f"Basic {token}"
        return instance

    def _table_url(self, table: str) -> str:
        """Build full Table API URL for a table."""
        return f"{self._base_url}{TABLE_API_PATH}/{table}"

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request to ServiceNow Table API."""
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        response = await self.http_client.get(url, headers=headers, params=params)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _fetch_table_paginated(
        self,
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
            data = await self._get(url, params=params)
            results = data.get("result") or []
            for rec in results:
                yield rec
            if len(results) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT

    async def _generate_incidents(self) -> AsyncGenerator[BaseEntity, None]:
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
        async for rec in self._fetch_table_paginated("incident", fields):
            yield ServiceNowIncidentEntity.from_api(rec, base_url=self._base_url)

    async def _generate_kb_articles(self) -> AsyncGenerator[BaseEntity, None]:
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
        async for rec in self._fetch_table_paginated("kb_knowledge", fields):
            yield ServiceNowKnowledgeArticleEntity.from_api(rec, base_url=self._base_url)

    async def _generate_change_requests(self) -> AsyncGenerator[BaseEntity, None]:
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
        async for rec in self._fetch_table_paginated("change_request", fields):
            yield ServiceNowChangeRequestEntity.from_api(rec, base_url=self._base_url)

    async def _generate_problems(self) -> AsyncGenerator[BaseEntity, None]:
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
        async for rec in self._fetch_table_paginated("problem", fields):
            yield ServiceNowProblemEntity.from_api(rec, base_url=self._base_url)

    async def _generate_catalog_items(self) -> AsyncGenerator[BaseEntity, None]:
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
        async for rec in self._fetch_table_paginated("sc_cat_item", fields):
            yield ServiceNowCatalogItemEntity.from_api(rec, base_url=self._base_url)

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all MVP entities from the ServiceNow instance."""
        self.logger.info("Starting ServiceNow sync")
        async for entity in self._generate_incidents():
            yield entity
        async for entity in self._generate_kb_articles():
            yield entity
        async for entity in self._generate_change_requests():
            yield entity
        async for entity in self._generate_problems():
            yield entity
        async for entity in self._generate_catalog_items():
            yield entity
        self.logger.info("ServiceNow sync completed")

    async def validate(self) -> None:
        """Validate credentials by querying the instance (minimal table read)."""
        await self._get(
            self._table_url("incident"), params={"sysparm_limit": 1, "sysparm_fields": "sys_id"}
        )
