"""Microsoft PowerPoint source implementation.

Retrieves data from Microsoft PowerPoint, including:
 - PowerPoint presentations (.pptx, .ppt, .pptm) the user has access to from OneDrive/SharePoint

The presentations are processed as FileEntity objects, which are then:
 - Downloaded to temporary storage
 - Converted to text using document converters (python-pptx)
 - Chunked for vector indexing
 - Indexed for semantic search

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import PowerPointConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.powerpoint import PowerPointPresentationEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="PowerPoint",
    short_name="powerpoint",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=PowerPointConfig,
    labels=["Productivity", "Presentations"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class PowerPointSource(BaseSource):
    """Microsoft PowerPoint source connector integrates with the Microsoft Graph API.

    Synchronizes PowerPoint presentations from Microsoft OneDrive and SharePoint.
    Presentations are processed through Airweave's file handling pipeline which:
    - Downloads the .pptx/.ppt/.pptm file
    - Extracts text for indexing
    - Chunks content for vector search
    - Indexes for semantic search

    It provides comprehensive access to PowerPoint presentations with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    PAGE_SIZE_DRIVE = 250
    MAX_FOLDER_DEPTH = 5

    POWERPOINT_EXTENSIONS = (".pptx", ".ppt", ".pptm", ".potx", ".potm")

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
        """Make an authenticated GET request to Microsoft Graph API."""
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            # 429 is left to raise_for_status(); tenacity retries with wait_rate_limit_with_backoff
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = self._get_descriptive_error_message(url, str(e))
            self.logger.error(f"Error in API request to {url}: {error_msg}")
            raise

    def _get_descriptive_error_message(self, url: str, error: str) -> str:
        """Get descriptive error message for common OAuth scope issues."""
        if "401" in error or "Unauthorized" in error:
            if "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 PowerPoint API requires specific OAuth scopes. Please ensure your auth "
                    "provider includes: Files.Read.All, User.Read, offline_access."
                )
        if "403" in error or "Forbidden" in error:
            if "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 PowerPoint access is forbidden. Ensure Files.Read.All scope and user "
                    "permissions are granted."
                )
        return error

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Microsoft Graph API format."""
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    def _process_drive_page_items(
        self, items: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Split drive items into PowerPoint files and subfolder IDs."""
        ppt_items: List[Dict[str, Any]] = []
        folder_ids: List[str] = []
        for item in items:
            if item.get("deleted"):
                self.logger.debug(f"Skipping deleted item: {item.get('name', '')}")
                continue
            file_name = item.get("name", "")
            if file_name.lower().endswith(self.POWERPOINT_EXTENSIONS):
                ppt_items.append(item)
            elif "folder" in item:
                folder_id = item.get("id")
                if folder_id:
                    folder_ids.append(folder_id)
        return ppt_items, folder_ids

    async def _discover_powerpoint_files_recursive(
        self,
        client: httpx.AsyncClient,
        folder_id: Optional[str] = None,
        depth: int = 0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively discover PowerPoint presentations in drive folders."""
        if depth > self.MAX_FOLDER_DEPTH:
            self.logger.debug(f"Max folder depth {self.MAX_FOLDER_DEPTH} reached, skipping")
            return

        url = (
            f"{self.GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
            if folder_id
            else f"{self.GRAPH_BASE_URL}/me/drive/root/children"
        )
        params: Optional[dict] = {"$top": self.PAGE_SIZE_DRIVE}

        try:
            while url:
                data = await self._get_with_auth(client, url, params=params)
                items = data.get("value", [])
                ppt_items, folder_ids = self._process_drive_page_items(items)
                for item in ppt_items:
                    yield item
                for subfolder_id in folder_ids:
                    async for ppt_file in self._discover_powerpoint_files_recursive(
                        client, subfolder_id, depth + 1
                    ):
                        yield ppt_file
                url = data.get("@odata.nextLink")
                params = None if url else params
        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {str(e)}")

    async def _generate_presentation_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[PowerPointPresentationEntity, None]:
        """Generate PowerPointPresentationEntity objects for presentations in user's drive."""
        self.logger.debug("Starting PowerPoint presentation discovery")
        document_count = 0

        try:
            async for item_data in self._discover_powerpoint_files_recursive(client):
                document_count += 1
                document_id = item_data.get("id")
                file_name = item_data.get("name", "Unknown")

                title = file_name
                for ext in self.POWERPOINT_EXTENSIONS:
                    if file_name.lower().endswith(ext):
                        title = file_name[: -len(ext)]
                        break

                if document_count <= 10 or document_count % 50 == 0:
                    self.logger.debug(f"Found PowerPoint presentation #{document_count}: {title}")

                content_download_url = f"{self.GRAPH_BASE_URL}/me/drive/items/{document_id}/content"

                parent_ref = item_data.get("parentReference", {})
                folder_path = parent_ref.get("path", "")
                if folder_path and "/root:" in folder_path:
                    # /drive/root:/MyFolder/Docs -> /MyFolder/Docs
                    folder_path = (
                        folder_path.split("/root:", 1)[1].lstrip(":")
                        if "/root:" in folder_path
                        else folder_path
                    )

                mime_type = item_data.get("file", {}).get("mimeType") or (
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )

                yield PowerPointPresentationEntity(
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
                    file_type="microsoft_powerpoint",
                    mime_type=mime_type,
                    local_path=None,
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
                    "No PowerPoint presentations found in OneDrive (searched root and subfolders)"
                )
            else:
                self.logger.debug(f"Discovered {document_count} PowerPoint presentations")

        except Exception as e:
            self.logger.error(
                f"Error generating PowerPoint presentation entities: {str(e)}",
                exc_info=True,
            )
            raise

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft PowerPoint entities."""
        self.logger.debug("===== STARTING MICROSOFT POWERPOINT ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.debug("HTTP client created, starting entity generation")

                async for presentation_entity in self._generate_presentation_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: PowerPoint - {presentation_entity.title}"
                    )

                    try:
                        await self.file_downloader.download_from_url(
                            entity=presentation_entity,
                            http_client_factory=self.http_client,
                            access_token_provider=self.get_access_token,
                            logger=self.logger,
                        )

                        if not presentation_entity.local_path:
                            raise ValueError(
                                f"Download failed - no local path set for "
                                f"{presentation_entity.name}"
                            )

                        self.logger.debug(
                            f"Successfully downloaded presentation: {presentation_entity.name}"
                        )
                        yield presentation_entity

                    except FileSkippedException as e:
                        self.logger.debug(
                            f"Skipping presentation {presentation_entity.title}: {e.reason}"
                        )
                        continue

                    except Exception as e:
                        self.logger.error(
                            f"Failed to download presentation {presentation_entity.title}: {e}"
                        )
                        continue

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== MICROSOFT POWERPOINT ENTITY GENERATION COMPLETE: "
                f"{entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Microsoft PowerPoint OAuth2 token by pinging the drive endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/drive?$select=id",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
