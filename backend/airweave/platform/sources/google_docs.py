"""Google Docs source implementation.

Retrieves Google Docs documents from a user's Google Drive using the Drive API (read-only mode):
  - Lists all Google Docs documents (application/vnd.google-apps.document)
  - Exports document content as DOCX for processing
  - Maintains metadata like permissions, sharing, and modification times

The documents are represented as FileEntity objects that get processed through
Airweave's file processing pipeline to create searchable chunks.

References:
    https://developers.google.com/drive/api/v3/reference/files
    https://developers.google.com/drive/api/guides/manage-downloads
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import GoogleDocsConfig
from airweave.platform.cursors import GoogleDocsCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.google_docs import GoogleDocsDocumentEntity
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


@source(
    name="Google Docs",
    short_name="google_docs",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
        AuthenticationMethod.OAUTH_BYOC,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=GoogleDocsConfig,
    labels=["Document Management", "Productivity"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=GoogleDocsCursor,
)
class GoogleDocsSource(BaseSource):
    """Google Docs source connector integrates with Google Drive API to extract Google Docs.

    Connects to your Google Drive account to retrieve Google Docs documents.
    Documents are exported as DOCX and processed through Airweave's file
    processing pipeline to enable full-text semantic search across document content.

    The connector handles:
    - Document listing and filtering
    - Content export and download (DOCX format)
    - Metadata preservation (ownership, sharing, timestamps)
    - Incremental sync via Drive Changes API
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GoogleDocsConfig,
    ) -> GoogleDocsSource:
        """Create a new Google Docs source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.include_trashed = config.include_trashed if config else False
        instance.include_shared = config.include_shared if config else True
        return instance

    async def validate(self) -> None:
        """Validate credentials by pinging Drive API about (user)."""
        await self._get(
            "https://www.googleapis.com/drive/v3/about",
            params={"fields": "user"},
        )

    # --- HTTP helpers ---

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make authenticated GET request to Google Drive API with token refresh support."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # --- File downloads ---

    async def _download_document(
        self, entity: GoogleDocsDocumentEntity, files: FileService | None
    ) -> bool:
        """Download document content. Returns True if download succeeded.

        401 propagates (dead token). Other HTTP errors log a warning and skip.
        """
        if not files:
            return False
        try:
            await files.download_from_url(
                entity=entity, client=self.http_client, auth=self.auth, logger=self.logger
            )
            if not entity.local_path:
                self.logger.warning(f"Download failed - no local path set for {entity.name}")
                return False
            self.logger.debug(f"Successfully downloaded document: {entity.name}")
            return True
        except FileSkippedException as e:
            self.logger.debug(f"Skipping file: {e.reason}")
            return False
        except SourceAuthError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(f"Failed to download document {entity.name}: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Failed to download document {entity.name}: {e}")
            return False

    # --- Incremental sync helpers ---

    async def _get_start_page_token(self) -> Optional[str]:
        """Retrieve the current start page token from the Drive Changes API."""
        try:
            data = await self._get("https://www.googleapis.com/drive/v3/changes/startPageToken")
            return data.get("startPageToken")
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to get start page token: {e}")
            return None

    # --- Main sync method ---

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from Google Docs documents.

        Yields:
            GoogleDocsDocumentEntity objects for each document found
        """
        cursor_data = cursor.data if cursor else {}

        if cursor_data.get("start_page_token"):
            start_token = cursor_data["start_page_token"]
            self.logger.debug(f"Starting incremental sync from page token: {start_token}")

            async for entity in self._process_changes(start_token, cursor=cursor, files=files):
                yield entity
        else:
            self.logger.debug("Starting full sync of Google Docs")

            start_page_token = await self._get_start_page_token()

            async for entity in self._list_and_process_documents(files=files):
                yield entity

            if cursor and start_page_token:
                cursor.update(start_page_token=start_page_token)

    # --- Incremental sync via Changes API ---

    async def _process_changes(
        self,
        start_token: str,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[GoogleDocsDocumentEntity, None]:
        """Process changes from the Drive Changes API.

        Args:
            start_token: Starting page token for changes
            cursor: Sync cursor to update with new start page token
            files: File service for downloading document content

        Yields:
            GoogleDocsDocumentEntity for changed/new documents
        """
        url = "https://www.googleapis.com/drive/v3/changes"
        page_token = start_token
        latest_new_start = None

        while page_token:
            params = {
                "pageToken": page_token,
                "pageSize": 100,
                "includeItemsFromAllDrives": "true",
                "supportsAllDrives": "true",
                "fields": "nextPageToken, newStartPageToken, changes(fileId, removed, file(*))",
            }

            data = await self._get(url, params=params)

            changes = data.get("changes", [])
            for change in changes:
                file_data = change.get("file")
                removed = change.get("removed", False)

                if (
                    file_data
                    and file_data.get("mimeType") == "application/vnd.google-apps.document"
                ):
                    if not removed and not self._should_filter_document(file_data):
                        try:
                            entity = GoogleDocsDocumentEntity.from_api(file_data)
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to create entity for document {file_data.get('id')}: {e}",
                                exc_info=True,
                            )
                            continue

                        if await self._download_document(entity, files):
                            yield entity

            page_token = data.get("nextPageToken")
            if data.get("newStartPageToken"):
                latest_new_start = data["newStartPageToken"]

            if not page_token:
                break

        if latest_new_start and cursor:
            cursor.update(start_page_token=latest_new_start)

    # --- Full sync: list all documents ---

    async def _list_and_process_documents(
        self,
        *,
        files: FileService | None = None,
    ) -> AsyncGenerator[GoogleDocsDocumentEntity, None]:
        """List all Google Docs documents and create entities.

        Yields:
            GoogleDocsDocumentEntity for each document found
        """
        url = "https://www.googleapis.com/drive/v3/files"

        query_parts = ["mimeType = 'application/vnd.google-apps.document'"]
        if not self.include_trashed:
            query_parts.append("trashed = false")

        query = " and ".join(query_parts)

        params: Dict[str, Any] = {
            "pageSize": 100,
            "corpora": "user",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "q": query,
            "fields": (
                "nextPageToken, files(id, name, mimeType, description, starred, trashed, "
                "explicitlyTrashed, parents, shared, sharedWithMeTime, sharingUser, "
                "owners, permissions, webViewLink, iconLink, createdTime, modifiedTime, "
                "modifiedByMeTime, viewedByMeTime, size, version, capabilities)"
            ),
        }

        page_count = 0
        total_docs = 0

        while True:
            self.logger.debug(f"Listing documents page {page_count + 1}")

            data = await self._get(url, params=params)

            docs = data.get("files", [])
            page_count += 1
            total_docs += len(docs)

            self.logger.debug(
                f"Page {page_count}: Found {len(docs)} documents (total: {total_docs})"
            )

            for file_data in docs:
                if not self._should_filter_document(file_data):
                    try:
                        entity = GoogleDocsDocumentEntity.from_api(file_data)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to create entity for document {file_data.get('id')}: {e}",
                            exc_info=True,
                        )
                        continue

                    if await self._download_document(entity, files):
                        yield entity

            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
            else:
                break

        self.logger.debug(f"Completed document listing: {total_docs} total documents found")

    def _should_filter_document(self, file_data: Dict[str, Any]) -> bool:
        """Determine if a document should be filtered out.

        Args:
            file_data: File metadata from Drive API

        Returns:
            True if document should be filtered, False otherwise
        """
        if not self.include_trashed and file_data.get("trashed", False):
            return True

        if not self.include_shared and file_data.get("shared", False):
            return True

        return False
