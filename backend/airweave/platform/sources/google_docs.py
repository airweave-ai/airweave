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

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import GoogleDocsConfig
from airweave.platform.cursors import GoogleDocsCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.google_docs import GoogleDocsDocumentEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


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
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleDocsSource":
        """Create a new Google Docs source instance with the provided OAuth access token.

        Args:
            access_token: OAuth2 access token for Google Drive API
            config: Optional configuration dict with:
                - include_trashed: Include trashed documents (default: False)
                - include_shared: Include shared documents (default: True)
                - batch_size: Number of documents to process concurrently (default: 30)
                - batch_generation: Enable concurrent processing (default: True)

        Returns:
            Configured GoogleDocsSource instance
        """
        instance = cls()
        instance.access_token = access_token

        config = config or {}
        instance.include_trashed = config.get("include_trashed", False)
        instance.include_shared = config.get("include_shared", True)

        # Concurrency configuration
        instance.batch_size = int(config.get("batch_size", 30))
        instance.batch_generation = bool(config.get("batch_generation", True))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        return instance

    async def validate(self) -> bool:
        """Validate the Google Docs source connection.

        Tests the connection by making a simple API call to list drives.

        Returns:
            True if connection is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/drive/v3/about?fields=user",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    # --- Incremental sync support (cursor field) ---
    def get_default_cursor_field(self) -> Optional[str]:
        """Default cursor field name for Google Docs incremental sync.

        Uses the Drive Changes API page token for incremental syncing.

        Returns:
            Cursor field name: "start_page_token"
        """
        return "start_page_token"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate the cursor field for Google Docs.

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If cursor field is not "start_page_token"
        """
        if cursor_field != "start_page_token":
            raise ValueError(
                f"Google Docs only supports 'start_page_token' cursor field, got: {cursor_field}"
            )

    async def get_initial_cursor_value(self) -> Dict[str, Any]:
        """Get initial cursor value for incremental sync.

        Retrieves the current start page token from the Drive Changes API.

        Returns:
            Dict with start_page_token for tracking changes
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(
                "https://www.googleapis.com/drive/v3/changes/startPageToken",
                headers=headers,
            )

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    "https://www.googleapis.com/drive/v3/changes/startPageToken",
                    headers=headers,
                )

            response.raise_for_status()
            data = response.json()
            return {"start_page_token": data.get("startPageToken")}

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse RFC3339 timestamps returned by Google Drive."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _has_file_changed(self, file_obj: Dict) -> bool:
        """Check if file metadata indicates change without downloading.

        Compares: modifiedTime, md5Checksum, size
        Returns True if file is new or changed, False if unchanged.

        Args:
            file_obj: File metadata from Google Drive API

        Returns:
            True if file should be processed (new or changed), False if unchanged
        """
        if not self.cursor:
            return True

        file_id = file_obj.get("id")
        if not file_id:
            return True

        cursor_data = self.cursor.data
        file_metadata = cursor_data.get("file_metadata", {})
        stored_meta = file_metadata.get(file_id)

        if not stored_meta:
            return True

        current_modified = file_obj.get("modifiedTime")
        current_md5 = file_obj.get("md5Checksum")
        current_size = file_obj.get("size")

        if (
            stored_meta.get("modified_time") != current_modified
            or stored_meta.get("md5_checksum") != current_md5
            or stored_meta.get("size") != current_size
        ):
            return True

        return False

    def _store_file_metadata(self, file_obj: Dict) -> None:
        """Store file metadata in cursor for future change detection.

        Args:
            file_obj: File metadata from Google Drive API
        """
        if not self.cursor:
            return

        file_id = file_obj.get("id")
        if not file_id:
            return

        cursor_data = self.cursor.data
        file_metadata = cursor_data.get("file_metadata", {})

        file_metadata[file_id] = {
            "modified_time": file_obj.get("modifiedTime"),
            "md5_checksum": file_obj.get("md5Checksum"),
            "size": file_obj.get("size"),
        }

        self.cursor.update(file_metadata=file_metadata)

    async def _store_next_start_page_token(self, client: httpx.AsyncClient) -> None:
        """Fetch and store the next start page token for future incremental syncs.

        Args:
            client: HTTP client for API requests
        """
        if not self.cursor:
            return

        try:
            url = "https://www.googleapis.com/drive/v3/changes/startPageToken"
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(url, headers=headers)

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers)

            response.raise_for_status()
            data = response.json()
            token = data.get("startPageToken")

            if token:
                self.cursor.update(start_page_token=token)
                self.logger.info(
                    f"Stored new start page token for next incremental sync: {token[:20]}..."
                )
        except Exception as e:
            self.logger.error(f"Failed to fetch/store next start page token: {e}")

    # --- Main sync method ---
    async def generate_entities(
        self, existing_cursor_value: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from Google Docs documents.

        Args:
            existing_cursor_value: Optional cursor for incremental sync with start_page_token

        Yields:
            GoogleDocsDocumentEntity objects for each document found
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Check cursor data
            cursor_data = self.cursor.data if self.cursor else {}
            start_token = cursor_data.get("start_page_token")

            # If we have a cursor, do incremental sync via changes API
            if start_token:
                self.logger.info(
                    f"📊 Incremental sync mode - processing changes only (token={start_token[:20]}...)"
                )

                async for entity in self._process_changes(client, start_token):
                    yield entity
            else:
                # Full sync: list all Google Docs
                self.logger.info("🔄 Full sync mode - listing all documents")

                async for entity in self._list_and_process_documents(client):
                    yield entity

                # Store start page token for next incremental sync
                await self._store_next_start_page_token(client)

    # --- Incremental sync via Changes API ---
    async def _process_changes(  # noqa: C901
        self, client: httpx.AsyncClient, start_token: str
    ) -> AsyncGenerator[GoogleDocsDocumentEntity, None]:
        """Process changes from the Drive Changes API.

        Args:
            client: HTTP client for API requests
            start_token: Starting page token for changes

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

            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()

            # Process changes
            changes = data.get("changes", [])
            for change in changes:
                file_data = change.get("file")
                removed = change.get("removed", False)

                # Only process Google Docs files
                if (
                    file_data
                    and file_data.get("mimeType") == "application/vnd.google-apps.document"
                ):
                    if not removed and not self._should_filter_document(file_data):
                        # Check if file actually changed using metadata
                        if not self._has_file_changed(file_data):
                            self.logger.debug(
                                f"Document {file_data.get('name')} unchanged (metadata match) - skipping"
                            )
                            continue

                        entity = await self._create_document_entity(client, file_data)
                        if entity:
                            # Download the file using file downloader
                            try:
                                await self.file_downloader.download_from_url(
                                    entity=entity,
                                    http_client_factory=self.http_client,
                                    access_token_provider=self.get_access_token,
                                    logger=self.logger,
                                )

                                # Verify download succeeded
                                if not entity.local_path:
                                    self.logger.error(
                                        f"Download failed - no local path set for {entity.name}"
                                    )
                                    continue

                                # Store metadata for future change detection
                                self._store_file_metadata(file_data)

                                self.logger.debug(
                                    f"Successfully downloaded document: {entity.name}"
                                )
                                yield entity

                            except FileSkippedException as e:
                                # File intentionally skipped (unsupported type, too large, etc.)
                                # Not an error
                                self.logger.debug(f"Skipping file: {e.reason}")
                                continue

                            except Exception as e:
                                self.logger.error(
                                    f"Failed to download document {entity.title}: {e}"
                                )
                                # Continue with other documents
                                continue

            # Update pagination
            page_token = data.get("nextPageToken")
            if data.get("newStartPageToken"):
                latest_new_start = data["newStartPageToken"]

            if not page_token:
                break

        # Update cursor for next incremental sync
        if latest_new_start and self.cursor:
            self.cursor.update(start_page_token=latest_new_start)
            self.logger.info(
                f"Updated cursor with new start page token: {latest_new_start[:20]}..."
            )

    # --- Full sync: list all documents ---
    async def _list_and_process_documents(  # noqa: C901
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GoogleDocsDocumentEntity, None]:
        """List all Google Docs documents and create entities.

        Args:
            client: HTTP client for API requests

        Yields:
            GoogleDocsDocumentEntity for each document found
        """
        url = "https://www.googleapis.com/drive/v3/files"

        # Build query to filter for Google Docs only
        query_parts = ["mimeType = 'application/vnd.google-apps.document'"]
        if not self.include_trashed:
            query_parts.append("trashed = false")

        query = " and ".join(query_parts)

        params = {
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

        while url:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            self.logger.debug(f"Listing documents page {page_count + 1}: {url}")

            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()

            files = data.get("files", [])
            page_count += 1
            total_docs += len(files)

            self.logger.debug(
                f"Page {page_count}: Found {len(files)} documents (total: {total_docs})"
            )

            # Process documents
            for file_data in files:
                if not self._should_filter_document(file_data):
                    entity = await self._create_document_entity(client, file_data)
                    if entity:
                        # Download the file using file downloader
                        try:
                            await self.file_downloader.download_from_url(
                                entity=entity,
                                http_client_factory=self.http_client,
                                access_token_provider=self.get_access_token,
                                logger=self.logger,
                            )

                            # Verify download succeeded
                            if not entity.local_path:
                                self.logger.error(
                                    f"Download failed - no local path set for {entity.name}"
                                )
                                continue

                            # Store metadata for future change detection
                            self._store_file_metadata(file_data)

                            self.logger.debug(f"Successfully downloaded document: {entity.name}")
                            yield entity

                        except FileSkippedException as e:
                            # File intentionally skipped (unsupported type, too large, etc.)
                            # Not an error
                            self.logger.debug(f"Skipping file: {e.reason}")
                            continue

                        except Exception as e:
                            self.logger.error(f"Failed to download document {entity.title}: {e}")
                            # Continue with other documents
                            continue

            # Check for next page
            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
            else:
                url = None

        self.logger.debug(f"Completed document listing: {total_docs} total documents found")

    def _should_filter_document(self, file_data: Dict[str, Any]) -> bool:
        """Determine if a document should be filtered out.

        Args:
            file_data: File metadata from Drive API

        Returns:
            True if document should be filtered, False otherwise
        """
        # Filter trashed documents if configured
        if not self.include_trashed and file_data.get("trashed", False):
            return True

        # Filter shared documents if configured
        if not self.include_shared and file_data.get("shared", False):
            return True

        return False

    async def _create_document_entity(
        self, client: httpx.AsyncClient, file_data: Dict[str, Any]
    ) -> Optional[GoogleDocsDocumentEntity]:
        """Create a GoogleDocsDocumentEntity from file metadata.

        Args:
            client: HTTP client for API requests
            file_data: File metadata from Drive API

        Returns:
            GoogleDocsDocumentEntity or None if creation fails
        """
        try:
            file_id = file_data["id"]

            # Generate export URL for DOCX content
            export_mime = (
                "application%2Fvnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            export_url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}"
            )

            # Parse timestamps
            created_time = self._parse_datetime(file_data.get("createdTime")) or datetime.utcnow()
            modified_time = self._parse_datetime(file_data.get("modifiedTime")) or created_time
            modified_by_me_time = self._parse_datetime(file_data.get("modifiedByMeTime"))
            viewed_by_me_time = self._parse_datetime(file_data.get("viewedByMeTime"))
            shared_with_me_time = self._parse_datetime(file_data.get("sharedWithMeTime"))

            # Prepare name with .docx extension for file processing
            doc_name = file_data.get("name", "Untitled Document")
            if not doc_name.endswith(".docx"):
                doc_name_with_ext = f"{doc_name}.docx"
            else:
                doc_name_with_ext = doc_name

            # Create entity
            entity = GoogleDocsDocumentEntity(
                breadcrumbs=[],
                document_key=file_id,
                title=doc_name,
                created_timestamp=created_time,
                modified_timestamp=modified_time,
                name=doc_name_with_ext,
                created_at=created_time,
                updated_at=modified_time,
                url=export_url,  # Use export URL for downloading (file downloader uses entity.url)
                size=int(file_data.get("size") or 0),
                file_type="google_doc",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                local_path=None,  # Will be set after download
                description=file_data.get("description"),
                starred=file_data.get("starred", False),
                trashed=file_data.get("trashed", False),
                explicitly_trashed=file_data.get("explicitlyTrashed", False),
                shared=file_data.get("shared", False),
                shared_with_me_time=shared_with_me_time,
                sharing_user=file_data.get("sharingUser"),
                owners=file_data.get("owners", []),
                permissions=file_data.get("permissions"),
                parents=file_data.get("parents", []),
                web_view_link=file_data.get("webViewLink"),
                icon_link=file_data.get("iconLink"),
                created_time=created_time,
                modified_time=modified_time,
                modified_by_me_time=modified_by_me_time,
                viewed_by_me_time=viewed_by_me_time,
                version=file_data.get("version"),
                export_mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                web_url_value=file_data.get("webViewLink"),
            )

            return entity

        except Exception as e:
            self.logger.error(
                f"Failed to create entity for document {file_data.get('id')}: {e}",
                exc_info=True,
            )
            return None
