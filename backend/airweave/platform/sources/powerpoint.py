"""Microsoft PowerPoint source implementation.

Retrieves data from Microsoft PowerPoint, including:
 - PowerPoint presentations (.pptx, .ppt) the user has access to from OneDrive/SharePoint

The presentations are processed as FileEntity objects, which are then:
 - Downloaded to temporary storage
 - Converted to markdown/text using document converters
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
from airweave.platform.entities.powerpoint import PowerPointPresentationEntity
from airweave.platform.sources._microsoft_graph_files_base import (
    MicrosoftGraphFilesSource,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Microsoft PowerPoint",
    short_name="powerpoint",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="PowerPointConfig",
    labels=["Productivity", "Presentation", "Document"],
    supports_continuous=False,
)
class PowerPointSource(MicrosoftGraphFilesSource):
    """Microsoft PowerPoint source connector integrates with the Microsoft Graph API.

    Synchronizes PowerPoint presentations from Microsoft OneDrive and SharePoint.
    Presentations are processed through Airweave's file handling pipeline which:
    - Downloads the .pptx/.ppt file
    - Converts to markdown/text for content extraction
    - Chunks content for vector search
    - Indexes for semantic search

    It provides comprehensive access to PowerPoint presentations with proper token refresh
    and rate limiting.
    """

    # Supported PowerPoint file extensions
    FILE_EXTENSIONS = (".pptx", ".ppt", ".pptm", ".potx", ".potm", ".ppsx", ".ppsm")

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "PowerPointSource":
        """Create a new Microsoft PowerPoint source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Microsoft Graph API
            config: Optional configuration parameters

        Returns:
            Configured PowerPointSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Microsoft PowerPoint entities.

        Yields PowerPointPresentationEntity objects as FileEntity instances, which are then
        processed by Airweave's file handling pipeline:
        1. Document is downloaded from OneDrive
        2. Converted from .pptx to markdown
        3. Chunked into searchable pieces
        4. Indexed with embeddings for semantic search
        """
        self.logger.info("===== STARTING MICROSOFT POWERPOINT ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Discover all PowerPoint files recursively
                self.logger.info("Discovering PowerPoint presentations...")
                async for file_data in self._discover_files_recursive(client):
                    entity_count += 1

                    # Create PowerPoint presentation entity
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

                    presentation_entity = PowerPointPresentationEntity(
                        entity_id=file_data["id"],
                        title=(
                            file_data.get("name", "Untitled Presentation").rsplit(".", 1)[0].strip()
                        ),
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
                        f"Yielding entity #{entity_count}: PowerPoint Presentation - "
                        f"{presentation_entity.title}"
                    )

                    # Process the file entity (downloads content and prepares for chunking)
                    processed_entity = await self.process_file_entity(presentation_entity)

                    # Validate downloaded file before yielding
                    if processed_entity:
                        # Check if file was actually downloaded successfully
                        file_size = processed_entity.airweave_system_metadata.total_size or 0

                        if file_size == 0:
                            self.logger.warning(
                                f"Skipping presentation '{presentation_entity.title}' - "
                                f"downloaded file is empty (0 bytes). This may indicate:\n"
                                f"  • File is a link/shortcut in OneDrive\n"
                                f"  • Permission issues preventing download\n"
                                f"  • File is corrupted in OneDrive\n"
                                f"  URL: {presentation_entity.web_url}"
                            )
                            continue

                        # Also skip if the file was marked to skip by the file handler
                        if processed_entity.airweave_system_metadata.should_skip:
                            self.logger.debug(
                                f"Skipping presentation '{presentation_entity.title}' - "
                                f"marked as should_skip by file handler"
                            )
                            continue

                        yield processed_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT POWERPOINT ENTITY GENERATION COMPLETE: "
                f"{entity_count} entities ====="
            )
