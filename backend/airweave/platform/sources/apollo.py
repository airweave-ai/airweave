"""Apollo source implementation.

Syncs Contacts, Accounts, Sequences, and Email Activities from Apollo.
API reference: https://docs.apollo.io/
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceEntityForbiddenError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import ApolloAuthConfig
from airweave.platform.configs.config import ApolloConfig
from airweave.platform.decorators import source
from airweave.platform.entities.apollo import (
    ApolloAccountEntity,
    ApolloContactEntity,
    ApolloEmailActivityEntity,
    ApolloSequenceEntity,
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

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
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
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ApolloConfig,
    ) -> ApolloSource:
        """Create a new Apollo source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        return instance

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        """Build request headers with Apollo API key."""
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Authenticated POST request to Apollo API with retry on 429/5xx/timeout."""
        response = await self.http_client.post(
            url, headers=self._headers(), json=json_data or {}, params=params, timeout=30.0
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

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
        """Authenticated GET request to Apollo API with retry on 429/5xx/timeout."""
        response = await self.http_client.get(
            url, headers=self._headers(), params=params or {}, timeout=30.0
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def _paginate_post(
        self,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        data_key: str = "accounts",
        use_query_params: bool = False,
        log_first_page: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a POST search endpoint. Yields items.

        If use_query_params is True (e.g. for emailer_campaigns), page/per_page
        are sent as query params instead of in the body.
        """
        page = 1
        while True:
            if use_query_params:
                params = {"page": page, "per_page": PER_PAGE}
                data = await self._post(
                    f"{APOLLO_BASE_URL}{path}", json_data=body or {}, params=params
                )
            else:
                payload = dict(body or {})
                payload["page"] = page
                payload["per_page"] = PER_PAGE
                data = await self._post(f"{APOLLO_BASE_URL}{path}", payload)
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
            data = await self._get(f"{APOLLO_BASE_URL}{path}", q)
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

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_accounts(self) -> AsyncGenerator[ApolloAccountEntity, None]:
        """Generate account entities from POST /accounts/search."""
        async for raw in self._paginate_post("/accounts/search", body={}, data_key="accounts"):
            if not raw.get("id"):
                continue
            try:
                yield ApolloAccountEntity.from_api(raw)
            except Exception as e:
                self.logger.warning(f"Failed to build account entity: {e}")

    async def _generate_contacts(self) -> AsyncGenerator[ApolloContactEntity, None]:
        """Generate contact entities from POST /contacts/search."""
        async for raw in self._paginate_post("/contacts/search", body={}, data_key="contacts"):
            if not raw.get("id"):
                continue
            try:
                yield ApolloContactEntity.from_api(raw)
            except Exception as e:
                self.logger.warning(f"Failed to build contact entity: {e}")

    async def _generate_sequences(self) -> AsyncGenerator[ApolloSequenceEntity, None]:
        """Generate sequence entities from POST /emailer_campaigns/search."""
        try:
            async for raw in self._paginate_post(
                "/emailer_campaigns/search",
                body={},
                data_key="emailer_campaigns",
                use_query_params=True,
                log_first_page="Apollo sequences",
            ):
                if not raw.get("id"):
                    continue
                try:
                    yield ApolloSequenceEntity.from_api(raw)
                except Exception as e:
                    self.logger.warning(f"Failed to build sequence entity: {e}")
        except SourceEntityForbiddenError:
            self.logger.info(
                "Apollo Sequences skipped (403): this endpoint requires a master API key. "
                "In Apollo go to Settings → API, create a master key and use it for this "
                "connection to sync sequences."
            )

    async def _generate_email_activities(
        self,
    ) -> AsyncGenerator[ApolloEmailActivityEntity, None]:
        """Generate email activity entities from GET /emailer_messages/search."""
        try:
            async for raw in self._paginate_get(
                "/emailer_messages/search",
                params={},
                data_key="emailer_messages",
                log_first_page="Apollo email activities",
            ):
                if not raw.get("id"):
                    continue
                try:
                    yield ApolloEmailActivityEntity.from_api(raw)
                except Exception as e:
                    self.logger.warning(f"Failed to build email activity entity: {e}")
        except SourceEntityForbiddenError:
            self.logger.info(
                "Apollo Email Activities skipped (403): this endpoint requires a master "
                "API key. In Apollo go to Settings → API, create a master key and use it "
                "for this connection to sync outreach emails."
            )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Generate all entities: Accounts, Contacts, Sequences, Email Activities."""
        self.logger.info("Starting Apollo sync (Accounts, Contacts, Sequences, Email Activities)")

        self.logger.info("Fetching Apollo accounts...")
        async for acc in self._generate_accounts():
            yield acc

        self.logger.info("Fetching Apollo contacts...")
        async for contact in self._generate_contacts():
            yield contact

        self.logger.info(
            "Fetching Apollo sequences (requires master API key; 403 = use master key)..."
        )
        seq_count = 0
        async for seq in self._generate_sequences():
            seq_count += 1
            yield seq
        self.logger.info(f"Apollo sequences synced: {seq_count}")

        self.logger.info(
            "Fetching Apollo email activities (master API key; 403 = use master key)..."
        )
        activity_count = 0
        async for activity in self._generate_email_activities():
            activity_count += 1
            yield activity
        self.logger.info(f"Apollo email activities synced: {activity_count}")

        self.logger.info("Apollo sync completed")

    async def validate(self) -> None:
        """Validate API key by calling a lightweight endpoint."""
        await self._post(
            f"{APOLLO_BASE_URL}/accounts/search",
            {"per_page": 1, "page": 1},
        )
