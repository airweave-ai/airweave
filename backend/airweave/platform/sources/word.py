"""Microsoft Word source implementation.

Retrieves data from Microsoft Word, including:
 - Word documents (.docx, .doc) the user has access to from OneDrive/SharePoint

The documents are processed as FileEntity objects, which are then:
 - Downloaded to temporary storage
 - Converted to markdown using document converters
 - Chunked for vector indexing
 - Indexed for semantic search

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import WordConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.word import WordDocumentEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Word",
    short_name="word",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=WordConfig,
    labels=["Productivity", "Document", "Word Processing"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class WordSource(BaseSource):
    """Microsoft Word source connector integrates with the Microsoft Graph API.

    Synchronizes Word documents from Microsoft OneDrive and SharePoint.
    Documents are processed through Airweave's file handling pipeline which:
    - Downloads the .docx/.doc file
    - Converts to markdown for text extraction
    - Chunks content for vector search
    - Indexes for semantic search

    It provides comprehensive access to Word documents with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    # Configuration constants for optimization
    PAGE_SIZE_DRIVE = 250  # Optimal page size for drive items
    MAX_FOLDER_DEPTH = 5  # Limit recursive folder traversal depth

    # Supported Word file extensions
    WORD_EXTENSIONS = (".docx", ".doc", ".docm", ".dotx", ".dotm")

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "WordSource":
        """Create a new Microsoft Word source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Microsoft Graph API
            config: Optional configuration parameters

        Returns:
            Configured WordSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                await asyncio.sleep(float(retry_after))
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Provide more descriptive error messages for common OAuth scope issues
            error_msg = self._get_descriptive_error_message(url, str(e))
            self.logger.error(f"Error in API request to {url}: {error_msg}")
            raise

    def _get_descriptive_error_message(self, url: str, error: str) -> str:
        """Get descriptive error message for common OAuth scope issues.

        Args:
            url: The API URL that failed
            error: The original error message

        Returns:
            Enhanced error message with helpful guidance
        """
        # Check for 401 Unauthorized errors
        if "401" in error or "Unauthorized" in error:
            if "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 Word API requires specific OAuth scopes. Please ensure your auth "
                    "provider (Composio, Pipedream, etc.) includes the following scopes:\n"
                    "• Files.Read.All - Required to read Word documents from user's drive\n"
                    "• User.Read - Required to access user information\n"
                    "• offline_access - Required for token refresh\n\n"
                    "If using Composio, make sure to add 'Files.Read.All' to your "
                    "OneDrive integration scopes."
                )
            elif "/me" in url and "select=" in url:
                return (
                    f"{error}\n\n"
                    "🔧 User profile access requires the User.Read scope. Please ensure your auth "
                    "provider includes this scope in the OAuth configuration."
                )

        # Check for 403 Forbidden errors
        if "403" in error or "Forbidden" in error:
            if "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 Word document access is forbidden. This usually means:\n"
                    "• The Files.Read.All scope is missing from your OAuth configuration\n"
                    "• The user hasn't granted permission to access files\n"
                    "• The OneDrive service is not available for this user/tenant\n\n"
                    "Please check your OAuth scopes and user permissions."
                )

        # Return original error if no specific guidance available
        return error

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Microsoft Graph API format.

        Args:
            dt_str: DateTime string from API

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    async def _discover_word_files_recursive(  # noqa: C901
        self, client: httpx.AsyncClient, folder_id: Optional[str] = None, depth: int = 0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively discover Word documents in drive folders.

        Args:
            client: HTTP client for API requests
            folder_id: ID of folder to search (None for root)
            depth: Current recursion depth

        Yields:
            DriveItem dictionaries for Word documents
        """
        if depth > self.MAX_FOLDER_DEPTH:
            self.logger.debug(f"Max folder depth {self.MAX_FOLDER_DEPTH} reached, skipping")
            return

        # Build URL for folder or root
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/me/drive/root/children"

        params = {"$top": self.PAGE_SIZE_DRIVE}

        try:
            # Process all pages in this folder
            while url:
                data = await self._get_with_auth(client, url, params=params)
                items = data.get("value", [])

                folders_to_traverse = []

                for item in items:
                    file_name = item.get("name", "")

                    # Skip deleted items (trashed but still returned by API)
                    if item.get("deleted"):
                        self.logger.debug(f"Skipping deleted item: {file_name}")
                        continue

                    # Check if it's a Word document
                    if file_name.lower().endswith(self.WORD_EXTENSIONS):
                        yield item

                    # Collect folders for recursive traversal
                    elif "folder" in item:
                        folders_to_traverse.append(item.get("id"))

                # Recursively process subfolders
                for subfolder_id in folders_to_traverse:
                    async for word_file in self._discover_word_files_recursive(
                        client, subfolder_id, depth + 1
                    ):
                        yield word_file

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    params = None  # nextLink includes params

        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {str(e)}")

    async def _generate_word_document_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[WordDocumentEntity, None]:
        """Generate WordDocumentEntity objects for Word documents in user's drive.

        Recursively searches OneDrive for Word documents and yields document entities.
        Uses optimized pagination and reduced logging for production scale.

        Args:
            client: HTTP client for API requests

        Yields:
            WordDocumentEntity objects (FileEntity subclass)
        """
        self.logger.debug("Starting Word document discovery")
        document_count = 0

        try:
            # Recursively discover all Word documents
            async for item_data in self._discover_word_files_recursive(client):
                document_count += 1
                document_id = item_data.get("id")
                file_name = item_data.get("name", "Unknown")

                # Extract title (remove extension)
                title = file_name
                for ext in self.WORD_EXTENSIONS:
                    if file_name.lower().endswith(ext):
                        title = file_name[: -len(ext)]
                        break

                if document_count <= 10 or document_count % 50 == 0:
                    # Log first 10 and then every 50th document to reduce noise
                    self.logger.debug(f"Found Word document #{document_count}: {title}")

                # Build download URL for the document content
                content_download_url = f"{self.GRAPH_BASE_URL}/me/drive/items/{document_id}/content"

                # Extract folder path from parent reference
                parent_ref = item_data.get("parentReference", {})
                folder_path = parent_ref.get("path", "")
                if folder_path and "/root:" in folder_path:
                    # Clean up the path format: /drive/root:/Documents/Folder -> /Documents/Folder
                    folder_path = (
                        folder_path.split("/root:", 1)[1]
                        if "/root:" in folder_path
                        else folder_path
                    )

                # Get MIME type or default for Word documents
                mime_type = item_data.get("file", {}).get("mimeType") or (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

                yield WordDocumentEntity(
                    breadcrumbs=[],
                    name=file_name,
                    id=document_id,
                    title=title,
                    created_datetime=self._parse_datetime(item_data.get("createdDateTime")),
                    last_modified_datetime=self._parse_datetime(
                        item_data.get("lastModifiedDateTime")
                    ),
                    url=content_download_url,
                    size=item_data.get("size", 0),
                    file_type="microsoft_word_doc",
                    mime_type=mime_type,
                    local_path=None,  # Will be set after download
                    web_url_override=item_data.get("webUrl"),
                    content_download_url=content_download_url,
                    created_by=item_data.get("createdBy"),
                    last_modified_by=item_data.get("lastModifiedBy"),
                    parent_reference=parent_ref,
                    drive_id=parent_ref.get("driveId"),
                    folder_path=folder_path,
                    description=item_data.get("description"),
                    shared=item_data.get("shared"),
                )

            if document_count == 0:
                self.logger.warning(
                    "No Word documents found in OneDrive (searched root and subfolders)"
                )
            else:
                self.logger.debug(f"Discovered {document_count} Word documents")

        except Exception as e:
            self.logger.error(f"Error generating Word document entities: {str(e)}", exc_info=True)
            raise

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft Word entities.

        Yields WordDocumentEntity objects as FileEntity instances, which are then
        processed by Airweave's file handling pipeline:
        1. Document is downloaded from OneDrive
        2. Converted from .docx to markdown
        3. Chunked into searchable pieces
        4. Indexed with embeddings for semantic search
        """
        self.logger.debug("===== STARTING MICROSOFT WORD ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.debug("HTTP client created, starting entity generation")

                # Generate Word document entities
                self.logger.debug("Generating Word document entities...")
                async for document_entity in self._generate_word_document_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Word Document - {document_entity.title}"
                    )

                    # Download the file using file downloader
                    try:
                        await self.file_downloader.download_from_url(
                            entity=document_entity,
                            http_client_factory=self.http_client,
                            access_token_provider=self.get_access_token,
                            logger=self.logger,
                        )

                        # Verify download succeeded
                        if not document_entity.local_path:
                            raise ValueError(
                                f"Download failed - no local path set for {document_entity.name}"
                            )

                        self.logger.debug(
                            f"Successfully downloaded document: {document_entity.name}"
                        )
                        yield document_entity

                    except FileSkippedException as e:
                        # Document intentionally skipped (unsupported type, too large, etc.)
                        self.logger.debug(f"Skipping document {document_entity.title}: {e.reason}")
                        continue

                    except Exception as e:
                        self.logger.error(
                            f"Failed to download document {document_entity.title}: {e}"
                        )
                        # Continue with other documents
                        continue

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== MICROSOFT WORD ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Microsoft Word OAuth2 token by pinging the drive endpoint.

        Returns:
            True if token is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/drive?$select=id",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
