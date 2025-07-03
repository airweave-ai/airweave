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

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.google_drive import GoogleDriveDriveEntity, GoogleDriveFileEntity
from airweave.platform.sources._base import BaseSource


@source(
    name="Google Drive",
    short_name="google_drive",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="GoogleDriveAuthConfig",
    config_class="GoogleDriveConfig",
    labels=["File Storage"],
)
class GoogleDriveSource(BaseSource):
    """Google Drive source implementation (read-only).

    Retrieves and yields:
      - GoogleDriveDriveEntity objects, representing shared drives
      - GoogleDriveFileEntity objects, representing files in each shared drive
      - GoogleDriveFileEntity objects, representing files in the user's My Drive
    """

    def __init__(self):
        """Initialize the source and add a counter for testing."""
        super().__init__()
        # FOR TESTING: This counter will be used to simulate a token expiry.
        self._test_entity_counter = 0

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleDriveSource":
        """Create a new Google Drive source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token

        instance.exclude_patterns = config.get("exclude_patterns", [])

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
        """Make an authenticated GET request to the Google Drive API.

        This method now delegates to the base class's helper, which handles
        token refresh and retry logic automatically.
        """
        # FOR TESTING: Simulate a 401 unauthorized error after 20 entities have been processed.
        if self._test_entity_counter >= 20:
            self.logger.warning(
                f"TESTING: Simulating 401 Unauthorized. Counter is {self._test_entity_counter}."
            )
            # Set counter to a negative number to ensure this only triggers once per sync.
            self._test_entity_counter = -1

            # Build a fake response and raise an HTTPStatusError to trigger the refresh logic.
            request = client.build_request("GET", url, params=params)
            fake_response = httpx.Response(
                status_code=401,
                request=request,
                text='{"error": "Simulated token expiry for testing."}',
                headers={"Content-Type": "application/json"},
            )
            raise httpx.HTTPStatusError(
                "Simulated 401 Unauthorized for testing token refresh.",
                request=request,
                response=fake_response,
            )

        try:
            return await self._make_authenticated_request(
                lambda token: client.get(
                    url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30.0
                )
            )
        except httpx.ConnectTimeout:
            self.logger.error(f"Connection timeout accessing Google Drive API: {url}")
            raise
        except httpx.ReadTimeout:
            self.logger.error(f"Read timeout accessing Google Drive API: {url}")
            raise
        except httpx.HTTPError as e:
            # The base helper handles HTTPStatusError, so this catches other network issues.
            self.logger.error(f"HTTP error when accessing Google Drive API: {url}, {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in _get_with_auth for {url}: {str(e)}")
            raise

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
                self.logger.info(f"\nDrives: {drive_obj}\n")
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
                self.logger.info(f"\nfiles in {log_context}: {file_obj}\n")
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
        self.logger.info(f"\n{file_obj.get('mimeType', 'nothing')}\n")
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
            self.logger.info(
                f"Skipping file '{file_name}' (ID: {file_obj['id']}). "
                f"File is {'trashed' if trashed else 'not trashed'}. "
                f"Mime type: {file_obj.get('mimeType', 'unknown')}"
            )
            return None

        self.logger.info(f"\n{download_url}\n")
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
                # Check if file should be included based on exclusion patterns
                if not await self._should_include_file(client, file_obj):
                    continue  # Skip this file

                # Get file entity (might be None for trashed files)
                file_entity = self._build_file_entity(file_obj)

                # Skip if the entity was None (likely a trashed file)
                if not file_entity:
                    continue

                # Process the entity if it has a download URL
                if file_entity.download_url:
                    # The access_token parameter is removed. The base class's
                    # process_file_entity method now handles getting a valid token.
                    processed_entity = await self.process_file_entity(file_entity=file_entity)
                    yield processed_entity
                else:
                    # This should never happen now that we return None for files without URLs
                    self.logger.warning(f"No download URL available for {file_entity.name}")
            except Exception as e:
                error_context = f"in drive {drive_id}" if drive_id else "in MY DRIVE"
                self.logger.error(
                    f"\nFailed to process file {file_obj.get('name', 'unknown')} "
                    f"{error_context}: {str(e)}\n"
                )
                raise

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Wraps the original entity generator to inject test logic."""
        # This wrapper increments a counter for each entity yielded, allowing us to
        # simulate a token expiry after a specific number of entities.
        async for entity in self._original_generate_entities():
            # The counter is checked in _get_with_auth before the API call.
            yield entity
            if self._test_entity_counter >= 0:
                self._test_entity_counter += 1

    async def _original_generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Google Drive entities. (This was the original generate_entities).

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
                        self.logger.info("Stopping after first file entity for testing purposes")
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
                        self.logger.info("Stopping after first file entity for testing purposes")
                        return

    async def _get_file_path(self, client: httpx.AsyncClient, file_obj: Dict) -> str:
        """Get full path of file by recursively fetching parent folders."""
        path_parts = [file_obj.get("name", "")]
        file_id = file_obj.get("id", "unknown")

        self.logger.debug(f"Building path for file: {path_parts[0]} (ID: {file_id})")

        # Get parents from file object
        parents = file_obj.get("parents", [])
        if not parents:
            self.logger.debug(f"No parents found for file: {path_parts[0]}")
            return path_parts[0]

        # Start with the first parent
        current_parent_id = parents[0]
        self.logger.debug(f"Starting parent resolution with ID: {current_parent_id}")

        # Limit recursion depth to avoid potential infinite loops
        max_depth = 20
        depth = 0

        while current_parent_id and depth < max_depth:
            depth += 1
            try:
                # Get folder information
                folder_url = f"https://www.googleapis.com/drive/v3/files/{current_parent_id}"
                folder_params = {"fields": "id,name,parents,mimeType"}
                folder_data = await self._get_with_auth(client, folder_url, params=folder_params)

                # If this is the root folder or My Drive, stop recursion
                if folder_data.get("id") == "root" or not folder_data.get("parents"):
                    path_parts.insert(0, folder_data.get("name", "") or "My Drive")
                    break

                # Add folder name to path
                path_parts.insert(0, folder_data.get("name", ""))

                # Move to parent folder
                parents = folder_data.get("parents", [])
                current_parent_id = parents[0] if parents else None

            except Exception as e:
                self.logger.error(f"Error retrieving parent folder {current_parent_id}: {str(e)}")
                break

        # Build path string
        final_path = "/".join(path_parts)
        self.logger.debug(f"Final path for {file_id}: {final_path}")
        return final_path

    async def _should_include_file(self, client: httpx.AsyncClient, file_obj: Dict) -> bool:
        """Determine if a file should be included based on exclusion patterns."""
        file_name = file_obj.get("name", "unknown")

        # Get the full file path with async call
        file_path = await self._get_file_path(client, file_obj)

        # Log full path info for EVERY file - this makes debugging easier
        self.logger.info(
            f"FILE PATH: '{file_path}' (name: {file_name}, id: {file_obj.get('id', 'unknown')})"
        )

        # If no exclusion patterns, include everything
        if not self.exclude_patterns:
            self.logger.info(f"No exclusion patterns set, including file: {file_name}")
            return True

        # Check against each exclusion pattern
        for pattern in self.exclude_patterns:
            if self._path_matches_pattern(file_path, pattern):
                self.logger.info(
                    f"EXCLUDED: File '{file_name}' (path: {file_path}) matches "
                    f"exclusion pattern '{pattern}'"
                )
                return False

        self.logger.info(
            f"INCLUDED: File '{file_name}' (path: {file_path}) doesn't match any exclusion patterns"
        )
        return True

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern using glob-style matching."""
        import fnmatch

        match_result = fnmatch.fnmatch(path, pattern)
        self.logger.debug(
            f"Pattern match check: path '{path}' against pattern '{pattern}' -> {match_result}"
        )
        return match_result
