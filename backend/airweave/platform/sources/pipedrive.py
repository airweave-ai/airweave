"""Pipedrive source implementation."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import PipedriveAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.pipedrive import (
    PipedriveActivityEntity,
    PipedriveDealEntity,
    PipedriveLeadEntity,
    PipedriveNoteEntity,
    PipedriveOrganizationEntity,
    PipedrivePersonEntity,
    PipedriveProductEntity,
    parse_pipedrive_datetime,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Pipedrive",
    short_name="pipedrive",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=PipedriveAuthConfig,
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

    # Pipedrive API configuration
    PIPEDRIVE_API_LIMIT = 100  # Maximum results per page for list endpoints
    BASE_URL = "https://api.pipedrive.com/v1"

    def __init__(self):
        """Initialize the Pipedrive source."""
        super().__init__()
        self._company_domain: Optional[str] = None
        self._api_token: Optional[str] = None

    @classmethod
    async def create(
        cls, credentials: PipedriveAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "PipedriveSource":
        """Create a new Pipedrive source instance.

        Args:
            credentials: PipedriveAuthConfig instance containing api_token
            config: Optional source configuration parameters

        Returns:
            Configured PipedriveSource instance
        """
        instance = cls()
        instance._api_token = credentials.api_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to Pipedrive API using API token.

        Args:
            client: HTTP client
            url: API endpoint URL

        Returns:
            JSON response from API
        """
        # API token auth - add as query parameter
        # Keep original URL for logging to avoid exposing the token
        separator = "&" if "?" in url else "?"
        auth_url = f"{url}{separator}api_token={self._api_token}"

        response = await client.get(auth_url)

        # Log detailed error information for 4xx/5xx responses before raising
        if not response.is_success:
            try:
                error_body = response.json()
                error_message = error_body.get("error", "No message provided")
                error_info = error_body.get("error_info", "No info")
                self.logger.error(
                    f"Pipedrive API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Message: {error_message}, "
                    f"Info: {error_info}, "
                    f"Full response: {error_body}"
                )
            except Exception:
                # If we can't parse JSON, log the raw response
                self.logger.error(
                    f"Pipedrive API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )

        response.raise_for_status()
        return response.json()

    def _clean_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove null, empty string, and internal fields from properties.

        Args:
            data: Raw data dictionary from Pipedrive

        Returns:
            Cleaned properties dictionary with only meaningful values
        """
        cleaned = {}
        skip_keys = {"id", "company_id", "creator_user_id", "owner_id", "user_id"}

        for key, value in data.items():
            # Skip internal/redundant fields
            if key in skip_keys:
                continue
            # Skip null and empty values
            if value is None or value == "":
                continue
            # Skip objects that are just references (have id but no useful content)
            if isinstance(value, dict) and set(value.keys()) <= {"id", "name", "value"}:
                continue
            cleaned[key] = value

        return cleaned

    async def _ensure_company_domain(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch and cache the Pipedrive company domain for building record URLs."""
        if self._company_domain:
            return self._company_domain

        try:
            url = f"{self.BASE_URL}/users/me"
            data = await self._get_with_auth(client, url)
            if data.get("success") and data.get("data"):
                company_domain = data["data"].get("company_domain")
                if company_domain:
                    self._company_domain = company_domain
                else:
                    self.logger.warning("Pipedrive response missing company_domain.")
        except Exception as exc:
            self.logger.warning(f"Failed to fetch Pipedrive company domain: {exc}")

        return self._company_domain

    def _build_record_url(self, record_type: str, record_id: str) -> Optional[str]:
        """Build a Pipedrive UI URL for the given record.

        Args:
            record_type: Type of record (person, organization, deal, activity, product, lead)
            record_id: ID of the record

        Returns:
            URL to view the record in Pipedrive UI, or None if domain not available
        """
        if not self._company_domain:
            return None

        base = f"https://{self._company_domain}.pipedrive.com"

        # Different record types have different URL patterns in Pipedrive UI
        url_patterns = {
            "person": f"{base}/person/{record_id}",
            "organization": f"{base}/organization/{record_id}",
            "deal": f"{base}/deal/{record_id}",
            "activity": f"{base}/activities/list/user/everyone/filter/all/activity/{record_id}",
            "product": f"{base}/settings/products",  # Products don't have direct URLs
            "lead": f"{base}/leads/inbox/{record_id}",
        }

        return url_patterns.get(record_type, f"{base}/{record_type}/{record_id}")

    async def _paginate(
        self, client: httpx.AsyncClient, endpoint: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through Pipedrive API results.

        Args:
            client: HTTP client
            endpoint: API endpoint (without base URL)

        Yields:
            Individual items from the paginated response
        """
        start = 0
        while True:
            url = f"{self.BASE_URL}/{endpoint}?start={start}&limit={self.PIPEDRIVE_API_LIMIT}"
            data = await self._get_with_auth(client, url)

            if not data.get("success"):
                self.logger.error(f"Pipedrive API returned unsuccessful response: {data}")
                break

            items = data.get("data") or []
            for item in items:
                yield item

            # Check if there are more pages
            additional_data = data.get("additional_data", {})
            pagination = additional_data.get("pagination", {})
            if not pagination.get("more_items_in_collection"):
                break

            start = pagination.get("next_start", start + self.PIPEDRIVE_API_LIMIT)

    async def _generate_person_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Person entities from Pipedrive.

        Yields:
            PipedrivePersonEntity objects
        """
        self.logger.info("Fetching Pipedrive persons...")
        count = 0

        async for person in self._paginate(client, "persons"):
            person_id = str(person.get("id"))

            # Extract name
            name = person.get("name") or f"Person {person_id}"
            first_name = person.get("first_name")
            last_name = person.get("last_name")

            # Extract primary email
            emails = person.get("email") or []
            primary_email = None
            if isinstance(emails, list) and emails:
                primary_email = emails[0].get("value") if isinstance(emails[0], dict) else emails[0]
            elif isinstance(emails, str):
                primary_email = emails

            # Extract primary phone
            phones = person.get("phone") or []
            primary_phone = None
            if isinstance(phones, list) and phones:
                primary_phone = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]
            elif isinstance(phones, str):
                primary_phone = phones

            # Extract organization info
            org_id = person.get("org_id")
            org_name = None
            if isinstance(org_id, dict):
                org_name = org_id.get("name")
                org_id = org_id.get("value")

            created_time = parse_pipedrive_datetime(person.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(person.get("update_time")) or created_time

            # Build breadcrumbs - include organization if linked
            breadcrumbs = []
            if org_id and org_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(org_id),
                        name=org_name,
                        entity_type="PipedriveOrganizationEntity",
                    )
                )

            yield PipedrivePersonEntity(
                entity_id=f"person_{person_id}",
                breadcrumbs=breadcrumbs,
                name=name,
                created_at=created_time,
                updated_at=updated_time,
                person_id=person_id,
                display_name=name,
                created_time=created_time,
                updated_time=updated_time,
                first_name=first_name,
                last_name=last_name,
                email=primary_email,
                phone=primary_phone,
                organization_id=org_id,
                organization_name=org_name,
                owner_id=person.get("owner_id", {}).get("id")
                if isinstance(person.get("owner_id"), dict)
                else person.get("owner_id"),
                properties=self._clean_properties(person),
                active_flag=person.get("active_flag", True),
                web_url_value=self._build_record_url("person", person_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive persons")

    async def _generate_organization_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Organization entities from Pipedrive.

        Yields:
            PipedriveOrganizationEntity objects
        """
        self.logger.info("Fetching Pipedrive organizations...")
        count = 0

        async for org in self._paginate(client, "organizations"):
            org_id = str(org.get("id"))
            name = org.get("name") or f"Organization {org_id}"

            created_time = parse_pipedrive_datetime(org.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(org.get("update_time")) or created_time

            yield PipedriveOrganizationEntity(
                entity_id=f"organization_{org_id}",
                breadcrumbs=[],
                name=name,
                created_at=created_time,
                updated_at=updated_time,
                organization_id=org_id,
                organization_name=name,
                created_time=created_time,
                updated_time=updated_time,
                address=org.get("address"),
                owner_id=org.get("owner_id", {}).get("id")
                if isinstance(org.get("owner_id"), dict)
                else org.get("owner_id"),
                people_count=org.get("people_count"),
                properties=self._clean_properties(org),
                active_flag=org.get("active_flag", True),
                web_url_value=self._build_record_url("organization", org_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive organizations")

    async def _generate_deal_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Deal entities from Pipedrive.

        Yields:
            PipedriveDealEntity objects
        """
        self.logger.info("Fetching Pipedrive deals...")
        count = 0

        async for deal in self._paginate(client, "deals"):
            deal_id = str(deal.get("id"))
            title = deal.get("title") or f"Deal {deal_id}"

            # Extract person info
            person_id = deal.get("person_id")
            person_name = None
            if isinstance(person_id, dict):
                person_name = person_id.get("name")
                person_id = person_id.get("value")

            # Extract organization info
            org_id = deal.get("org_id")
            org_name = None
            if isinstance(org_id, dict):
                org_name = org_id.get("name")
                org_id = org_id.get("value")

            # Extract stage info
            stage_id = deal.get("stage_id")
            stage_name = None
            # Note: Stage name might need additional API call, but we capture ID

            # Extract pipeline info
            pipeline_id = deal.get("pipeline_id")
            pipeline_name = None
            # Note: Pipeline name might need additional API call

            created_time = parse_pipedrive_datetime(deal.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(deal.get("update_time")) or created_time
            expected_close = parse_pipedrive_datetime(deal.get("expected_close_date"))

            # Build breadcrumbs - include organization and/or person if linked
            breadcrumbs = []
            if org_id and org_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(org_id),
                        name=org_name,
                        entity_type="PipedriveOrganizationEntity",
                    )
                )
            if person_id and person_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(person_id),
                        name=person_name,
                        entity_type="PipedrivePersonEntity",
                    )
                )

            yield PipedriveDealEntity(
                entity_id=f"deal_{deal_id}",
                breadcrumbs=breadcrumbs,
                name=title,
                created_at=created_time,
                updated_at=updated_time,
                deal_id=deal_id,
                deal_title=title,
                created_time=created_time,
                updated_time=updated_time,
                value=deal.get("value"),
                currency=deal.get("currency"),
                status=deal.get("status"),
                stage_id=stage_id,
                stage_name=stage_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                person_id=person_id,
                person_name=person_name,
                organization_id=org_id,
                organization_name=org_name,
                owner_id=deal.get("user_id", {}).get("id")
                if isinstance(deal.get("user_id"), dict)
                else deal.get("user_id"),
                expected_close_date=expected_close,
                probability=deal.get("probability"),
                properties=self._clean_properties(deal),
                active_flag=deal.get("active", True),
                web_url_value=self._build_record_url("deal", deal_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive deals")

    async def _generate_activity_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Activity entities from Pipedrive.

        Yields:
            PipedriveActivityEntity objects
        """
        self.logger.info("Fetching Pipedrive activities...")
        count = 0

        async for activity in self._paginate(client, "activities"):
            activity_id = str(activity.get("id"))
            subject = activity.get("subject") or f"Activity {activity_id}"

            # Extract deal info
            deal_id = activity.get("deal_id")
            deal_title = activity.get("deal_title")

            # Extract person info
            person_id = activity.get("person_id")
            person_name = activity.get("person_name")

            # Extract organization info
            org_id = activity.get("org_id")
            org_name = activity.get("org_name")

            created_time = parse_pipedrive_datetime(activity.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(activity.get("update_time")) or created_time
            due_date = parse_pipedrive_datetime(activity.get("due_date"))

            # Build breadcrumbs - include org, person, and/or deal if linked
            breadcrumbs = []
            if org_id and org_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(org_id),
                        name=org_name,
                        entity_type="PipedriveOrganizationEntity",
                    )
                )
            if person_id and person_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(person_id),
                        name=person_name,
                        entity_type="PipedrivePersonEntity",
                    )
                )
            if deal_id and deal_title:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(deal_id),
                        name=deal_title,
                        entity_type="PipedriveDealEntity",
                    )
                )

            yield PipedriveActivityEntity(
                entity_id=f"activity_{activity_id}",
                breadcrumbs=breadcrumbs,
                name=subject,
                created_at=created_time,
                updated_at=updated_time,
                activity_id=activity_id,
                activity_subject=subject,
                created_time=created_time,
                updated_time=updated_time,
                activity_type=activity.get("type"),
                due_date=due_date,
                due_time=activity.get("due_time"),
                duration=activity.get("duration"),
                done=activity.get("done", False),
                note=activity.get("note"),
                deal_id=deal_id,
                deal_title=deal_title,
                person_id=person_id,
                person_name=person_name,
                organization_id=org_id,
                organization_name=org_name,
                owner_id=activity.get("user_id"),
                properties=self._clean_properties(activity),
                active_flag=activity.get("active_flag", True),
                web_url_value=self._build_record_url("activity", activity_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive activities")

    async def _generate_product_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Product entities from Pipedrive.

        Yields:
            PipedriveProductEntity objects
        """
        self.logger.info("Fetching Pipedrive products...")
        count = 0

        async for product in self._paginate(client, "products"):
            product_id = str(product.get("id"))
            name = product.get("name") or f"Product {product_id}"

            created_time = parse_pipedrive_datetime(product.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(product.get("update_time")) or created_time

            # Extract prices
            prices = {}
            if product.get("prices"):
                for price in product.get("prices", []):
                    if isinstance(price, dict):
                        currency = price.get("currency")
                        if currency:
                            prices[currency] = {
                                "price": price.get("price"),
                                "cost": price.get("cost"),
                                "overhead_cost": price.get("overhead_cost"),
                            }

            yield PipedriveProductEntity(
                entity_id=f"product_{product_id}",
                breadcrumbs=[],
                name=name,
                created_at=created_time,
                updated_at=updated_time,
                product_id=product_id,
                product_name=name,
                created_time=created_time,
                updated_time=updated_time,
                code=product.get("code"),
                description=product.get("description"),
                unit=product.get("unit"),
                tax=product.get("tax"),
                category=product.get("category"),
                owner_id=product.get("owner_id", {}).get("id")
                if isinstance(product.get("owner_id"), dict)
                else product.get("owner_id"),
                prices=prices,
                properties=self._clean_properties(product),
                active_flag=product.get("active_flag", True),
                web_url_value=self._build_record_url("product", product_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive products")

    async def _generate_lead_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Lead entities from Pipedrive.

        Yields:
            PipedriveLeadEntity objects
        """
        self.logger.info("Fetching Pipedrive leads...")
        count = 0

        async for lead in self._paginate(client, "leads"):
            lead_id = str(lead.get("id"))
            title = lead.get("title") or f"Lead {lead_id}"

            # Extract person info
            person_id = lead.get("person_id")
            person_name = None
            if isinstance(person_id, dict):
                person_name = person_id.get("name")
                person_id = person_id.get("value")

            # Extract organization info
            org_id = lead.get("organization_id")
            org_name = None
            if isinstance(org_id, dict):
                org_name = org_id.get("name")
                org_id = org_id.get("value")

            # Extract value info
            value_obj = lead.get("value") or {}
            value = value_obj.get("amount") if isinstance(value_obj, dict) else None
            currency = value_obj.get("currency") if isinstance(value_obj, dict) else None

            created_time = parse_pipedrive_datetime(lead.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(lead.get("update_time")) or created_time
            expected_close = parse_pipedrive_datetime(lead.get("expected_close_date"))

            # Build breadcrumbs - include organization and/or person if linked
            breadcrumbs = []
            if org_id and org_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(org_id),
                        name=org_name,
                        entity_type="PipedriveOrganizationEntity",
                    )
                )
            if person_id and person_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(person_id),
                        name=person_name,
                        entity_type="PipedrivePersonEntity",
                    )
                )

            yield PipedriveLeadEntity(
                entity_id=f"lead_{lead_id}",
                breadcrumbs=breadcrumbs,
                name=title,
                created_at=created_time,
                updated_at=updated_time,
                lead_id=lead_id,
                lead_title=title,
                created_time=created_time,
                updated_time=updated_time,
                value=value,
                currency=currency,
                expected_close_date=expected_close,
                person_id=person_id,
                person_name=person_name,
                organization_id=org_id,
                organization_name=org_name,
                owner_id=lead.get("owner_id"),
                source_name=lead.get("source_name"),
                label_ids=lead.get("label_ids"),
                properties=self._clean_properties(lead),
                is_archived=lead.get("is_archived", False),
                web_url_value=self._build_record_url("lead", lead_id),
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive leads")

    async def _generate_note_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Note entities from Pipedrive.

        Yields:
            PipedriveNoteEntity objects
        """
        self.logger.info("Fetching Pipedrive notes...")
        count = 0

        async for note in self._paginate(client, "notes"):
            note_id = str(note.get("id"))
            content = note.get("content") or ""

            # Create a title from content (first 50 chars)
            title = content[:50].strip() if content else f"Note {note_id}"
            if len(content) > 50:
                title += "..."

            # Extract deal info
            deal_id = note.get("deal_id")
            deal_title = None
            if isinstance(note.get("deal"), dict):
                deal_title = note.get("deal").get("title")

            # Extract person info
            person_id = note.get("person_id")
            person_name = (
                note.get("person", {}).get("name") if isinstance(note.get("person"), dict) else None
            )

            # Extract organization info
            org_id = note.get("org_id")
            org_name = (
                note.get("organization", {}).get("name")
                if isinstance(note.get("organization"), dict)
                else None
            )

            created_time = parse_pipedrive_datetime(note.get("add_time")) or datetime.utcnow()
            updated_time = parse_pipedrive_datetime(note.get("update_time")) or created_time

            # Build breadcrumbs - include org, person, and/or deal if linked
            breadcrumbs = []
            if org_id and org_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(org_id),
                        name=org_name,
                        entity_type="PipedriveOrganizationEntity",
                    )
                )
            if person_id and person_name:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(person_id),
                        name=person_name,
                        entity_type="PipedrivePersonEntity",
                    )
                )
            if deal_id and deal_title:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=str(deal_id),
                        name=deal_title,
                        entity_type="PipedriveDealEntity",
                    )
                )

            yield PipedriveNoteEntity(
                entity_id=f"note_{note_id}",
                breadcrumbs=breadcrumbs,
                name=title,
                created_at=created_time,
                updated_at=updated_time,
                note_id=note_id,
                note_title=title,
                created_time=created_time,
                updated_time=updated_time,
                content=content,
                deal_id=deal_id,
                deal_title=deal_title,
                person_id=person_id,
                person_name=person_name,
                organization_id=org_id,
                organization_name=org_name,
                lead_id=note.get("lead_id"),
                user_id=note.get("user_id"),
                pinned_to_deal_flag=note.get("pinned_to_deal_flag", False),
                pinned_to_person_flag=note.get("pinned_to_person_flag", False),
                pinned_to_organization_flag=note.get("pinned_to_organization_flag", False),
                properties=self._clean_properties(note),
                active_flag=note.get("active_flag", True),
                web_url_value=None,  # Notes don't have direct URLs
            )
            count += 1

        self.logger.info(f"Fetched {count} Pipedrive notes")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Pipedrive.

        Yields:
            Pipedrive entities: Persons, Organizations, Deals, Activities, Products, Leads, Notes.
        """
        async with self.http_client() as client:
            # Fetch company domain for building URLs
            await self._ensure_company_domain(client)

            # Yield person entities
            async for person_entity in self._generate_person_entities(client):
                yield person_entity

            # Yield organization entities
            async for org_entity in self._generate_organization_entities(client):
                yield org_entity

            # Yield deal entities
            async for deal_entity in self._generate_deal_entities(client):
                yield deal_entity

            # Yield activity entities
            async for activity_entity in self._generate_activity_entities(client):
                yield activity_entity

            # Yield product entities
            async for product_entity in self._generate_product_entities(client):
                yield product_entity

            # Yield lead entities
            async for lead_entity in self._generate_lead_entities(client):
                yield lead_entity

            # Yield note entities
            async for note_entity in self._generate_note_entities(client):
                yield note_entity

    async def validate(self) -> bool:
        """Verify Pipedrive API token by pinging a lightweight endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.BASE_URL}/users/me?api_token={self._api_token}"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("success", False)
                return False
        except Exception as e:
            self.logger.error(f"Pipedrive API token validation failed: {e}")
            return False
