"""Cal.com source implementation.

Syncs bookings from Cal.com using the public API v2.

Primary entity:
    - CalBookingEntity: one entity per booking (regular, recurring, or seated)

Authentication:
    - API key (Settings → Security) provided via CalComAuthConfig.

Data model reference:
- Introduction: https://cal.com/docs/api-reference/v2/introduction
- List bookings: https://cal.com/docs/api-reference/v2/bookings/get-all-bookings
"""

from __future__ import annotations

from datetime import timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import CalComAuthConfig
from airweave.platform.configs.config import CalComConfig
from airweave.platform.cursors import CalComCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.calcom import (
    CalBookingDeletionEntity,
    CalBookingEntity,
    CalEventTypeEntity,
    CalScheduleEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

DEFAULT_CAL_API_BASE = "https://api.cal.com"
# API versions per endpoint family (see Cal.com v2 docs)
CAL_BOOKINGS_API_VERSION = "2024-08-13"
CAL_EVENT_TYPES_API_VERSION = "2024-06-14"
CAL_SCHEDULES_API_VERSION = "2024-06-11"


@source(
    name="Cal.com",
    short_name="calcom",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=CalComAuthConfig,
    config_class=CalComConfig,
    labels=["Calendar", "Scheduling"],
    supports_continuous=True,
    cursor_class=CalComCursor,
    rate_limit_level=RateLimitLevel.ORG,
)
class CalSource(BaseSource):
    """Cal.com source connector.

    Syncs bookings from the Cal.com API into searchable entities.

    The connector:
    - Uses the Bookings API with `cal-api-version=2024-08-13`
    - Paginates with `take`/`skip`
    - Supports incremental sync via `afterUpdatedAt` cursor watermark
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: CalComConfig,
    ) -> CalSource:
        """Create and configure the Cal.com source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        host = config.host.strip() or DEFAULT_CAL_API_BASE
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        instance._base_url = host.rstrip("/")
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Cal.com API."""
        url = f"{self._base_url}{path}" if path.startswith("/") else f"{self._base_url}/{path}"
        request_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        response = await self.http_client.get(url, headers=request_headers, params=params or {})
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _list_bookings(
        self,
        after_updated_at: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all bookings from Cal.com, optionally incrementally.

        Uses cursor-based incremental sync via the `afterUpdatedAt` query parameter
        and CalComCursor.last_updated_at watermark.

        Always requests all statuses (upcoming, recurring, past, cancelled, unconfirmed)
        so that full sync sees every booking. Otherwise the API may default to a subset
        (e.g. only recently updated or non-cancelled), causing remaining bookings to be
        missing from the stream and wrongly deleted as orphans during orphan cleanup.
        """
        params: Dict[str, Any] = {
            "take": 100,
            "skip": 0,
            # Request all statuses so full sync returns every booking (required for
            # correct orphan detection; omitting status can return a subset only).
            "status": "upcoming,recurring,past,cancelled,unconfirmed",
            # Sort by updated time ascending so the cursor watermark is monotonic.
            "sortUpdatedAt": "asc",
        }
        if after_updated_at:
            params["afterUpdatedAt"] = after_updated_at

        while True:
            data = await self._get(
                "/v2/bookings",
                params=params,
                headers={"cal-api-version": CAL_BOOKINGS_API_VERSION},
            )
            items = data.get("data", []) or []
            for item in items:
                yield item

            pagination = data.get("pagination") or {}
            has_next = pagination.get("hasNextPage")
            returned_items = pagination.get("returnedItems", len(items))

            if not items or not has_next or returned_items == 0:
                break

            # Advance skip by number of items returned on this page.
            params["skip"] = params.get("skip", 0) + int(returned_items)

    async def _list_event_types(
        self,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all event types from Cal.com with pagination.

        Event types describe the bookable meeting templates (duration, locations,
        booking page URL, etc.). Uses take/skip and pagination metadata when present.
        """
        params: Dict[str, Any] = {
            "take": 100,
            "skip": 0,
            "sortCreatedAt": "asc",
        }
        while True:
            data = await self._get(
                "/v2/event-types",
                params=params,
                headers={"cal-api-version": CAL_EVENT_TYPES_API_VERSION},
            )
            items = data.get("data", []) or []
            for item in items:
                yield item

            pagination = data.get("pagination") or {}
            has_next = pagination.get("hasNextPage")
            returned_items = pagination.get("returnedItems", len(items))

            if not items or not has_next or returned_items == 0:
                break

            params["skip"] = params.get("skip", 0) + int(returned_items)

    async def _list_schedules(
        self,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all schedules for the authenticated user from Cal.com.

        The v2/schedules endpoint returns all schedules in a single response;
        no pagination parameters are documented.
        """
        data = await self._get(
            "/v2/schedules",
            headers={"cal-api-version": CAL_SCHEDULES_API_VERSION},
        )
        for item in data.get("data", []) or []:
            yield item

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all booking entities from Cal.com.

        Uses incremental sync when a cursor is available; otherwise performs
        a full sync.
        """
        cursor_data = cursor.data if cursor else {}
        last_updated_at = cursor_data.get("last_updated_at")

        if last_updated_at:
            self.logger.info("Cal.com: incremental sync from updatedAt=%s", last_updated_at)
        else:
            self.logger.info("Cal.com: full sync (no existing cursor)")

        async for event_type in self._list_event_types():
            yield CalEventTypeEntity.from_api(event_type)

        async for schedule in self._list_schedules():
            yield CalScheduleEntity.from_api(schedule)

        latest_watermark: Optional[str] = last_updated_at

        async for booking in self._list_bookings(after_updated_at=last_updated_at):
            entity = CalBookingEntity.from_api(booking)

            if (entity.status or "").lower() == "cancelled":
                yield CalBookingDeletionEntity(
                    breadcrumbs=[],
                    uid=entity.uid,
                    booking_id=entity.booking_id,
                    label=f"Deleted booking {entity.uid}",
                    deletion_status="removed",
                )
            else:
                yield entity

            if cursor:
                updated_at = entity.updated_at or entity.created_at
                if updated_at:
                    iso = updated_at.astimezone(timezone.utc).isoformat()
                    if latest_watermark is None or iso > latest_watermark:
                        latest_watermark = iso
                        cursor.update(last_updated_at=latest_watermark)

    async def validate(self) -> None:
        """Validate credentials by pinging the Cal.com bookings endpoint."""
        await self._get(
            "/v2/bookings",
            params={"take": 1, "skip": 0},
            headers={"cal-api-version": CAL_BOOKINGS_API_VERSION},
        )
