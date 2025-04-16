"""Google Drive source implementation.

Retrieves data from a user's Google Drive (read-only mode):
  - Shared drives (Drive objects)
  - Files within each shared drive
  - Files in the user's "My Drive" (non-shared, corpora=user)

Follows the same structure and pattern as other connector implementations
(e.g., Gmail, Asana, Todoist, HubSpot). The entity schemas are defined in
entities/google_drive.py.

References:
    https://developers.google.com/drive/api/v3/reference/drives (Shared drives)
    https://developers.google.com/drive/api/v3/reference/files  (Files)
"""

from typing import AsyncGenerator, Dict, Optional

import httpx

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.google_drive import GoogleDriveDriveEntity, GoogleDriveFileEntity
from airweave.platform.file_handling.file_manager import file_manager
from airweave.platform.sources._base import BaseSource


@source(
    "Google Drive",
    "google_drive",
    # i dont think it is with refresh (the config says something else)
    AuthType.oauth2_with_refresh,
    labels=["File Storage"],
)
class GoogleDriveSource(BaseSource):
    """Google Drive source implementation (read-only).

    Retrieves and yields:
      - GoogleDriveDriveEntity objects, representing shared drives
      - GoogleDriveFileEntity objects, representing files in each shared drive
      - GoogleDriveFileEntity objects, representing files in the user's My Drive
    """

    @classmethod
    async def create(cls, access_token: str) -> "GoogleDriveSource":
        """Create a new Google Drive source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to the Google Drive API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        resp = await client.get(url, headers=headers, params=params)
        logger.error(f"Request URL: {url}")
        resp.raise_for_status()
        return resp.json()

    async def _list_drives(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
        """List all shared drives (Drive objects) using pagination.

        GET https://www.googleapis.com/drive/v3/drives
        """
        url = "https://www.googleapis.com/drive/v3/drives"
        params = {"pageSize": 100}
        while url:
            data = await self._get_with_auth(client, url, params=params)
            drives = data.get("drives", [])
            for drive_obj in drives:
                logger.info(f"\nDrives: {drive_obj}\n")
                yield drive_obj

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break  # no more results
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/drives"  # keep the same base URL

    async def _generate_drive_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GoogleDriveDriveEntity objects for each shared drive."""
        async for drive_obj in self._list_drives(client):
            yield GoogleDriveDriveEntity(
                entity_id=drive_obj["id"],
                # No breadcrumbs for top-level drives in this connector
                breadcrumbs=[],
                drive_id=drive_obj["id"],
                name=drive_obj.get("name"),
                kind=drive_obj.get("kind"),
                color_rgb=drive_obj.get("colorRgb"),
                created_time=drive_obj.get("createdTime"),
                hidden=drive_obj.get("hidden", False),
                org_unit_id=drive_obj.get("orgUnitId"),
            )

    async def _list_files_in_drive(
        self, client: httpx.AsyncClient, drive_id: str
    ) -> AsyncGenerator[Dict, None]:
        """List files within a shared drive using pagination.

        GET https://www.googleapis.com/drive/v3/files
        ?driveId=<drive_id>&includeItemsFromAllDrives=true&supportsAllDrives=true&corpora=drive
        """
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "pageSize": 100,
            "driveId": drive_id,
            "corpora": "drive",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "fields": "nextPageToken, files(id, name, mimeType, description, starred, trashed, "
            "explicitlyTrashed, parents, shared, webViewLink, iconLink, createdTime, "
            "modifiedTime, size, md5Checksum, webContentLink)",
        }
        while url:
            data = await self._get_with_auth(client, url, params=params)
            for file_obj in data.get("files", []):
                logger.info(f"\nfiles in drive_id {drive_id}: {file_obj}\n")
                yield file_obj

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

    async def _list_files_in_my_drive(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict, None]:
        """List files in the user's My Drive (corpora=user) using pagination.

        GET https://www.googleapis.com/drive/v3/files
        ?corpora=user&includeItemsFromAllDrives=false&supportsAllDrives=true
        """
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "pageSize": 100,
            "corpora": "user",
            "includeItemsFromAllDrives": "false",
            "supportsAllDrives": "true",
            "fields": "nextPageToken, files(id, name, mimeType, description, starred, trashed, "
            "explicitlyTrashed, parents, shared, webViewLink, iconLink, createdTime, "
            "modifiedTime, size, md5Checksum, webContentLink)",
        }
        while url:
            data = await self._get_with_auth(client, url, params=params)
            for file_obj in data.get("files", []):
                logger.info(f"\nfiles in MY DRIVE: {file_obj}\n")
                yield file_obj

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

    def _build_file_entity(self, file_obj: Dict) -> GoogleDriveFileEntity:
        """Helper to build a GoogleDriveFileEntity from a file API response object."""
        # Create download URL based on file type
        download_url = None
        logger.info(f"\n{file_obj.get('mimeType', 'nothing')}\n")
        if file_obj.get("mimeType", "").startswith("application/vnd.google-apps."):
            # For Google native files, need export URL
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}/export?mimeType=application/pdf"
        elif not file_obj.get("trashed", False):
            # For regular files, use direct download or webContentLink
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}?alt=media"

        logger.info(f"\n{download_url}\n")
        return GoogleDriveFileEntity(
            entity_id=file_obj["id"],
            breadcrumbs=[],
            file_id=file_obj["id"],
            download_url=download_url,
            name=file_obj.get("name", "Untitled"),
            mime_type=file_obj.get("mimeType"),
            description=file_obj.get("description"),
            starred=file_obj.get("starred", False),
            trashed=file_obj.get("trashed", False),
            explicitly_trashed=file_obj.get("explicitlyTrashed", False),
            parents=file_obj.get("parents", []),
            owners=file_obj.get("owners", []),
            shared=file_obj.get("shared", False),
            web_view_link=file_obj.get("webViewLink"),
            icon_link=file_obj.get("iconLink"),
            created_time=file_obj.get("createdTime"),
            modified_time=file_obj.get("modifiedTime"),
            size=int(file_obj["size"]) if file_obj.get("size") else None,
            md5_checksum=file_obj.get("md5Checksum"),
        )

    async def _generate_file_entities_in_drive(
        self, client: httpx.AsyncClient, drive_id: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GoogleDriveFileEntity objects for each file in a shared drive."""
        async for file_obj in self._list_files_in_drive(client, drive_id):
            try:
                file_entity = self._build_file_entity(file_obj)
                if file_entity.download_url:
                    # Stream the file and process it
                    file_stream = file_manager.stream_file_from_url(
                        file_entity.download_url, access_token=self.access_token
                    )
                    processed_entity = await file_manager.handle_file_entity(
                        stream=file_stream, entity=file_entity
                    )
                    yield processed_entity
                else:
                    # Skip files without download URL
                    logger.warning(f"No download URL available for {file_entity.name}")
            except Exception as e:
                logger.error(
                    f"\nFailed to process file {file_obj.get('name', 'unknown')} "
                    f"in drive {drive_id}: {str(e)}\n"
                )
                raise

    async def _generate_file_entities_in_my_drive(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GoogleDriveFileEntity objects for each file in the user's My Drive."""
        async for file_obj in self._list_files_in_my_drive(client):
            try:
                file_entity = self._build_file_entity(file_obj)
                if file_entity.download_url:
                    file_stream = file_manager.stream_file_from_url(
                        file_entity.download_url, access_token=self.access_token
                    )
                    processed_entity = await file_manager.handle_file_entity(
                        stream=file_stream, entity=file_entity
                    )
                    yield processed_entity
                else:
                    logger.warning(f"No download URL available for {file_entity.name}")
            except Exception as e:
                logger.error(
                    f"\nFailed to process file {file_obj.get('name', 'unknown')} "
                    f"in MY DRIVE: {str(e)}\n"
                )
                raise

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Google Drive entities.

        Yields entities in the following order:
          - Shared drives (Drive objects)
          - Files in each shared drive
          - Files in My Drive (corpora=user)
        """
        async with httpx.AsyncClient() as client:
            # For testing: count file entities yielded
            file_entity_count = 0
            # Testing flag - set to True to stop after first file entity
            stop_after_first_file = False

            # 1) Generate entities for shared drives
            async for drive_entity in self._generate_drive_entities(client):
                yield drive_entity

            # 2) For each shared drive, yield file entities
            #    We'll re-list drives in memory so we don't have to fetch them again
            drive_ids = []
            async for drive_obj in self._list_drives(client):
                drive_ids.append(drive_obj["id"])

            for drive_id in drive_ids:
                async for file_entity in self._generate_file_entities_in_drive(client, drive_id):
                    yield file_entity
                    file_entity_count += 1
                    if stop_after_first_file and file_entity_count >= 4:
                        logger.info("Stopping after first file entity for testing purposes")
                        return

            # 3) Finally, yield file entities for My Drive (corpora=user)
            # Only reach here if we didn't find any files in shared drives
            if not (stop_after_first_file and file_entity_count >= 4):
                async for mydrive_file_entity in self._generate_file_entities_in_my_drive(client):
                    yield mydrive_file_entity
                    file_entity_count += 1
                    if stop_after_first_file and file_entity_count >= 4:
                        logger.info("Stopping after first file entity for testing purposes")
                        return
