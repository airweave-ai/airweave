"""SharePoint source implementation using Microsoft Graph API.

Retrieves data from SharePoint, including:
 - Users in the organization
 - Groups in the organization
 - Sites (starting from root site)
 - Drives (document libraries) within sites
 - DriveItems (files and folders) within drives

Reference:
  https://learn.microsoft.com/en-us/graph/sharepoint-concept-overview
  https://learn.microsoft.com/en-us/graph/api/resources/site
  https://learn.microsoft.com/en-us/graph/api/resources/drive
"""

from __future__ import annotations

from collections import deque
from typing import AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
)
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import SharePointConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.sharepoint import (
    SharePointDriveEntity,
    SharePointDriveItemEntity,
    SharePointGroupEntity,
    SharePointListEntity,
    SharePointListItemEntity,
    SharePointPageEntity,
    SharePointSiteEntity,
    SharePointUserEntity,
    _parse_dt,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="SharePoint",
    short_name="sharepoint",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=SharePointConfig,
    labels=["File Storage", "Collaboration"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class SharePointSource(BaseSource):
    """SharePoint source connector integrates with the Microsoft Graph API.

    Synchronizes data from SharePoint including sites, document libraries,
    files, users, and groups.

    It provides comprehensive access to SharePoint resources with intelligent
    error handling and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SharePointConfig,
    ) -> SharePointSource:
        """Create a new SharePoint source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Microsoft Graph API — refreshing token")
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}", "Accept": "application/json"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_user_entities(self) -> AsyncGenerator[SharePointUserEntity, None]:
        """Generate SharePointUserEntity objects for users in the organization."""
        self.logger.debug("Starting user entity generation")
        url = f"{self.GRAPH_BASE_URL}/users"
        params = {
            "$top": 100,
            "$select": (
                "id,displayName,userPrincipalName,mail,jobTitle,department,"
                "officeLocation,mobilePhone,businessPhones,accountEnabled"
            ),
        }
        user_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching users from: {url}")
                data = await self._get(url, params=params)
                users = data.get("value", [])
                self.logger.debug(f"Retrieved {len(users)} users")

                for user_data in users:
                    user_count += 1
                    user_id = user_data.get("id")
                    display_name = user_data.get("displayName", "Unknown User")

                    self.logger.debug(f"Processing user #{user_count}: {display_name}")

                    yield SharePointUserEntity(
                        breadcrumbs=[],
                        id=user_id,
                        name=display_name,
                        created_at=None,
                        updated_at=None,
                        display_name=display_name,
                        user_principal_name=user_data.get("userPrincipalName"),
                        mail=user_data.get("mail"),
                        job_title=user_data.get("jobTitle"),
                        department=user_data.get("department"),
                        office_location=user_data.get("officeLocation"),
                        mobile_phone=user_data.get("mobilePhone"),
                        business_phones=user_data.get("businessPhones"),
                        account_enabled=user_data.get("accountEnabled"),
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(f"Completed user generation. Total users: {user_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating user entities: {str(e)}")
            raise

    async def _generate_group_entities(self) -> AsyncGenerator[SharePointGroupEntity, None]:
        """Generate SharePointGroupEntity objects for groups in the organization."""
        self.logger.debug("Starting group entity generation")
        url = f"{self.GRAPH_BASE_URL}/groups"
        params = {
            "$top": 100,
            "$select": (
                "id,displayName,description,mail,mailEnabled,securityEnabled,"
                "groupTypes,visibility,createdDateTime"
            ),
        }
        group_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching groups from: {url}")
                data = await self._get(url, params=params)
                groups = data.get("value", [])
                self.logger.debug(f"Retrieved {len(groups)} groups")

                for group_data in groups:
                    group_count += 1
                    self.logger.debug(
                        f"Processing group #{group_count}: "
                        f"{group_data.get('displayName', 'Unknown Group')}"
                    )
                    yield SharePointGroupEntity.from_api(group_data)

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(f"Completed group generation. Total groups: {group_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating group entities: {str(e)}")
            raise

    async def _generate_site_entities(self) -> AsyncGenerator[SharePointSiteEntity, None]:
        """Generate SharePointSiteEntity objects starting from the root site."""
        self.logger.debug("Starting site entity generation")

        try:
            url = f"{self.GRAPH_BASE_URL}/sites/root"
            self.logger.debug(f"Fetching root site from: {url}")
            site_data = await self._get(url)

            site_id = site_data.get("id")
            display_name = site_data.get("displayName", "Root Site")

            self.logger.debug(f"Processing root site: {display_name} (ID: {site_id})")

            yield SharePointSiteEntity(
                breadcrumbs=[],
                id=site_id,
                name=display_name,
                created_at=_parse_dt(site_data.get("createdDateTime")),
                updated_at=_parse_dt(site_data.get("lastModifiedDateTime")),
                display_name=display_name,
                site_name=site_data.get("name"),
                description=site_data.get("description"),
                web_url_override=site_data.get("webUrl"),
                is_personal_site=site_data.get("isPersonalSite"),
                site_collection=site_data.get("siteCollection"),
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating site entities: {str(e)}")
            raise

    async def _generate_drive_entities(
        self, site_id: str, site_name: str
    ) -> AsyncGenerator[SharePointDriveEntity, None]:
        """Generate SharePointDriveEntity objects for drives in a site."""
        self.logger.debug(f"Starting drive entity generation for site: {site_name}")
        url = f"{self.GRAPH_BASE_URL}/sites/{site_id}/drives"
        params = {"$top": 100}
        drive_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching drives from: {url}")
                data = await self._get(url, params=params)
                drives = data.get("value", [])
                self.logger.debug(f"Retrieved {len(drives)} drives for site {site_name}")

                for drive_data in drives:
                    drive_count += 1
                    self.logger.debug(
                        f"Processing drive #{drive_count}: "
                        f"{drive_data.get('name', 'Unknown Drive')}"
                    )
                    yield SharePointDriveEntity.from_api(
                        drive_data, site_id=site_id, site_name=site_name
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed drive generation for site {site_name}. Total drives: {drive_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating drive entities for site {site_name}: {str(e)}")
            raise

    async def _list_drive_items(
        self,
        drive_id: str,
        folder_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """List items in a drive using pagination."""
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/root/children"

        params = {
            "$top": 100,
            "$select": (
                "id,name,size,createdDateTime,lastModifiedDateTime,webUrl,"
                "file,folder,parentReference,createdBy,lastModifiedBy"
            ),
        }

        try:
            while url:
                data = await self._get(url, params=params)

                for item in data.get("value", []):
                    self.logger.debug(f"Found drive item: {item.get('name')}")
                    yield item

                url = data.get("@odata.nextLink")
                if url:
                    params = None
        except SourceEntityForbiddenError:
            self.logger.warning(f"Access denied to folder {folder_id}, skipping")
            return
        except SourceEntityNotFoundError:
            self.logger.warning(f"Folder {folder_id} not found, skipping")
            return

    def _get_download_url(self, drive_id: str, item_id: str) -> Optional[str]:
        """Get the download URL for a specific file item.

        Returns a Graph API content endpoint URL that can be used with the access token.
        """
        try:
            return f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
        except Exception as e:
            self.logger.warning(f"Failed to get download URL for item {item_id}: {e}")
            return None

    async def _list_all_drive_items_recursively(
        self,
        drive_id: str,
        site_id: str,
    ) -> AsyncGenerator[Dict, None]:
        """Recursively list all items in a drive using BFS approach."""
        folder_queue = deque([None])
        processed_folders = set()

        while folder_queue:
            current_folder_id = folder_queue.popleft()

            if current_folder_id in processed_folders:
                continue
            processed_folders.add(current_folder_id)

            try:
                async for item in self._list_drive_items(drive_id, current_folder_id):
                    item["_site_id"] = site_id
                    item["_drive_id"] = drive_id
                    yield item

                    if "folder" in item:
                        folder_queue.append(item["id"])
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error processing folder {current_folder_id}: {e}")
                continue

    async def _generate_drive_item_entities(  # noqa: C901
        self,
        drive_id: str,
        drive_name: str,
        site_id: str,
        site_name: str,
        site_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate SharePointDriveItemEntity objects for files in the drive."""
        self.logger.debug(f"Starting file generation for drive: {drive_name}")
        file_count = 0

        drive_breadcrumb = Breadcrumb(
            entity_id=drive_id,
            name=drive_name,
            entity_type="SharePointDriveEntity",
        )

        async for item in self._list_all_drive_items_recursively(drive_id, site_id):
            try:
                if "folder" in item:
                    continue

                download_url = self._get_download_url(drive_id, item["id"])

                file_entity = SharePointDriveItemEntity.from_api(
                    item,
                    site_id=site_id,
                    drive_id=drive_id,
                    site_breadcrumb=site_breadcrumb,
                    drive_breadcrumb=drive_breadcrumb,
                    download_url=download_url,
                )
                if not file_entity:
                    continue

                if files:
                    try:
                        await files.download_from_url(
                            entity=file_entity,
                            client=self.http_client,
                            auth=self.auth,
                            logger=self.logger,
                        )

                        if not file_entity.local_path:
                            self.logger.warning(
                                f"Download produced no local path for {file_entity.name}"
                            )
                            continue

                        file_count += 1
                        self.logger.debug(f"Processed file {file_count}: {file_entity.name}")
                        yield file_entity

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                        continue

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            raise
                        self.logger.warning(
                            f"HTTP {e.response.status_code} downloading {file_entity.name}: {e}"
                        )
                        continue

            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    f"Failed to process item {item.get('name', 'unknown')}: {str(e)}"
                )
                continue

        self.logger.debug(f"Total files processed in drive {drive_name}: {file_count}")

    async def _generate_list_entities(
        self, site_id: str, site_name: str
    ) -> AsyncGenerator[SharePointListEntity, None]:
        """Generate SharePointListEntity objects for lists in a site."""
        self.logger.debug(f"Starting list entity generation for site: {site_name}")
        url = f"{self.GRAPH_BASE_URL}/sites/{site_id}/lists"
        params = {"$top": 100, "$expand": "columns"}
        list_count = 0

        try:
            site_breadcrumb = Breadcrumb(
                entity_id=site_id,
                name=site_name,
                entity_type="SharePointSiteEntity",
            )
            while url:
                self.logger.debug(f"Fetching lists from: {url}")
                data = await self._get(url, params=params)
                lists = data.get("value", [])
                self.logger.debug(f"Retrieved {len(lists)} lists for site {site_name}")

                for list_data in lists:
                    list_count += 1
                    self.logger.debug(
                        f"Processing list #{list_count}: "
                        f"{list_data.get('displayName', 'Unknown List')}"
                    )
                    yield SharePointListEntity.from_api(
                        list_data, site_id=site_id, site_breadcrumb=site_breadcrumb
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed list generation for site {site_name}. Total lists: {list_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating list entities for site {site_name}: {str(e)}")

    async def _generate_list_item_entities(
        self,
        list_entity: SharePointListEntity,
        site_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[SharePointListItemEntity, None]:
        """Generate SharePointListItemEntity objects for items in a list."""
        list_id = list_entity.id
        list_name = list_entity.display_name or "Unknown List"
        self.logger.debug(f"Starting list item generation for list: {list_name}")

        url = f"{self.GRAPH_BASE_URL}/sites/{list_entity.site_id}/lists/{list_id}/items"
        params = {"$top": 100, "$expand": "fields"}
        item_count = 0

        list_breadcrumb = Breadcrumb(
            entity_id=list_id,
            name=list_entity.display_name or list_name,
            entity_type="SharePointListEntity",
        )

        try:
            while url:
                self.logger.debug(f"Fetching list items from: {url}")
                data = await self._get(url, params=params)
                items = data.get("value", [])
                self.logger.debug(f"Retrieved {len(items)} items for list {list_name}")

                for item_data in items:
                    item_count += 1
                    yield SharePointListItemEntity.from_api(
                        item_data,
                        site_id=list_entity.site_id,
                        list_id=list_id,
                        site_breadcrumb=site_breadcrumb,
                        list_breadcrumb=list_breadcrumb,
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed list item generation for list {list_name}. Total items: {item_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating list items for list {list_name}: {str(e)}")

    # ------------------------------------------------------------------
    # Page content extraction utilities
    # ------------------------------------------------------------------

    def _clean_html_text(self, html: str) -> str:
        """Strip HTML tags and clean text content."""
        import re

        text = re.sub(r"<[^>]+>", " ", html)
        return text.strip()

    def _extract_canvas_sections(self, canvas: Dict) -> list[str]:
        """Extract text from canvas layout sections."""
        content_parts = []
        sections = canvas.get("horizontalSections", [])
        for section in sections:
            columns = section.get("columns", [])
            for column in columns:
                webparts = column.get("webparts", [])
                for webpart in webparts:
                    inner_html = webpart.get("innerHtml", "")
                    if inner_html:
                        text = self._clean_html_text(inner_html)
                        if text:
                            content_parts.append(text)
        return content_parts

    def _extract_webparts_array(self, webparts: list) -> list[str]:
        """Extract text from webParts array (older format)."""
        content_parts = []
        for webpart in webparts:
            if isinstance(webpart, dict):
                inner_html = webpart.get("data", {}).get("innerHTML", "")
                if inner_html:
                    text = self._clean_html_text(inner_html)
                    if text:
                        content_parts.append(text)
        return content_parts

    def _extract_page_content(self, page_data: Dict) -> str:
        """Extract text content from page webParts."""
        content_parts = []

        canvas = page_data.get("canvasLayout")
        if canvas and isinstance(canvas, dict):
            content_parts = self._extract_canvas_sections(canvas)

        if not content_parts:
            webparts = page_data.get("webParts", [])
            content_parts = self._extract_webparts_array(webparts)

        return "\n\n".join(content_parts) if content_parts else ""

    async def _generate_page_entities(
        self, site_id: str, site_name: str
    ) -> AsyncGenerator[SharePointPageEntity, None]:
        """Generate SharePointPageEntity objects for pages in a site."""
        self.logger.debug(f"Starting page entity generation for site: {site_name}")
        url = f"{self.GRAPH_BASE_URL}/sites/{site_id}/pages"
        params = {"$top": 100}
        page_count = 0

        try:
            site_breadcrumb = Breadcrumb(
                entity_id=site_id,
                name=site_name,
                entity_type="SharePointSiteEntity",
            )
            while url:
                self.logger.debug(f"Fetching pages from: {url}")
                data = await self._get(url, params=params)
                pages = data.get("value", [])
                self.logger.debug(f"Retrieved {len(pages)} pages for site {site_name}")

                for page_data in pages:
                    page_count += 1
                    title = page_data.get("title", "Untitled Page")
                    self.logger.debug(f"Processing page #{page_count}: {title}")

                    content = self._extract_page_content(page_data)
                    yield SharePointPageEntity.from_api(
                        page_data,
                        site_id=site_id,
                        site_breadcrumb=site_breadcrumb,
                        content=content,
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed page generation for site {site_name}. Total pages: {page_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating page entities for site {site_name}: {str(e)}")

    # ------------------------------------------------------------------
    # Composite generators
    # ------------------------------------------------------------------

    async def _generate_lists_with_items(
        self,
        site_id: str,
        site_name: str,
        site_breadcrumb: Breadcrumb,
        start_count: int,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate list entities and their items for a site."""
        self.logger.debug(f"Generating list entities for site: {site_name}")
        current_count = start_count

        async for list_entity in self._generate_list_entities(site_id, site_name):
            current_count += 1
            self.logger.debug(
                f"Yielding entity #{current_count}: List - {list_entity.display_name}"
            )
            yield list_entity

            async for list_item_entity in self._generate_list_item_entities(
                list_entity, site_breadcrumb
            ):
                current_count += 1
                list_name = list_entity.display_name
                self.logger.debug(f"Yielding entity #{current_count}: ListItem from {list_name}")
                yield list_item_entity

    async def _generate_drives_with_items(
        self,
        site_id: str,
        site_name: str,
        site_breadcrumb: Breadcrumb,
        start_count: int,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate drive entities and their files for a site."""
        self.logger.debug(f"Generating drive entities for site: {site_name}")
        current_count = start_count

        async for drive_entity in self._generate_drive_entities(site_id, site_name):
            current_count += 1
            self.logger.debug(f"Yielding entity #{current_count}: Drive - {drive_entity.name}")
            yield drive_entity

            drive_id = drive_entity.id
            drive_name = drive_entity.name or "Document Library"

            self.logger.debug(f"Starting to process files from drive: {drive_id} ({drive_name})")

            async for file_entity in self._generate_drive_item_entities(
                drive_id, drive_name, site_id, site_name, site_breadcrumb, files=files
            ):
                current_count += 1
                entity_type = type(file_entity).__name__
                file_name = getattr(file_entity, "name", "unnamed")
                self.logger.debug(f"Yielding entity #{current_count}: {entity_type} - {file_name}")
                yield file_entity

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all SharePoint entities.

        Yields entities in the following order:
          - SharePointUserEntity for users in the organization
          - SharePointGroupEntity for groups in the organization
          - SharePointSiteEntity for the root site
          - SharePointListEntity for each list in the site
          - SharePointListItemEntity for each item in each list
          - SharePointPageEntity for each page in the site
          - SharePointDriveEntity for each drive in the site
          - SharePointDriveItemEntity for each file in each drive
        """
        self.logger.debug("===== STARTING SHAREPOINT ENTITY GENERATION =====")
        entity_count = 0

        try:
            self.logger.debug("Starting entity generation")

            async for user_entity in self._generate_user_entities():
                entity_count += 1
                self.logger.debug(
                    f"Yielding entity #{entity_count}: User - {user_entity.display_name}"
                )
                yield user_entity

            async for group_entity in self._generate_group_entities():
                entity_count += 1
                self.logger.debug(
                    f"Yielding entity #{entity_count}: Group - {group_entity.display_name}"
                )
                yield group_entity

            site_entity = None
            async for site in self._generate_site_entities():
                entity_count += 1
                self.logger.debug(f"Yielding entity #{entity_count}: Site - {site.display_name}")
                yield site
                site_entity = site
                break

            if not site_entity:
                self.logger.warning("No site found")
                return

            site_id = site_entity.id
            site_name = site_entity.display_name or "SharePoint"
            site_breadcrumb = Breadcrumb(
                entity_id=site_id,
                name=site_name,
                entity_type="SharePointSiteEntity",
            )

            async for entity in self._generate_lists_with_items(
                site_id, site_name, site_breadcrumb, entity_count
            ):
                entity_count += 1
                yield entity

            self.logger.debug(f"Generating page entities for site: {site_name}")
            async for page_entity in self._generate_page_entities(site_id, site_name):
                entity_count += 1
                self.logger.debug(f"Yielding entity #{entity_count}: Page - {page_entity.title}")
                yield page_entity

            async for entity in self._generate_drives_with_items(
                site_id, site_name, site_breadcrumb, entity_count, files=files
            ):
                entity_count += 1
                yield entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== SHAREPOINT ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> None:
        """Validate credentials by pinging the root site endpoint."""
        await self._get(f"{self.GRAPH_BASE_URL}/sites/root")
