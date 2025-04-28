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
from airweave.platform.sources._base import BaseSource


@source(
    "Google Drive",
    "google_drive",
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

    async def _list_files(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
    ) -> AsyncGenerator[Dict, None]:
        """Generic method to list files with configurable parameters.

        Args:
            client: HTTP client to use for requests
            corpora: Google Drive API corpora parameter ("drive" or "user")
            include_all_drives: Whether to include items from all drives
            drive_id: ID of the shared drive to list files from (only for corpora="drive")
            context: Context string for logging
        """
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "pageSize": 100,
            "corpora": corpora,
            "includeItemsFromAllDrives": str(include_all_drives).lower(),
            "supportsAllDrives": "true",
            "q": "mimeType != 'application/vnd.google-apps.folder'",
            "fields": "nextPageToken, files(id, name, mimeType, description, starred, trashed, "
            "explicitlyTrashed, parents, shared, webViewLink, iconLink, createdTime, "
            "modifiedTime, size, md5Checksum, webContentLink)",
        }

        if drive_id:
            params["driveId"] = drive_id

        while url:
            data = await self._get_with_auth(client, url, params=params)
            for file_obj in data.get("files", []):
                log_context = f"drive_id {drive_id}" if drive_id else "MY DRIVE"
                logger.info(f"\nfiles in {log_context}: {file_obj}\n")
                yield file_obj

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

    def _build_file_entity(self, file_obj: Dict) -> Optional[GoogleDriveFileEntity]:
        """Helper to build a GoogleDriveFileEntity from a file API response object.

        Returns None for files that should be skipped (e.g., trashed files).
        """
        # Create download URL based on file type
        download_url = None
        logger.info(f"\n{file_obj.get('mimeType', 'nothing')}\n")
        if file_obj.get("mimeType", "").startswith("application/vnd.google-apps."):
            # For Google native files, need export URL
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}/export?mimeType=application/pdf"
        elif not file_obj.get("trashed", False):
            # For regular files, use direct download or webContentLink
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}?alt=media"

        # Return None if download_url is None (typically for trashed files)
        if not download_url:
            file_name = file_obj.get("name", "Untitled")
            trashed = file_obj.get("trashed", False)
            logger.info(
                f"Skipping file '{file_name}' (ID: {file_obj['id']}). "
                f"File is {'trashed' if trashed else 'not trashed'}. "
                f"Mime type: {file_obj.get('mimeType', 'unknown')}"
            )
            return None

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

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file entities from a file listing."""
        async for file_obj in self._list_files(
            client, corpora, include_all_drives, drive_id, context
        ):
            try:
                # Get file entity (might be None for trashed files)
                file_entity = self._build_file_entity(file_obj)

                # Skip if the entity was None (likely a trashed file)
                if not file_entity:
                    continue

                # Process the entity if it has a download URL
                if file_entity.download_url:
                    processed_entity = await self.process_file_entity(
                        file_entity=file_entity, access_token=self.access_token
                    )

                    yield processed_entity
                else:
                    # This should never happen now that we return None for files without URLs
                    logger.warning(f"No download URL available for {file_entity.name}")
            except Exception as e:
                error_context = f"in drive {drive_id}" if drive_id else "in MY DRIVE"
                logger.error(
                    f"\nFailed to process file {file_obj.get('name', 'unknown')} "
                    f"{error_context}: {str(e)}\n"
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
                async for file_entity in self._generate_file_entities(
                    client,
                    corpora="drive",
                    include_all_drives=True,
                    drive_id=drive_id,
                    context=f"drive {drive_id}",
                ):
                    yield file_entity
                    file_entity_count += 1
                    if stop_after_first_file and file_entity_count >= 4:
                        logger.info("Stopping after first file entity for testing purposes")
                        return

            # 3) Finally, yield file entities for My Drive (corpora=user)
            # Only reach here if we didn't find any files in shared drives
            if not (stop_after_first_file and file_entity_count >= 4):
                async for mydrive_file_entity in self._generate_file_entities(
                    client, corpora="user", include_all_drives=False, context="MY DRIVE"
                ):
                    yield mydrive_file_entity
                    file_entity_count += 1
                    if stop_after_first_file and file_entity_count >= 4:
                        logger.info("Stopping after first file entity for testing purposes")
                        return
