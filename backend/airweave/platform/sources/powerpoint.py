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

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

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
from airweave.platform.configs.config import PowerPointConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.powerpoint import PowerPointPresentationEntity
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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: PowerPointConfig,
    ) -> PowerPointSource:
        """Create a new Microsoft PowerPoint source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization + Accept headers with a fresh token."""
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
            )
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _discover_powerpoint_files_recursive(
        self,
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
                data = await self._get(url, params=params)
                items = data.get("value", [])
                ppt_items, folder_ids = self._process_drive_page_items(items)
                for item in ppt_items:
                    yield item
                for subfolder_id in folder_ids:
                    async for ppt_file in self._discover_powerpoint_files_recursive(
                        subfolder_id, depth + 1
                    ):
                        yield ppt_file
                url = data.get("@odata.nextLink")
                params = None if url else params
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {str(e)}")

    async def _generate_presentation_entities(
        self,
    ) -> AsyncGenerator[PowerPointPresentationEntity, None]:
        """Generate PowerPointPresentationEntity objects for presentations in user's drive."""
        self.logger.debug("Starting PowerPoint presentation discovery")
        document_count = 0

        try:
            async for item_data in self._discover_powerpoint_files_recursive():
                document_count += 1
                entity = PowerPointPresentationEntity.from_api(
                    item_data, graph_base_url=self.GRAPH_BASE_URL
                )

                if document_count <= 10 or document_count % 50 == 0:
                    self.logger.debug(
                        f"Found PowerPoint presentation #{document_count}: {entity.title}"
                    )

                yield entity

            if document_count == 0:
                self.logger.warning(
                    "No PowerPoint presentations found in OneDrive (searched root and subfolders)"
                )
            else:
                self.logger.debug(f"Discovered {document_count} PowerPoint presentations")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error generating PowerPoint presentation entities: {str(e)}",
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft PowerPoint entities."""
        self.logger.debug("===== STARTING MICROSOFT POWERPOINT ENTITY GENERATION =====")
        entity_count = 0

        try:
            self.logger.debug("Starting entity generation")

            async for presentation_entity in self._generate_presentation_entities():
                entity_count += 1
                self.logger.debug(
                    f"Yielding entity #{entity_count}: PowerPoint - {presentation_entity.title}"
                )

                if files:
                    try:
                        await files.download_from_url(
                            entity=presentation_entity,
                            client=self.http_client,
                            auth=self.auth,
                            logger=self.logger,
                        )

                        if not presentation_entity.local_path:
                            self.logger.warning(
                                f"Download produced no local path for {presentation_entity.name}"
                            )
                            continue

                        yield presentation_entity

                    except FileSkippedException as e:
                        self.logger.debug(
                            f"Skipping presentation {presentation_entity.title}: {e.reason}"
                        )
                        continue

                    except SourceAuthError:
                        raise

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            raise
                        self.logger.warning(
                            f"HTTP {e.response.status_code} downloading "
                            f"{presentation_entity.name}: {e}"
                        )
                        continue

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to download presentation {presentation_entity.title}: {e}"
                        )
                        continue
                else:
                    yield presentation_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== MICROSOFT POWERPOINT ENTITY GENERATION COMPLETE: "
                f"{entity_count} entities ====="
            )

    async def validate(self) -> None:
        """Validate credentials by pinging the drive endpoint."""
        await self._get(
            f"{self.GRAPH_BASE_URL}/me/drive",
            params={"$select": "id"},
        )
