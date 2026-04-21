"""Attio source implementation.

Attio is a flexible CRM platform. We extract:
- Objects (Companies, People, Deals, etc.)
- Lists (Custom collections)
- Records (Individual entries in objects/lists)
- Notes (Attached to records)

Note: Comments are not supported as the Attio API does not expose them via REST API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceEntityNotFoundError,
    SourceError,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import AttioAuthConfig
from airweave.platform.configs.config import AttioConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.attio import (
    AttioListEntity,
    AttioNoteEntity,
    AttioObjectEntity,
    AttioRecordEntity,
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

_API = "https://api.attio.com/v2"


@source(
    name="Attio",
    short_name="attio",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=AttioAuthConfig,
    config_class=AttioConfig,
    labels=["CRM"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AttioSource(BaseSource):
    """Attio source connector — syncs objects, lists, records, and notes."""

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: AttioConfig,
    ) -> AttioSource:
        """Create a new Attio source instance."""
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
        """Build request headers with Attio bearer token."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Authenticated GET with retry on 429/5xx/timeout."""
        response = await self.http_client.get(
            url, headers=self._headers(), params=params, timeout=20.0
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
    async def _post(self, url: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Authenticated POST with retry on 429/5xx/timeout."""
        response = await self.http_client.post(
            url, headers=self._headers(), json=json_data or {}, timeout=20.0
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

    async def _paginate_get(
        self, url: str, data_key: str = "data", limit: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a GET endpoint using offset/limit. Yields items."""
        offset = 0
        while True:
            params = {"offset": offset, "limit": limit}
            data = await self._get(url, params)
            items = data.get(data_key, [])
            for item in items:
                yield item
            if len(items) < limit:
                break
            offset += limit

    async def _paginate_post(
        self, url: str, data_key: str = "data", limit: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a POST query endpoint using offset/limit. Yields items."""
        offset = 0
        while True:
            body = {"offset": offset, "limit": limit}
            data = await self._post(url, body)
            items = data.get(data_key, [])
            for item in items:
                yield item
            if len(items) < limit:
                break
            offset += limit

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_objects(self) -> AsyncGenerator[AttioObjectEntity, None]:
        """Generate Attio Object entities (Companies, People, Deals, etc.)."""
        self.logger.info("Fetching Attio objects...")
        async for obj in self._paginate_get(f"{_API}/objects"):
            object_id = obj.get("id", {}).get("object_id")
            if not object_id:
                continue

            singular_noun = obj.get("singular_noun", "")
            display_name = singular_noun or object_id

            yield AttioObjectEntity(
                object_id=object_id,
                breadcrumbs=[],
                name=display_name,
                created_at=obj.get("created_at"),
                singular_noun=display_name,
                plural_noun=obj.get("plural_noun", display_name + "s"),
                api_slug=obj.get("api_slug", object_id),
                icon=obj.get("icon"),
            )

    async def _generate_lists(self) -> AsyncGenerator[AttioListEntity, None]:
        """Generate Attio List entities."""
        self.logger.info("Fetching Attio lists...")
        async for lst in self._paginate_get(f"{_API}/lists"):
            list_id = lst.get("id", {}).get("list_id")
            if not list_id:
                continue

            parent_object = lst.get("parent_object")
            if isinstance(parent_object, list):
                parent_object = ", ".join(parent_object) if parent_object else None

            yield AttioListEntity(
                list_id=list_id,
                breadcrumbs=[],
                name=lst.get("name", list_id),
                created_at=lst.get("created_at"),
                workspace_id=lst.get("workspace_id", ""),
                parent_object=parent_object,
            )

    async def _generate_records_for_object(
        self,
        object_slug: str,
        object_name: str,
        object_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[AttioRecordEntity, None]:
        """Generate record entities for a specific object."""
        self.logger.debug(f"Fetching records for object: {object_slug}")
        url = f"{_API}/objects/{object_slug}/records/query"

        try:
            async for record in self._paginate_post(url):
                entity = self._build_object_record(
                    record, object_slug, object_name, object_breadcrumb
                )
                if entity:
                    yield entity
        except SourceEntityNotFoundError:
            self.logger.warning(f"Object {object_slug} not found or not accessible, skipping")

    async def _generate_records_for_list(
        self,
        list_id: str,
        list_name: str,
        list_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[AttioRecordEntity, None]:
        """Generate record entities for a specific list."""
        self.logger.debug(f"Fetching records for list: {list_id}")
        url = f"{_API}/lists/{list_id}/records/query"

        try:
            async for record in self._paginate_post(url):
                entity = self._build_list_record(record, list_id, list_name, list_breadcrumb)
                if entity:
                    yield entity
        except SourceEntityNotFoundError:
            self.logger.debug(f"List {list_id} not found or not accessible, skipping")

    async def _generate_notes_for_record(
        self,
        parent_object_or_list_id: str,
        record_id: str,
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[AttioNoteEntity, None]:
        """Generate note entities for a specific record."""
        url = f"{_API}/notes"
        params = {
            "parent_object": parent_object_or_list_id,
            "parent_record_id": record_id,
            "limit": 50,
        }

        try:
            data = await self._get(url, params=params)
        except SourceEntityNotFoundError:
            return
        except SourceError as exc:
            self.logger.warning(f"Error fetching notes for record {record_id}: {exc}")
            return

        for note in data.get("data", []):
            note_id = note.get("id", {}).get("note_id")
            if not note_id:
                continue

            title = note.get("title")
            content = note.get("content", "")
            if title:
                note_name = title
            else:
                note_name = content[:50] + "..." if len(content) > 50 else content
                if not note_name:
                    note_name = f"Note {note_id}"

            yield AttioNoteEntity(
                note_id=note_id,
                breadcrumbs=record_breadcrumbs,
                name=note_name,
                created_at=note.get("created_at"),
                updated_at=note.get("updated_at"),
                parent_record_id=record_id,
                parent_object=parent_object_or_list_id,
                title=title,
                content=content,
                format=note.get("format"),
                author=note.get("author"),
                permalink_url=None,
            )

    # ------------------------------------------------------------------
    # Record builders (extract attribute parsing from generator loops)
    # ------------------------------------------------------------------

    def _build_object_record(  # noqa: C901
        self,
        record: Dict[str, Any],
        object_slug: str,
        object_name: str,
        breadcrumb: Breadcrumb,
    ) -> Optional[AttioRecordEntity]:
        """Build a record entity from raw API data for an object."""
        record_id = record.get("id", {}).get("record_id")
        if not record_id or record.get("deleted_at"):
            return None

        values = record.get("values", {})
        name = None
        description = None
        email_addresses: List[Dict[str, Any]] = []
        phone_numbers: List[Dict[str, Any]] = []
        domains: List[str] = []
        categories: List[str] = []
        attributes: Dict[str, Any] = {}

        for attr_key, attr_values in values.items():
            if not attr_values:
                continue

            first_val = attr_values[0] if isinstance(attr_values, list) else attr_values
            key_lower = attr_key.lower()

            if "name" in key_lower or "title" in key_lower:
                name = (
                    (first_val.get("value") or first_val.get("text"))
                    if isinstance(first_val, dict)
                    else str(first_val)
                )
            elif "description" in key_lower or "notes" in key_lower:
                description = (
                    (first_val.get("value") or first_val.get("text"))
                    if isinstance(first_val, dict)
                    else str(first_val)
                )
            elif "email" in key_lower:
                email_addresses = [v for v in attr_values if isinstance(v, dict)]
            elif "phone" in key_lower:
                phone_numbers = [v for v in attr_values if isinstance(v, dict)]
            elif "domain" in key_lower:
                domains = [
                    v.get("domain") if isinstance(v, dict) else v
                    for v in attr_values
                    if v is not None
                    and (isinstance(v, dict) and v.get("domain") or isinstance(v, str))
                ]
            elif "category" in key_lower or "tag" in key_lower:
                categories = [
                    v.get("value") if isinstance(v, dict) else v
                    for v in attr_values
                    if v is not None
                    and (isinstance(v, dict) and v.get("value") or isinstance(v, str))
                ]
            attributes[attr_key] = attr_values

        return AttioRecordEntity(
            record_id=record_id,
            breadcrumbs=[breadcrumb],
            name=name or record_id,
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            object_id=object_slug,
            list_id=None,
            parent_object_name=object_name,
            description=description,
            email_addresses=email_addresses,
            phone_numbers=phone_numbers,
            domains=domains,
            categories=categories,
            attributes=attributes,
            permalink_url=None,
        )

    def _build_list_record(  # noqa: C901
        self,
        record: Dict[str, Any],
        list_id: str,
        list_name: str,
        breadcrumb: Breadcrumb,
    ) -> Optional[AttioRecordEntity]:
        """Build a record entity from raw API data for a list."""
        record_id = record.get("id", {}).get("record_id")
        if not record_id or record.get("deleted_at"):
            return None

        values = record.get("values", {})
        name = None
        description = None
        attributes: Dict[str, Any] = {}

        for attr_key, attr_values in values.items():
            if not attr_values:
                continue

            first_val = attr_values[0] if isinstance(attr_values, list) else attr_values
            key_lower = attr_key.lower()

            if "name" in key_lower or "title" in key_lower:
                name = (
                    (first_val.get("value") or first_val.get("text"))
                    if isinstance(first_val, dict)
                    else str(first_val)
                )
            elif "description" in key_lower:
                description = (
                    (first_val.get("value") or first_val.get("text"))
                    if isinstance(first_val, dict)
                    else str(first_val)
                )
            attributes[attr_key] = attr_values

        return AttioRecordEntity(
            record_id=record_id,
            breadcrumbs=[breadcrumb],
            name=name or record_id,
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            object_id=None,
            list_id=list_id,
            parent_object_name=list_name,
            description=description,
            email_addresses=[],
            phone_numbers=[],
            domains=[],
            categories=[],
            attributes=attributes,
            permalink_url=None,
        )

    # ------------------------------------------------------------------
    # Orchestration helpers
    # ------------------------------------------------------------------

    async def _yield_record_with_notes(
        self,
        record: AttioRecordEntity,
        parent_slug_or_id: str,
        parent_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield a record entity followed by its notes."""
        yield record

        record_breadcrumbs = [
            parent_breadcrumb,
            Breadcrumb(
                entity_id=record.record_id,
                name=record.name,
                entity_type="AttioRecordEntity",
            ),
        ]

        try:
            async for note in self._generate_notes_for_record(
                parent_slug_or_id, record.record_id, record_breadcrumbs
            ):
                yield note
        except Exception as e:
            self.logger.warning(
                f"Error fetching notes for record {record.record_id}: {e}",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Attio."""
        self.logger.info("Starting Attio sync...")

        object_map: Dict[str, AttioObjectEntity] = {}
        async for obj in self._generate_objects():
            yield obj
            object_map[obj.object_id] = obj

        list_map: Dict[str, AttioListEntity] = {}
        async for lst in self._generate_lists():
            yield lst
            list_map[lst.list_id] = lst

        for object_id, obj in object_map.items():
            object_breadcrumb = Breadcrumb(
                entity_id=object_id, name=obj.name, entity_type="AttioObjectEntity"
            )

            records: List[AttioRecordEntity] = []
            async for record in self._generate_records_for_object(
                obj.api_slug, obj.singular_noun, object_breadcrumb
            ):
                records.append(record)

            async def _object_record_worker(record, _obj=obj, _bc=object_breadcrumb):
                async for entity in self._yield_record_with_notes(record, _obj.api_slug, _bc):
                    yield entity

            async for entity in self.process_entities_concurrent(
                items=records,
                worker=_object_record_worker,
                batch_size=10,
                preserve_order=False,
                stop_on_error=False,
            ):
                yield entity

        for list_id, lst in list_map.items():
            list_breadcrumb = Breadcrumb(
                entity_id=list_id, name=lst.name, entity_type="AttioListEntity"
            )

            records = []
            async for record in self._generate_records_for_list(list_id, lst.name, list_breadcrumb):
                records.append(record)

            async def _list_record_worker(record, _list_id=list_id, _bc=list_breadcrumb):
                async for entity in self._yield_record_with_notes(record, _list_id, _bc):
                    yield entity

            async for entity in self.process_entities_concurrent(
                items=records,
                worker=_list_record_worker,
                batch_size=10,
                preserve_order=False,
                stop_on_error=False,
            ):
                yield entity

        self.logger.info("Attio sync completed")

    async def validate(self) -> None:
        """Verify credentials by pinging the Attio API."""
        await self._get(f"{_API}/objects", params={"limit": 1})
