"""Airtable source implementation for syncing bases, tables, records, and comments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import AirtableAuthConfig
from airweave.platform.configs.config import AirtableConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.airtable import (
    AirtableAttachmentEntity,
    AirtableBaseEntity,
    AirtableCommentEntity,
    AirtableRecordEntity,
    AirtableTableEntity,
    AirtableUserEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

_API = "https://api.airtable.com/v0"


@source(
    name="Airtable",
    short_name="airtable",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=AirtableAuthConfig,
    config_class=AirtableConfig,
    labels=["Database", "Spreadsheet"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AirtableSource(BaseSource):
    """Airtable source connector — syncs bases, tables, records, comments, attachments."""

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: AirtableConfig,
    ) -> AirtableSource:
        """Create a new Airtable source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Authenticated GET with retry on 429/5xx/timeout and 401 refresh."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get authenticated user information from whoami endpoint."""
        return await self._get(f"{_API}/meta/whoami")

    async def _list_bases(self) -> AsyncGenerator[Dict[str, Any], None]:
        """List all accessible bases via Meta API with pagination."""
        params: Dict[str, Any] = {}
        while True:
            data = await self._get(f"{_API}/meta/bases", params=params)
            for base in data.get("bases", []):
                yield base

            offset = data.get("offset")
            if not offset:
                break
            params["offset"] = offset

    async def _list_records(
        self, base_id: str, table_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all records in a table with pagination."""
        url = f"{_API}/{base_id}/{table_id}"
        params: Dict[str, Any] = {"pageSize": 100}

        while True:
            data = await self._get(url, params=params)
            for record in data.get("records", []):
                yield record

            offset = data.get("offset")
            if not offset:
                break
            params["offset"] = offset

    async def _list_comments(
        self, base_id: str, table_id: str, record_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all comments for a record with pagination."""
        url = f"{_API}/{base_id}/{table_id}/{record_id}/comments"
        params: Dict[str, Any] = {"pageSize": 100}

        while True:
            data = await self._get(url, params=params)
            for comment in data.get("comments", []):
                yield comment

            offset = data.get("offset")
            if not offset:
                break
            params["offset"] = offset

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_base_entities(self) -> AsyncGenerator[AirtableBaseEntity, None]:
        """Generate base entities."""
        async for base in self._list_bases():
            if not base.get("id"):
                continue
            yield AirtableBaseEntity.from_api(base)

    async def _generate_table_entities(
        self, base_id: str, base_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[AirtableTableEntity, None]:
        """Generate table entities for a base."""
        schema = await self._get(f"{_API}/meta/bases/{base_id}/tables")
        for table in schema.get("tables", []):
            if not table.get("id"):
                continue
            yield AirtableTableEntity.from_api(
                table, base_id=base_id, breadcrumbs=[base_breadcrumb]
            )

    async def _generate_comment_entities(
        self,
        base_id: str,
        table_id: str,
        record_id: str,
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[AirtableCommentEntity, None]:
        """Generate comment entities for a record."""
        async for comment in self._list_comments(base_id, table_id, record_id):
            if not comment.get("id"):
                continue
            yield AirtableCommentEntity.from_api(
                comment,
                record_id=record_id,
                base_id=base_id,
                table_id=table_id,
                breadcrumbs=record_breadcrumbs,
            )

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def _download_attachment(
        self, entity: AirtableAttachmentEntity, files: FileService
    ) -> AirtableAttachmentEntity | None:
        """Download an attachment. Returns None on expected skips.

        401 after refresh propagates (token is dead → abort sync).
        Infrastructure failures (IOError, OSError) propagate.
        Other HTTP errors skip the file.
        """
        try:
            await files.download_from_url(
                entity=entity,
                client=self.http_client,
                auth=self.auth,
                logger=self.logger,
            )
            if not entity.local_path:
                self.logger.warning(f"Download produced no local path for {entity.name}")
                return None
            return entity
        except FileSkippedException as e:
            self.logger.debug(f"Skipping file: {e.reason}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(f"HTTP {e.response.status_code} downloading {entity.name}: {e}")
            return None

    async def _generate_attachment_entities(
        self,
        base_id: str,
        table_id: str,
        table_name: str,
        record: Dict[str, Any],
        record_breadcrumbs: List[Breadcrumb],
        files: FileService,
    ) -> AsyncGenerator[AirtableAttachmentEntity, None]:
        """Generate attachment entities for a record."""
        record_id = record.get("id")
        if not record_id:
            return

        for field_name, field_value in record.get("fields", {}).items():
            if not isinstance(field_value, list):
                continue
            for attachment in field_value:
                if not isinstance(attachment, dict):
                    continue

                entity = AirtableAttachmentEntity.from_api(
                    attachment,
                    base_id=base_id,
                    table_id=table_id,
                    table_name=table_name,
                    record_id=record_id,
                    field_name=field_name,
                    breadcrumbs=record_breadcrumbs,
                )
                if not entity:
                    continue

                downloaded = await self._download_attachment(entity, files)
                if downloaded:
                    yield downloaded

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
        """Generate all entities from Airtable."""
        user_info = await self._get_user_info()
        if user_info:
            yield AirtableUserEntity.from_api(user_info)

        async for base_entity in self._generate_base_entities():
            yield base_entity

            base_bc = Breadcrumb(
                entity_id=base_entity.base_id,
                name=base_entity.name,
                entity_type="AirtableBaseEntity",
            )

            try:
                async for table_entity in self._generate_table_entities(
                    base_entity.base_id, base_bc
                ):
                    yield table_entity

                    table_bc = Breadcrumb(
                        entity_id=table_entity.table_id,
                        name=table_entity.name,
                        entity_type="AirtableTableEntity",
                    )
                    table_bcs = [base_bc, table_bc]

                    async for record in self._list_records(
                        base_entity.base_id, table_entity.table_id
                    ):
                        if not record.get("id"):
                            continue

                        record_entity = AirtableRecordEntity.from_api(
                            record,
                            base_id=base_entity.base_id,
                            table_id=table_entity.table_id,
                            table_name=table_entity.name,
                            breadcrumbs=table_bcs,
                        )
                        yield record_entity

                        record_bcs = [
                            *table_bcs,
                            Breadcrumb(
                                entity_id=record_entity.record_id,
                                name=record_entity.name,
                                entity_type="AirtableRecordEntity",
                            ),
                        ]

                        try:
                            async for comment in self._generate_comment_entities(
                                base_entity.base_id,
                                table_entity.table_id,
                                record_entity.record_id,
                                record_bcs,
                            ):
                                yield comment
                        except SourceAuthError:
                            raise
                        except SourceError as exc:
                            self.logger.warning(
                                f"Failed to fetch comments for record "
                                f"{record_entity.record_id}: {exc}"
                            )

                        if files:
                            async for att in self._generate_attachment_entities(
                                base_entity.base_id,
                                table_entity.table_id,
                                table_entity.name,
                                record,
                                record_bcs,
                                files,
                            ):
                                yield att

            except SourceAuthError:
                raise
            except SourceError as exc:
                self.logger.warning(f"Failed to process base {base_entity.base_id}: {exc}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate(self) -> None:
        """Validate credentials by pinging Airtable's bases metadata endpoint."""
        await self._get(f"{_API}/meta/bases")
