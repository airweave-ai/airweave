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

from typing import Any, AsyncGenerator, Dict, Optional

from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.word import WordDocumentEntity
from airweave.platform.sources._microsoft_graph_files_base import (
    MicrosoftGraphFilesSource,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Microsoft Word",
    short_name="word",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="WordConfig",
    labels=["Productivity", "Document", "Word Processing"],
    supports_continuous=False,
)
class WordSource(MicrosoftGraphFilesSource):
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

    # Supported Word file extensions
    FILE_EXTENSIONS = (".docx", ".doc", ".docm", ".dotx", ".dotm")

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

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Microsoft Word entities.

        Yields WordDocumentEntity objects as FileEntity instances, which are then
        processed by Airweave's file handling pipeline:
        1. Document is downloaded from OneDrive
        2. Converted from .docx to markdown
        3. Chunked into searchable pieces
        4. Indexed with embeddings for semantic search
        """
        self.logger.info("===== STARTING MICROSOFT WORD ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Discover all Word documents recursively
                self.logger.info("Discovering Word documents...")
                async for file_data in self._discover_files_recursive(client):
                    entity_count += 1

                    # Create Word document entity
                    # Use Microsoft Graph /content endpoint instead of @microsoft.graph.downloadUrl
                    # The downloadUrl provides temporary signed URLs that expire quickly
                    # The /content endpoint uses OAuth and is more reliable
                    drive_id = file_data.get("parentReference", {}).get("driveId")
                    item_id = file_data["id"]
                    if drive_id:
                        content_url = (
                            f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
                        )
                    else:
                        content_url = f"{self.GRAPH_BASE_URL}/me/drive/items/{item_id}/content"

                    # Extract filename and mime type from Graph API response
                    filename = file_data.get("name", "Untitled Document")
                    mime_type = file_data.get("file", {}).get("mimeType")

                    document_entity = WordDocumentEntity(
                        entity_id=file_data["id"],
                        title=filename.rsplit(".", 1)[0].strip() if "." in filename else filename,
                        name=filename,  # Pass actual filename with extension
                        mime_type=mime_type,  # Pass actual MIME type from Graph API
                        content_download_url=content_url,
                        web_url=file_data.get("webUrl"),
                        size=file_data.get("size"),
                        created_datetime=self._parse_datetime(file_data.get("createdDateTime")),
                        last_modified_datetime=self._parse_datetime(
                            file_data.get("lastModifiedDateTime")
                        ),
                        created_by=file_data.get("createdBy"),
                        last_modified_by=file_data.get("lastModifiedBy"),
                        parent_reference=file_data.get("parentReference"),
                        drive_id=drive_id,
                        folder_path=file_data.get("parentReference", {})
                        .get("path", "")
                        .replace("/drive/root:", ""),
                    )

                    self.logger.info(
                        f"Yielding entity #{entity_count}: Word Document - {document_entity.title}"
                    )

                    # Process the file entity (downloads content and prepares for chunking)
                    processed_entity = await self.process_file_entity(document_entity)

                    # Validate downloaded file before yielding
                    if processed_entity:
                        # Check if file was actually downloaded successfully
                        file_size = processed_entity.airweave_system_metadata.total_size or 0

                        if file_size == 0:
                            self.logger.warning(
                                f"Skipping document '{document_entity.title}' - "
                                f"downloaded file is empty (0 bytes). This may indicate:\n"
                                f"  • File is a link/shortcut in OneDrive\n"
                                f"  • Permission issues preventing download\n"
                                f"  • File is corrupted in OneDrive\n"
                                f"  URL: {document_entity.web_url}"
                            )
                            continue

                        # Also skip if the file was marked to skip by the file handler
                        if processed_entity.airweave_system_metadata.should_skip:
                            self.logger.debug(
                                f"Skipping document '{document_entity.title}' - "
                                f"marked as should_skip by file handler"
                            )
                            continue

                        yield processed_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT WORD ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )
