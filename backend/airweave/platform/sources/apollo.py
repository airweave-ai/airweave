"""Apollo source implementation.

Syncs Contacts, Accounts, Sequences, and Email Activities from Apollo.
API reference: https://docs.apollo.io/
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.configs.auth import ApolloAuthConfig
from airweave.platform.configs.config import ApolloConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.apollo import (
    ApolloAccountEntity,
    ApolloContactEntity,
    ApolloEmailActivityEntity,
    ApolloSequenceEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
APOLLO_APP_BASE_URL = "https://app.apollo.io"
PER_PAGE = 100


@source(
    name="Apollo",
    short_name="apollo",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=None,
    auth_config_class=ApolloAuthConfig,
    config_class=ApolloConfig,
    labels=["CRM", "Sales"],
    supports_continuous=False,
)
class ApolloSource(BaseSource):
    """Apollo source connector.

    Syncs Contacts, Accounts, Sequences, and Email Activities from your
    team's Apollo account. Requires an Apollo API key (master key for
    Sequences and Email Activities).
    """

    @classmethod
    async def create(
        cls, credentials: ApolloAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "ApolloSource":
        """Create and configure the Apollo source.

        Args:
            credentials: Apollo auth config (API key).
            config: Optional source configuration.

        Returns:
            Configured ApolloSource instance.
        """
        instance = cls()
        instance.api_key = credentials.api_key
        return instance

    def _headers(self) -> Dict[str, str]:
        """Build request headers with Apollo API key."""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def _post_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated POST request to Apollo API."""
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json=json_data or {},
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Apollo API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Apollo API: {url}, {e}")
            raise

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Apollo API."""
        try:
            response = await client.get(
                url,
                headers=self._headers(),
                params=params or {},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Apollo API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Apollo API: {url}, {e}")
            raise

    async def _paginate_post(
        self,
        client: httpx.AsyncClient,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        data_key: str = "accounts",
        use_query_params: bool = False,
        log_first_page: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a POST search endpoint. Yields items.

        If use_query_params is True (e.g. for emailer_campaigns), page/per_page
        are sent as query params instead of in the body.
        If log_first_page is set, logs response keys and item count for page 1 (diagnostics).
        """
        page = 1
        while True:
            if use_query_params:
                params = {"page": page, "per_page": PER_PAGE}
                data = await self._post_with_auth(
                    client, f"{APOLLO_BASE_URL}{path}", json_data=body or {}, params=params
                )
            else:
                payload = dict(body or {})
                payload["page"] = page
                payload["per_page"] = PER_PAGE
                data = await self._post_with_auth(client, f"{APOLLO_BASE_URL}{path}", payload)
            items = data.get(data_key, [])
            pagination = data.get("pagination", {})
            if log_first_page and page == 1:
                self.logger.info(
                    f"{log_first_page}: response keys=%s, {data_key!r} count=%d, pagination=%s",
                    list(data.keys()),
                    len(items),
                    pagination,
                )
            for item in items:
                yield item
            total_pages = pagination.get("total_pages", 1)
            if page >= total_pages or not items:
                break
            page += 1

    async def _paginate_get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data_key: str = "emailer_messages",
        log_first_page: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a GET search endpoint. Yields items."""
        page = 1
        while True:
            q = dict(params or {})
            q["page"] = page
            q["per_page"] = PER_PAGE
            data = await self._get_with_auth(client, f"{APOLLO_BASE_URL}{path}", q)
            items = data.get(data_key, [])
            pagination = data.get("pagination", {})
            if log_first_page and page == 1:
                self.logger.info(
                    f"{log_first_page}: response keys=%s, {data_key!r} count=%d, pagination=%s",
                    list(data.keys()),
                    len(items),
                    pagination,
                )
            for item in items:
                yield item
            total_pages = pagination.get("total_pages", 1)
            if page >= total_pages or not items:
                break
            page += 1

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all entities: Accounts, Contacts, Sequences, Email Activities."""
        self.logger.info("Starting Apollo sync (Accounts, Contacts, Sequences, Email Activities)")
        async with self.http_client() as client:
            # 1. Accounts (top-level)
            self.logger.info("Fetching Apollo accounts...")
            async for acc in self._generate_accounts(client):
                yield acc

            # 2. Contacts (with optional account breadcrumb)
            self.logger.info("Fetching Apollo contacts...")
            async for contact in self._generate_contacts(client):
                yield contact

            # 3. Sequences (top-level) – requires master API key
            self.logger.info(
                "Fetching Apollo sequences (requires master API key; 403 = use master key)..."
            )
            seq_count = 0
            async for seq in self._generate_sequences(client):
                seq_count += 1
                yield seq
            self.logger.info(f"Apollo sequences synced: {seq_count}")

            # 4. Email activities (with sequence/contact breadcrumbs) – requires master API key
            self.logger.info(
                "Fetching Apollo email activities (master API key; 403 = use master key)..."
            )
            activity_count = 0
            async for activity in self._generate_email_activities(client):
                activity_count += 1
                yield activity
            self.logger.info(f"Apollo email activities synced: {activity_count}")

        self.logger.info("Apollo sync completed")

    async def _generate_accounts(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ApolloAccountEntity, None]:
        """Generate account entities from POST /accounts/search."""
        async for raw in self._paginate_post(
            client, "/accounts/search", body={}, data_key="accounts"
        ):
            try:
                acc_id = raw.get("id")
                if not acc_id:
                    continue
                name = raw.get("name") or raw.get("domain") or acc_id
                created_at = raw.get("created_at")
                updated_at = raw.get("updated_at")
                # Accounts don't have updated_at in the search response; use created_at
                if not updated_at and created_at:
                    updated_at = created_at
                web_url = f"{APOLLO_APP_BASE_URL}/accounts/{acc_id}" if acc_id else None
                yield ApolloAccountEntity(
                    entity_id=acc_id,
                    breadcrumbs=[],
                    name=name,
                    account_id=acc_id,
                    domain=raw.get("domain"),
                    created_at=created_at,
                    updated_at=updated_at,
                    source=raw.get("source"),
                    source_display_name=raw.get("source_display_name"),
                    num_contacts=raw.get("num_contacts"),
                    last_activity_date=raw.get("last_activity_date"),
                    label_ids=raw.get("label_ids") or [],
                    web_url_value=web_url,
                )
            except Exception as e:
                self.logger.warning(f"Failed to build account entity: {e}")
                continue

    async def _generate_contacts(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ApolloContactEntity, None]:
        """Generate contact entities from POST /contacts/search."""
        async for raw in self._paginate_post(
            client, "/contacts/search", body={}, data_key="contacts"
        ):
            try:
                contact_id = raw.get("id")
                if not contact_id:
                    continue
                name = (
                    raw.get("name")
                    or " ".join(filter(None, [raw.get("first_name"), raw.get("last_name")]))
                    or raw.get("email")
                    or contact_id
                ).strip() or contact_id
                account_id = raw.get("account_id")
                account_name = None
                account_data = raw.get("account")
                if isinstance(account_data, dict):
                    account_name = account_data.get("name")
                breadcrumbs: List[Breadcrumb] = []
                if account_id and account_name:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name,
                            entity_type="ApolloAccountEntity",
                        )
                    )
                web_url = f"{APOLLO_APP_BASE_URL}/contacts/{contact_id}" if contact_id else None
                yield ApolloContactEntity(
                    entity_id=contact_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    contact_id=contact_id,
                    first_name=raw.get("first_name"),
                    last_name=raw.get("last_name"),
                    email=raw.get("email"),
                    title=raw.get("title"),
                    organization_name=raw.get("organization_name") or account_name,
                    account_id=account_id,
                    account_name=account_name,
                    created_at=raw.get("created_at"),
                    updated_at=raw.get("updated_at"),
                    email_status=raw.get("email_status"),
                    source_display_name=raw.get("source_display_name"),
                    emailer_campaign_ids=raw.get("emailer_campaign_ids") or [],
                    web_url_value=web_url,
                )
            except Exception as e:
                self.logger.warning(f"Failed to build contact entity: {e}")
                continue

    async def _generate_sequences(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ApolloSequenceEntity, None]:
        """Generate sequence entities from POST /emailer_campaigns/search."""
        try:
            async for raw in self._paginate_post(
                client,
                "/emailer_campaigns/search",
                body={},
                data_key="emailer_campaigns",
                use_query_params=True,
                log_first_page="Apollo sequences",
            ):
                try:
                    seq_id = raw.get("id")
                    if not seq_id:
                        continue
                    name = raw.get("name") or seq_id
                    web_url = f"{APOLLO_APP_BASE_URL}/sequences/{seq_id}" if seq_id else None
                    yield ApolloSequenceEntity(
                        entity_id=seq_id,
                        breadcrumbs=[],
                        name=name,
                        sequence_id=seq_id,
                        created_at=raw.get("created_at"),
                        active=raw.get("active"),
                        archived=raw.get("archived"),
                        num_steps=raw.get("num_steps"),
                        unique_scheduled=raw.get("unique_scheduled"),
                        unique_delivered=raw.get("unique_delivered"),
                        unique_opened=raw.get("unique_opened"),
                        unique_replied=raw.get("unique_replied"),
                        permissions=raw.get("permissions"),
                        web_url_value=web_url,
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to build sequence entity: {e}")
                    continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.logger.info(
                    "Apollo Sequences skipped (403): this endpoint requires a master API key. "
                    "In Apollo go to Settings → API, create a master key and use it for this "
                    "connection to sync sequences."
                )
                return
            raise

    async def _generate_email_activities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ApolloEmailActivityEntity, None]:
        """Generate email activity entities from GET /emailer_messages/search."""
        try:
            async for raw in self._paginate_get(
                client,
                "/emailer_messages/search",
                params={},
                data_key="emailer_messages",
                log_first_page="Apollo email activities",
            ):
                try:
                    msg_id = raw.get("id")
                    if not msg_id:
                        continue
                    subject = raw.get("subject") or "(No subject)"
                    to_name = raw.get("to_name") or raw.get("to_email") or "unknown"
                    name = f"Email: {subject} to {to_name}"
                    campaign_name = raw.get("campaign_name")
                    campaign_id = raw.get("emailer_campaign_id")
                    contact_id = raw.get("contact_id")
                    account_id = raw.get("account_id")
                    breadcrumbs: List[Breadcrumb] = []
                    if campaign_id and campaign_name:
                        breadcrumbs.append(
                            Breadcrumb(
                                entity_id=campaign_id,
                                name=campaign_name,
                                entity_type="ApolloSequenceEntity",
                            )
                        )
                    # Optional: add contact breadcrumb if we had contact name
                    # (API may not include it)
                    to_display = raw.get("to_name") or raw.get("to_email") or ""
                    if contact_id and to_display:
                        breadcrumbs.append(
                            Breadcrumb(
                                entity_id=contact_id,
                                name=to_display,
                                entity_type="ApolloContactEntity",
                            )
                        )
                    web_url = None
                    if campaign_id:
                        web_url = f"{APOLLO_APP_BASE_URL}/sequences/{campaign_id}"
                    yield ApolloEmailActivityEntity(
                        entity_id=msg_id,
                        breadcrumbs=breadcrumbs,
                        name=name,
                        message_id=msg_id,
                        subject=subject,
                        status=raw.get("status"),
                        from_email=raw.get("from_email"),
                        from_name=raw.get("from_name"),
                        to_email=raw.get("to_email"),
                        to_name=raw.get("to_name"),
                        body_text=raw.get("body_text"),
                        campaign_name=campaign_name,
                        emailer_campaign_id=campaign_id,
                        contact_id=contact_id,
                        account_id=account_id,
                        created_at=raw.get("created_at"),
                        completed_at=raw.get("completed_at"),
                        due_at=raw.get("due_at"),
                        failure_reason=raw.get("failure_reason"),
                        not_sent_reason=raw.get("not_sent_reason"),
                        web_url_value=web_url,
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to build email activity entity: {e}")
                    continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.logger.info(
                    "Apollo Email Activities skipped (403): this endpoint requires a master "
                    "API key. In Apollo go to Settings → API, create a master key and use it "
                    "for this connection to sync outreach emails."
                )
                return
            raise

    async def validate(self) -> bool:
        """Validate API key by calling a lightweight endpoint."""
        try:
            async with self.http_client() as client:
                # Search with minimal scope to verify auth
                data = await self._post_with_auth(
                    client,
                    f"{APOLLO_BASE_URL}/accounts/search",
                    {"per_page": 1, "page": 1},
                )
                return "accounts" in data
        except Exception as e:
            self.logger.error(f"Apollo validation failed: {e}")
            return False
