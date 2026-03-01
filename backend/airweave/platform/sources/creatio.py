"""Creatio CRM source implementation using OAuth 2.0 Client Credentials Grant.

Retrieves data from the Creatio OData 4 API for:
- Accounts
- Campaigns
- Contacts
- Leads
- Opportunities
- Orders

Authentication uses OAuth 2.0 client_credentials grant to exchange
client_id and client_secret for an access token via the Creatio Identity Service.
"""

from datetime import datetime
import enum
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.platform.configs.auth import CreatioAuthConfig
from airweave.platform.configs.config import CreatioConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.creatio import (
    CreatioAccountEntity,
    CreatioCampaignEntity,
    CreatioContactEntity,
    CreatioLeadEntity,
    CreatioOpportunityEntity,
    CreatioOrderEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


class CreatioEntity(enum.Enum):
    """
    Enum containing the resource endpoints and their
    appropriate BaseEntity implementation.

    This is used to map the resource endpoint response
    in generate_entities.

    The CreatioSource can be extended by adding more CreatioEntity types.
    """
    ACCOUNT = ("Account", CreatioAccountEntity)
    CAMPAIGN = ("Campaign", CreatioCampaignEntity)
    CONTACT = ("Contact", CreatioContactEntity)
    LEAD = ("Lead", CreatioLeadEntity)
    OPPORTUNITY = ("Opportunity", CreatioOpportunityEntity)
    ORDER = ("Order", CreatioOrderEntity)

    def __init__(self, odata_name: str, type: BaseEntity):
        self.odata_name = odata_name
        self.type = type


@source(
    name="Creatio",
    short_name="creatio",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=CreatioAuthConfig,
    config_class=CreatioConfig,
    labels=["CRM"],
    supports_continuous=False,
)
class CreatioSource(BaseSource):
    """Creatio CRM source connector using OData 4 API.

    Uses OAuth 2.0 client credentials grant to exchange client_id/client_secret
    for an access token, then syncs Contacts and Accounts from Creatio.
    """

    ODATA_PAGE_SIZE = 100  # OData $top per request

    def __init__(self):
        """Initialize the Creatio source."""
        super().__init__()
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.instance_url: Optional[str] = None
        self.identity_service_url: Optional[str] = None
        self.access_token: Optional[str] = None

    @classmethod
    async def create(
        cls, credentials: CreatioAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "CreatioSource":
        """Create a new Creatio source instance.

        Args:
            credentials: CreatioAuthConfig with client_id and client_secret
            config: Required configuration dict containing instance_url

        Returns:
            Configured CreatioSource instance
        """
        instance = cls()

        instance.client_id = credentials.client_id
        instance.client_secret = credentials.client_secret

        if config is None or not config.get("instance_url"):
            raise ValueError("Config with 'instance_url' is required for this source connector")

        instance.instance_url = cls._normalize_instance_url(config["instance_url"])

        if config.get("identity_service_url"):
            instance.identity_service_url = config["identity_service_url"]
        else:
            instance.identity_service_url = cls._identity_service_url_from_instance(instance_url=instance.instance_url)

        # Exchange client credentials for access token
        instance.access_token = await instance._get_access_token()

        return instance

    @staticmethod
    def _normalize_instance_url(url: str) -> str:
        """Normalize instance URL — strip protocol and trailing slash."""
        url = url.replace("https://", "").replace("http://", "")
        return url.rstrip("/").lower()

    @staticmethod
    def _identity_service_url_from_instance(*, instance_url: str) -> str:
        """
        Derive the Identity Service base URL from the instance URL.
        Creatio Identity Service lives at ``{instance}-is.creatio.com`` in the cloud case
        """
        return instance_url.replace(".creatio.com", "-is.creatio.com", 1)

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers.
        'ForceUseSession': 'true' is recommended from
        https://academy.creatio.com/docs/8.x/dev/development-on-creatio-platform/integrations-and-api/data-services/odata/basics/references/odata-odata-4
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "ForceUseSession": "true",
        }

    async def _get_access_token(self) -> str:
        """Exchange client credentials for an access token.

        POST https://{identity-service}/connect/token
        Body: grant_type=client_credentials&client_id=...&client_secret=...

        Returns:
            Access token string

        Raises:
            ValueError: If token exchange fails
        """
        url = f"https://{self.identity_service_url}/connect/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get Creatio access token: {response.status_code} - {response.text}"
                )

            data = response.json()
            return data["access_token"]

    @retry(stop=stop_after_attempt(3))
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> dict:
        """GET request with Bearer token, retrying up to 3 times.

        Args:
            client: httpx async client
            url: Full URL to GET

        Returns:
            Parsed JSON response dict

        Raises:
            ValueError: On non-200 response after retries
        """
        response = await client.get(
            url,
            headers=self._get_headers(),
            timeout=30.0,
        )

        if response.status_code == 401:
            # Token may have expired — refresh and retry
            self.access_token = await self._get_access_token()
            raise ValueError("Token expired, retrying with fresh token")

        response.raise_for_status()
        return response.json()

    async def _paginate_odata(
        self, client: httpx.AsyncClient, entity: CreatioEntity
    ) -> AsyncGenerator[dict, None]:
        """Paginate through Creatio OData results using @odata.nextLink.

        Args:
            client: httpx async client
            entity: Type of CreatioEntity, the OData entity set name (e.g. "Contact", "Account")

        Yields:
            Individual record dicts from the OData response
        """

        skip = 0

        def _build_url(skip: int) -> str:
            return (
                f"https://{self.instance_url}/0/odata/{entity.odata_name}"
                f"?$top={self.ODATA_PAGE_SIZE}&$skip={skip}"
            )
        url = _build_url(skip)

        while url:
            self.logger.debug(f"Doing URL request: {url}")
            data = await self._get_with_auth(client, url)
            records = data.get("value", [])
            for record in records:
                yield record

            # Increment skip. The server does not provide pagination through
            # @odata.nextLink
            if len(records) == self.ODATA_PAGE_SIZE:
                skip += self.ODATA_PAGE_SIZE
                url = _build_url(skip)
            else:
                # This was the last request of the batch
                url = None

    async def _generate_entity(
        self,
        *,
        client: httpx.AsyncClient,
        creatio_entity: CreatioEntity,
    ) -> AsyncGenerator[BaseEntity, None]:
        self.logger.info(f"Fetching Creatio {creatio_entity.odata_name} entities")

        count = 0
        async for record in self._paginate_odata(client, creatio_entity):
            entity = creatio_entity.type.model_validate({
                **record,
                "breadcrumbs": []
            })
            count += 1
            yield entity
        self.logger.info(f"Finished fetching Creatio {creatio_entity.odata_name} entities")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Creatio entities. You can add more through CreatioEntity

        Yields:
            Any CreatioEntity instance
        """
        async with self.http_client(timeout=30.0) as client:
            for ce in CreatioEntity:
                async for entity in self._generate_entity(client=client, creatio_entity=ce):
                    yield entity

    async def validate(self) -> bool:
        """Verify Creatio API access by fetching a single Contact.

        Returns:
            True if credentials are valid and OData API is reachable
        """
        if not self.client_id or not self.client_secret or not self.instance_url:
            self.logger.error(
                "Creatio validation failed: missing client_id, client_secret, or instance_url"
            )
            return False

        self.logger.debug("Trying validation for Creatio by fetching a single Contact")
        try:
            if not self.access_token:
                self.access_token = await self._get_access_token()

            async with self.http_client(timeout=10.0) as client:
                url = f"https://{self.instance_url}/0/odata/Contact?$top=1"
                await self._get_with_auth(client, url)
                self.logger.info("Creatio validation succeeded")
                return True
        except Exception as e:
            self.logger.error(f"Creatio validation failed: {e}")
            return False
