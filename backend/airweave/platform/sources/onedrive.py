"""OneDrive source implementation using Microsoft Graph API.

Retrieves data from a user's OneDrive, including:
 - Drive information (OneDriveDriveEntity objects)
 - DriveItems (OneDriveDriveItemEntity objects) for files and folders

This handles different OneDrive scenarios:
 - Personal OneDrive (with SPO license)
 - OneDrive without SPO license (app folder only)
 - Business OneDrive

Reference (Microsoft Graph API):
  https://learn.microsoft.com/en-us/graph/api/drive-get?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0
"""

from collections import deque
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import OneDriveConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.onedrive import OneDriveDriveEntity, OneDriveDriveItemEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="OneDrive",
    short_name="onedrive",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class=OneDriveConfig,
    labels=["File Storage"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class OneDriveSource(BaseSource):
    """OneDrive source connector integrates with the Microsoft Graph API to extract files.

    Supports OneDrive personal and business accounts.

    It supports various OneDrive scenarios including
    personal drives, business drives, and app folder access with intelligent fallback handling.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "OneDriveSource":
        """Create a new OneDrive source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to Microsoft Graph API with retry logic."""
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)

            # Handle 401 errors by refreshing token and retrying
            if resp.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = await client.get(url, headers=headers, params=params, timeout=30.0)

            self.logger.debug(f"Request URL: {url}")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectTimeout:
            self.logger.error(f"Connection timeout accessing Microsoft Graph API: {url}")
            raise
        except httpx.ReadTimeout:
            self.logger.error(f"Read timeout accessing Microsoft Graph API: {url}")
            raise
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"HTTP status error {e.response.status_code} from Microsoft Graph API: {url}"
            )
            # Log the response body for debugging
            try:
                error_body = e.response.json()
                self.logger.error(f"Error response body: {error_body}")
            except Exception:  # Catch specific exception instead of bare except
                self.logger.error(f"Error response text: {e.response.text}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Microsoft Graph API: {url}, {str(e)}")
            raise

    async def _get_available_drives(self, client: httpx.AsyncClient) -> List[Dict]:
        """Get all available drives for the user.

        This endpoint works better for accounts without SPO license.
        """
        try:
            url = "https://graph.microsoft.com/v1.0/me/drives"
            data = await self._get_with_auth(client, url)
            return data.get("value", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                self.logger.warning("Cannot access /me/drives, will try app folder access")
                return []
            raise

    async def _get_user_drive(self, client: httpx.AsyncClient) -> Optional[Dict]:
        """Get the user's default OneDrive with fallback handling.

        Tries multiple approaches based on available permissions.
        """
        # First try to get the default drive
        try:
            url = "https://graph.microsoft.com/v1.0/me/drive"
            return await self._get_with_auth(client, url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                error_body = e.response.json() if hasattr(e.response, "json") else {}
                if "SPO license" in str(error_body):
                    self.logger.warning(
                        "Tenant does not have SPO license, trying alternative endpoints"
                    )
                    # Try to get drives list instead
                    drives = await self._get_available_drives(client)
                    if drives:
                        self.logger.debug(f"Found {len(drives)} drives via /me/drives")
                        return drives[0]  # Return first available drive
                    else:
                        self.logger.debug("No drives found, will create virtual app folder drive")
                        return None
            raise

    async def _create_app_folder_drive(self) -> Dict:
        """Create a virtual drive object for app folder access.

        When full OneDrive access isn't available, we can still access app-specific folders.
        """
        return {
            "id": "appfolder",
            "name": "OneDrive App Folder",
            "driveType": "personal",
            "owner": {"user": {"displayName": "Current User"}},
            "quota": None,
            "createdDateTime": None,
            "lastModifiedDateTime": None,
        }

    async def _generate_drive_entity(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[OneDriveDriveEntity, None]:
        """Generate OneDriveDriveEntity for the user's drive(s)."""
        drive_obj = await self._get_user_drive(client)

        if not drive_obj:
            # Fallback to app folder if no drive is accessible
            drive_obj = await self._create_app_folder_drive()
            self.logger.debug("Using app folder access mode")

        self.logger.debug(f"Drive: {drive_obj}")

        # Get drive name from API or use drive_type as fallback
        drive_name = drive_obj.get("name") or drive_obj.get("driveType", "OneDrive")

        yield OneDriveDriveEntity(
            breadcrumbs=[],
            id=drive_obj["id"],
            name=drive_name,
            created_at=drive_obj.get("createdDateTime"),
            updated_at=drive_obj.get("lastModifiedDateTime"),
            # API fields
            drive_type=drive_obj.get("driveType"),
            owner=drive_obj.get("owner"),
            quota=drive_obj.get("quota"),
            web_url_override=drive_obj.get("webUrl"),
        )

    async def _list_drive_items(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        folder_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """List items in a drive using pagination.

        Args:
            client: HTTP client
            drive_id: ID of the drive
            folder_id: ID of specific folder, or None for root
        """
        # Handle app folder access
        if drive_id == "appfolder":
            url = "https://graph.microsoft.com/v1.0/me/drive/special/approot/children"
        elif folder_id:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"

        params = {
            "$top": 100,
            "$select": (
                "id,name,size,createdDateTime,lastModifiedDateTime,"
                "file,folder,parentReference,webUrl"
            ),
        }

        try:
            while url:
                data = await self._get_with_auth(client, url, params=params)

                for item in data.get("value", []):
                    self.logger.debug(f"DriveItem: {item}")
                    yield item

                # Handle pagination using @odata.nextLink
                url = data.get("@odata.nextLink")
                if url:
                    params = None  # nextLink already includes parameters
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.logger.warning(f"Access denied to folder {folder_id}, skipping")
                return
            elif e.response.status_code == 404:
                self.logger.warning(f"Folder {folder_id} not found, skipping")
                return
            else:
                raise

    async def _get_download_url(
        self, client: httpx.AsyncClient, drive_id: str, item_id: str
    ) -> Optional[str]:
        """Get the download URL for a specific file item.

        Returns a Graph API content endpoint URL that can be used with the access token.
        """
        try:
            # Use the Graph API /content endpoint instead of SharePoint download URLs
            # This works with Files.Read.All permission without needing Sites.Read.All
            return f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
        except Exception as e:
            self.logger.error(f"Failed to get download URL for item {item_id}: {e}")
            return None

    async def _list_all_drive_items_recursively(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
    ) -> AsyncGenerator[Dict, None]:
        """Recursively list all items in a drive using BFS approach."""
        # Queue of folder IDs to process (None = root folder)
        folder_queue = deque([None])
        processed_folders = set()  # Avoid infinite loops

        while folder_queue:
            current_folder_id = folder_queue.popleft()

            # Skip if we've already processed this folder
            if current_folder_id in processed_folders:
                continue
            processed_folders.add(current_folder_id)

            try:
                async for item in self._list_drive_items(client, drive_id, current_folder_id):
                    yield item

                    # If this item is a folder, add it to the queue for processing
                    if "folder" in item and len(folder_queue) < 100:  # Limit queue size
                        folder_queue.append(item["id"])
            except Exception as e:
                self.logger.error(f"Error processing folder {current_folder_id}: {e}")
                continue

    def _build_file_entity(
        self, item: Dict, drive_name: str, drive_id: str, download_url: Optional[str] = None
    ) -> Optional[OneDriveDriveItemEntity]:
        """Build a OneDriveDriveItemEntity from a Graph API DriveItem response.

        Returns None for items that should be skipped.
        """
        # Skip if this is a folder without downloadable content
        if "folder" in item:
            self.logger.debug(f"Skipping folder: {item.get('name', 'Untitled')}")
            return None

        # Skip if no download URL provided
        if not download_url:
            self.logger.warning(f"No download URL for file: {item.get('name', 'Untitled')}")
            return None

        # Create drive breadcrumb
        drive_breadcrumb = Breadcrumb(
            entity_id=drive_id,
            name=drive_name,
            entity_type="OneDriveDriveEntity",
        )

        # Extract file information
        file_info = item.get("file", {})
        parent_ref = item.get("parentReference", {})
        mime_type = file_info.get("mimeType") or "application/octet-stream"
        size = item.get("size", 0)

        # Determine file type from mime_type
        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            import os

            ext = os.path.splitext(item.get("name", ""))[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        entity = OneDriveDriveItemEntity(
            id=item["id"],
            breadcrumbs=[drive_breadcrumb],
            name=item.get("name"),
            created_at=item.get("createdDateTime"),
            updated_at=item.get("lastModifiedDateTime"),
            url=download_url,
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,  # Will be set after download
            description=None,  # Not provided in basic listing
            etag=item.get("eTag"),
            ctag=item.get("cTag"),
            web_url_override=item.get("webUrl"),
            file=file_info,
            folder=item.get("folder"),
            parent_reference=parent_ref,
        )

        return entity

    async def _generate_drive_item_entities(
        self, client: httpx.AsyncClient, drive_id: str, drive_name: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate OneDriveDriveItemEntity objects for files in the drive."""
        file_count = 0
        async for item in self._list_all_drive_items_recursively(client, drive_id):
            try:
                # Skip folders early
                if "folder" in item:
                    continue

                # Fetch the individual item to get download URL
                download_url = await self._get_download_url(client, drive_id, item["id"])

                # Build the entity with the download URL
                file_entity = self._build_file_entity(item, drive_name, drive_id, download_url)

                if not file_entity:
                    continue

                # Download the file using file downloader
                try:
                    await self.file_downloader.download_from_url(
                        entity=file_entity,
                        http_client_factory=self.http_client,
                        access_token_provider=self.get_access_token,
                        logger=self.logger,
                    )

                    # Verify download succeeded
                    if not file_entity.local_path:
                        raise ValueError(
                            f"Download failed - no local path set for {file_entity.name}"
                        )

                    file_count += 1
                    self.logger.debug(f"Processed file {file_count}: {file_entity.name}")
                    yield file_entity

                except FileSkippedException as e:
                    # File intentionally skipped (unsupported type, too large, etc.) - not an error
                    self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                    continue

                except Exception as e:
                    self.logger.error(f"Failed to download file {file_entity.name}: {e}")
                    # Continue with other files
                    continue

            except Exception as e:
                self.logger.error(f"Failed to process item {item.get('name', 'unknown')}: {str(e)}")
                # Continue processing other items
                continue

        self.logger.debug(f"Total files processed: {file_count}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all OneDrive entities.

        Yields entities in the following order:
          - OneDriveDriveEntity for the user's drive
          - OneDriveDriveItemEntity for each file in the drive
        """
        async with self.http_client() as client:
            # 1) Generate drive entity
            drive_entity = None
            async for drive in self._generate_drive_entity(client):
                yield drive
                drive_entity = drive
                break  # Only one drive for personal OneDrive

            if not drive_entity:
                self.logger.error("No drive found for user")
                return

            # 2) Generate file entities for the drive
            drive_id = drive_entity.id
            # Use the human-friendly drive name for breadcrumbs; fall back to drive_type/name.
            drive_name = drive_entity.name or drive_entity.drive_type or "OneDrive"

            self.logger.debug(f"Starting to process files from drive: {drive_id} ({drive_name})")

            async for file_entity in self._generate_drive_item_entities(
                client, drive_id, drive_name
            ):
                yield file_entity

    async def validate(self) -> bool:
        """Verify OneDrive OAuth2 token and access with sensible fallbacks.

        Tries default drive (/me/drive), then list drives (/me/drives),
        then app-folder-only access (/me/drive/special/approot).
        """
        headers = {"Accept": "application/json"}

        # 1) Default OneDrive (most common)
        ok = await self._validate_oauth2(
            ping_url="https://graph.microsoft.com/v1.0/me/drive",
            headers=headers,
            timeout=10.0,
        )
        if ok:
            return True

        # 2) Accounts without SPO default drive but with accessible drives list
        ok = await self._validate_oauth2(
            ping_url="https://graph.microsoft.com/v1.0/me/drives?$top=1",
            headers=headers,
            timeout=10.0,
        )
        if ok:
            return True

        # 3) App-folder-only scenario
        return await self._validate_oauth2(
            ping_url="https://graph.microsoft.com/v1.0/me/drive/special/approot",
            headers=headers,
            timeout=10.0,
        )
