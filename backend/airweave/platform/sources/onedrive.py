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


from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, AsyncGenerator, Dict, List, Optional

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
from airweave.platform.configs.config import OneDriveConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.onedrive import OneDriveDriveEntity, OneDriveDriveItemEntity
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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: OneDriveConfig,
    ) -> "OneDriveSource":
        """Create a new OneDrive source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated GET request to Microsoft Graph API with retry logic."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
            )
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _get_available_drives(self) -> List[Dict]:
        """Get all available drives for the user.

        This endpoint works better for accounts without SPO license.
        """
        try:
            url = "https://graph.microsoft.com/v1.0/me/drives"
            data = await self._get(url)
            return data.get("value", [])
        except SourceAuthError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                self.logger.warning("Cannot access /me/drives, will try app folder access")
                return []
            raise

    async def _get_user_drive(self) -> Optional[Dict]:
        """Get the user's default OneDrive with fallback handling.

        Tries multiple approaches based on available permissions.
        """
        try:
            url = "https://graph.microsoft.com/v1.0/me/drive"
            return await self._get(url)
        except SourceAuthError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                error_body = e.response.json() if hasattr(e.response, "json") else {}
                if "SPO license" in str(error_body):
                    self.logger.warning(
                        "Tenant does not have SPO license, trying alternative endpoints"
                    )
                    drives = await self._get_available_drives()
                    if drives:
                        self.logger.debug(f"Found {len(drives)} drives via /me/drives")
                        return drives[0]
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

    async def _generate_drive_entity(self) -> AsyncGenerator[OneDriveDriveEntity, None]:
        """Generate OneDriveDriveEntity for the user's drive(s)."""
        drive_obj = await self._get_user_drive()

        if not drive_obj:
            drive_obj = await self._create_app_folder_drive()
            self.logger.debug("Using app folder access mode")

        self.logger.debug(f"Drive: {drive_obj}")

        drive_name = drive_obj.get("name") or drive_obj.get("driveType", "OneDrive")

        yield OneDriveDriveEntity(
            breadcrumbs=[],
            id=drive_obj["id"],
            name=drive_name,
            created_at=drive_obj.get("createdDateTime"),
            updated_at=drive_obj.get("lastModifiedDateTime"),
            drive_type=drive_obj.get("driveType"),
            owner=drive_obj.get("owner"),
            quota=drive_obj.get("quota"),
            web_url_override=drive_obj.get("webUrl"),
        )

    async def _list_drive_items(
        self,
        drive_id: str,
        folder_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """List items in a drive using pagination.

        Args:
            drive_id: ID of the drive
            folder_id: ID of specific folder, or None for root
        """
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
                "file,folder,parentReference,webUrl,eTag,cTag"
            ),
        }

        try:
            while url:
                data = await self._get(url, params=params)

                for item in data.get("value", []):
                    self.logger.debug(f"DriveItem: {item}")
                    yield item

                url = data.get("@odata.nextLink")
                if url:
                    params = None
        except SourceAuthError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.logger.warning(f"Access denied to folder {folder_id}, skipping")
                return
            elif e.response.status_code == 404:
                self.logger.warning(f"Folder {folder_id} not found, skipping")
                return
            else:
                raise

    def _get_download_url(self, drive_id: str, item_id: str) -> Optional[str]:
        """Get the download URL for a specific file item.

        Returns a Graph API content endpoint URL that can be used with the access token.
        """
        return f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"

    async def _list_all_drive_items_recursively(
        self,
        drive_id: str,
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
                    yield item

                    if "folder" in item and len(folder_queue) < 100:
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
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate OneDriveDriveItemEntity objects for files in the drive."""
        file_count = 0
        async for item in self._list_all_drive_items_recursively(drive_id):
            try:
                if "folder" in item:
                    continue

                download_url = self._get_download_url(drive_id, item["id"])

                file_entity = OneDriveDriveItemEntity.from_api(
                    item, drive_name=drive_name, drive_id=drive_id, download_url=download_url
                )

                if not file_entity:
                    continue

                # Skip download if content + metadata unchanged
                lookup = getattr(self, "_source_hash_lookup", None)
                if lookup and lookup.should_skip_download(file_entity):
                    self.logger.debug(
                        f"Source-hash match, skipping download: {file_entity.name}"
                    )
                    file_count += 1
                    yield file_entity
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
                else:
                    yield file_entity

            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to process item {item.get('name', 'unknown')}: {e}")
                continue

        self.logger.debug(f"Total files processed: {file_count}")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all OneDrive entities.

        Yields entities in the following order:
          - OneDriveDriveEntity for the user's drive
          - OneDriveDriveItemEntity for each file in the drive
        """
        self._source_hash_lookup = source_hash_lookup
        drive_entity = None
        async for drive in self._generate_drive_entity():
            yield drive
            drive_entity = drive
            break

        if not drive_entity:
            self.logger.warning("No drive found for user")
            return

        drive_id = drive_entity.id
        drive_name = drive_entity.name or drive_entity.drive_type or "OneDrive"

        self.logger.debug(f"Starting to process files from drive: {drive_id} ({drive_name})")

        async for file_entity in self._generate_drive_item_entities(
            drive_id, drive_name, files=files
        ):
            yield file_entity

    async def validate(self) -> None:
        """Validate OneDrive credentials with drive access fallback."""
        await self._get("https://graph.microsoft.com/v1.0/me/drive")
