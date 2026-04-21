"""Pipedrive source implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import PipedriveAuthConfig
from airweave.platform.configs.config import PipedriveConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.pipedrive import (
    PipedriveActivityEntity,
    PipedriveDealEntity,
    PipedriveLeadEntity,
    PipedriveNoteEntity,
    PipedriveOrganizationEntity,
    PipedrivePersonEntity,
    PipedriveProductEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="Pipedrive",
    short_name="pipedrive",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=PipedriveAuthConfig,
    config_class=PipedriveConfig,
    labels=["CRM", "Sales"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class PipedriveSource(BaseSource):
    """Pipedrive source connector integrates with the Pipedrive CRM API to extract CRM data.

    Synchronizes customer relationship management data including persons, organizations,
    deals, activities, products, leads, and notes.

    Uses API token authentication.
    """

    PIPEDRIVE_API_LIMIT = 100
    BASE_URL = "https://api.pipedrive.com/v1"

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: PipedriveConfig,
    ) -> PipedriveSource:
        """Create a new Pipedrive source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._company_domain: Optional[str] = None
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_token = auth.credentials.api_token
        else:
            instance._api_token = await auth.get_token()
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> Dict:
        """Make authenticated GET request to Pipedrive API using API token."""
        separator = "&" if "?" in url else "?"
        auth_url = f"{url}{separator}api_token={self._api_token}"

        response = await self.http_client.get(auth_url)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _ensure_company_domain(self) -> Optional[str]:
        """Fetch and cache the Pipedrive company domain for building record URLs."""
        if self._company_domain:
            return self._company_domain

        try:
            url = f"{self.BASE_URL}/users/me"
            data = await self._get(url)
            if data.get("success") and data.get("data"):
                company_domain = data["data"].get("company_domain")
                if company_domain:
                    self._company_domain = company_domain
                else:
                    self.logger.warning("Pipedrive response missing company_domain.")
        except SourceAuthError:
            raise
        except Exception as exc:
            self.logger.warning(f"Failed to fetch Pipedrive company domain: {exc}")

        return self._company_domain

    async def _paginate(self, endpoint: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through Pipedrive API results.

        Args:
            endpoint: API endpoint (without base URL)

        Yields:
            Individual items from the paginated response
        """
        start = 0
        while True:
            url = f"{self.BASE_URL}/{endpoint}?start={start}&limit={self.PIPEDRIVE_API_LIMIT}"
            data = await self._get(url)

            if not data.get("success"):
                self.logger.warning(f"Pipedrive API returned unsuccessful response: {data}")
                break

            items = data.get("data") or []
            for item in items:
                yield item

            additional_data = data.get("additional_data", {})
            pagination = additional_data.get("pagination", {})
            if not pagination.get("more_items_in_collection"):
                break

            start = pagination.get("next_start", start + self.PIPEDRIVE_API_LIMIT)

    async def _generate_person_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Person entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive persons...")
        count = 0
        async for person in self._paginate("persons"):
            yield PipedrivePersonEntity.from_api(person, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive persons")

    async def _generate_organization_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Organization entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive organizations...")
        count = 0
        async for org in self._paginate("organizations"):
            yield PipedriveOrganizationEntity.from_api(org, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive organizations")

    async def _generate_deal_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Deal entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive deals...")
        count = 0
        async for deal in self._paginate("deals"):
            yield PipedriveDealEntity.from_api(deal, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive deals")

    async def _generate_activity_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Activity entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive activities...")
        count = 0
        async for activity in self._paginate("activities"):
            yield PipedriveActivityEntity.from_api(activity, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive activities")

    async def _generate_product_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Product entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive products...")
        count = 0
        async for product in self._paginate("products"):
            yield PipedriveProductEntity.from_api(product, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive products")

    async def _generate_lead_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Lead entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive leads...")
        count = 0
        async for lead in self._paginate("leads"):
            yield PipedriveLeadEntity.from_api(lead, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive leads")

    async def _generate_note_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Note entities from Pipedrive."""
        self.logger.info("Fetching Pipedrive notes...")
        count = 0
        async for note in self._paginate("notes"):
            yield PipedriveNoteEntity.from_api(note, company_domain=self._company_domain)
            count += 1
        self.logger.info(f"Fetched {count} Pipedrive notes")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Pipedrive.

        Yields:
            Pipedrive entities: Persons, Organizations, Deals, Activities, Products, Leads, Notes.
        """
        await self._ensure_company_domain()

        async for person_entity in self._generate_person_entities():
            yield person_entity

        async for org_entity in self._generate_organization_entities():
            yield org_entity

        async for deal_entity in self._generate_deal_entities():
            yield deal_entity

        async for activity_entity in self._generate_activity_entities():
            yield activity_entity

        async for product_entity in self._generate_product_entities():
            yield product_entity

        async for lead_entity in self._generate_lead_entities():
            yield lead_entity

        async for note_entity in self._generate_note_entities():
            yield note_entity

    async def validate(self) -> None:
        """Verify Pipedrive API token by pinging a lightweight endpoint."""
        await self._get(f"{self.BASE_URL}/users/me")
