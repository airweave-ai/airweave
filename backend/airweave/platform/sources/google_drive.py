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

from airweave.core.exceptions import TokenRefreshError
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
    """Google Drive source connector integrates with the Google Drive API to extract files.

    Supports both personal Google Drive (My Drive) and shared drives.

    It supports downloading and processing files
    while maintaining proper organization and access permissions.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleDriveSource":
        """Create a new Google Drive source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token

        # Tolerate None config and set defaults
        config = config or {}

        instance.exclude_patterns = config.get("exclude_patterns", [])

        # Performance option to skip expensive path lookups
        instance.skip_file_paths = config.get("skip_file_paths", True)

        # Initialize cache for parent folder lookups
        instance._parent_folder_cache = {}

        # Configurable concurrency for file processing
        # (used by BaseSource.process_entities_concurrent)
        # Default batch_size = 1 as requested
        instance.batch_size = int(config.get("batch_size", 30))

        # Toggle: default to sequential flow (False) as requested
        instance.batch_generation = bool(config.get("batch_generation", True))

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
        """Make an authenticated GET request to the Google Drive API with retry logic.

        This method now uses the token manager for authentication and handles
        401 errors by refreshing the token and retrying.
        """
        # Get a valid access token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # Add a longer timeout (30 seconds)
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)

            # Handle 401 Unauthorized - token might have expired
            if resp.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry the request with the new token
                        resp = await client.get(url, headers=headers, params=params, timeout=30.0)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        raise httpx.HTTPStatusError(
                            "Authentication failed and token refresh was unsuccessful",
                            request=resp.request,
                            response=resp,
                        ) from e
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    resp.raise_for_status()

            # Raise for other HTTP errors
            resp.raise_for_status()
            return resp.json()

        except httpx.ConnectTimeout:
            self.logger.error(f"Connection timeout accessing Google Drive API: {url}")
            raise
        except httpx.ReadTimeout:
            self.logger.error(f"Read timeout accessing Google Drive API: {url}")
            raise
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"HTTP status error {e.response.status_code} from Google Drive API: {url}"
            )
            raise
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error when accessing Google Drive API: {url}, {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Google Drive API: {url}, {str(e)}")
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

        total_files_from_api = 0  # Track total files returned by API
        page_count = 0

        while url:
            try:
                data = await self._get_with_auth(client, url, params=params)
            except Exception as e:
                self.logger.error(f"Error fetching files: {str(e)}")
                break

            files_in_page = data.get("files", [])
            page_count += 1
            files_count = len(files_in_page)
            total_files_from_api += files_count

            # Log how many files the API returned in this page
            self.logger.info(
                f"\n\nGoogle Drive API returned {files_count} files in page {page_count} "
                f"({context})\n\n"
            )

            for file_obj in files_in_page:
                yield file_obj

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

        # Log total count when done
        self.logger.info(
            f"\n\nGoogle Drive API returned {total_files_from_api} total files across "
            f"{page_count} pages ({context})\n\n"
        )

    def _get_export_format_and_extension(self, mime_type: str) -> tuple[str, str]:
        """Get the appropriate export MIME type and file extension for Google native files.

        Returns:
            tuple: (export_mime_type, file_extension)
        """
        # Mapping of Google MIME types to their corresponding export formats
        google_export_map = {
            "application/vnd.google-apps.document": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
            ),
            "application/vnd.google-apps.spreadsheet": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
            ),
            "application/vnd.google-apps.presentation": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".pptx",
            ),
        }

        # Return the specific format if available, otherwise fallback to PDF
        return google_export_map.get(mime_type, ("application/pdf", ".pdf"))

    def _build_file_entity(self, file_obj: Dict) -> Optional[GoogleDriveFileEntity]:
        """Helper to build a GoogleDriveFileEntity from a file API response object.

        Returns None for files that should be skipped (e.g., trashed files).
        """
        # Create download URL based on file type
        download_url = None

        # Get the original file name
        file_name = file_obj.get("name", "Untitled")

        if file_obj.get("mimeType", "").startswith("application/vnd.google-apps."):
            # For Google native files, get the appropriate export format
            export_mime_type, file_extension = self._get_export_format_and_extension(
                file_obj.get("mimeType", "")
            )

            # Create export URL with the appropriate MIME type
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}/export?mimeType={export_mime_type}"

            # Add the appropriate extension if it's not already there
            if not file_name.lower().endswith(file_extension):
                file_name = f"{file_name}{file_extension}"

        elif not file_obj.get("trashed", False):
            # For regular files, use direct download or webContentLink
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_obj['id']}?alt=media"

        # Return None if download_url is None (typically for trashed files)
        if not download_url:
            return None

        return GoogleDriveFileEntity(
            entity_id=file_obj["id"],
            breadcrumbs=[],
            file_id=file_obj["id"],
            download_url=download_url,
            name=file_name,  # Use the modified name with extension
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

    async def _process_file_batch(
        self, client: httpx.AsyncClient, file_obj: Dict
    ) -> Optional[ChunkEntity]:
        """Process a single file for batch generation."""
        try:
            # Check if file should be included based on exclusion patterns
            try:
                should_include = await self._should_include_file(client, file_obj)
            except Exception as e:
                self.logger.error(f"Error checking if file should be included: {str(e)}")
                # Skip this file if we can't check inclusion
                return None

            if not should_include:
                return None  # Skip this file

            # Get file entity (might be None for trashed files)
            file_entity = self._build_file_entity(file_obj)

            # Skip if the entity was None (likely a trashed file)
            if not file_entity:
                return None

            # Process the entity if it has a download URL
            if file_entity.download_url:
                # Note: process_file_entity now uses the token manager automatically
                processed_entity = await self.process_file_entity(file_entity=file_entity)
                print(processed_entity)

                # Yield the entity even if skipped - the entity processor will handle it
                if processed_entity:
                    return processed_entity
        except Exception as e:
            self.logger.error(f"Failed to process file {file_obj.get('name', 'unknown')}: {str(e)}")
            # Continue processing other files instead of raising
            return None
        return None

    async def _process_file_sequential(
        self, client: httpx.AsyncClient, file_obj: Dict
    ) -> Optional[ChunkEntity]:
        """Process a single file for sequential generation."""
        try:
            # Check if file should be included based on exclusion patterns
            try:
                should_include = await self._should_include_file(client, file_obj)
            except Exception as e:
                self.logger.error(f"Error checking if file should be included: {str(e)}")
                # Skip this file if we can't check inclusion
                return None

            if not should_include:
                return None  # Skip this file

            # Get file entity (might be None for trashed files)
            file_entity = self._build_file_entity(file_obj)

            # Skip if the entity was None (likely a trashed file)
            if not file_entity:
                return None

            # Process the entity if it has a download URL
            if file_entity.download_url:
                # Note: process_file_entity now uses the token manager automatically
                processed_entity = await self.process_file_entity(file_entity=file_entity)
                print(processed_entity)

                # Return the entity even if skipped - the entity processor will handle it
                if processed_entity:
                    return processed_entity
        except Exception as e:
            self.logger.error(f"Failed to process file {file_obj.get('name', 'unknown')}: {str(e)}")
            # Continue processing other files instead of raising
            return None
        return None

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file entities from a file listing."""
        try:
            if getattr(self, "batch_generation", False):
                # ===== Concurrent flow (A) =====
                try:
                    # Use BaseSource.process_entities_concurrent for bounded concurrency
                    async def _worker(file_obj: Dict):
                        return await self._process_file_batch(client, file_obj)

                    async for processed in self.process_entities_concurrent(
                        items=self._list_files(
                            client, corpora, include_all_drives, drive_id, context
                        ),
                        worker=_worker,
                        batch_size=getattr(self, "batch_size", 1),
                        preserve_order=False,
                    ):
                        yield processed

                except Exception as e:
                    self.logger.error(f"Critical exception in _generate_file_entities: {str(e)}")
                    # Don't re-raise - let the generator complete
            else:
                # ===== Sequential flow (B) =====
                try:
                    async for file_obj in self._list_files(
                        client, corpora, include_all_drives, drive_id, context
                    ):
                        processed_entity = await self._process_file_sequential(client, file_obj)
                        if processed_entity:
                            yield processed_entity

                except Exception as e:
                    self.logger.error(f"Critical exception in _generate_file_entities: {str(e)}")
                    # Don't re-raise - let the generator complete

        except Exception as e:
            self.logger.error(f"Critical exception in _generate_file_entities: {str(e)}")
            # Don't re-raise - let the generator complete

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Google Drive entities.

        Yields entities in the following order:
          - Shared drives (Drive objects)
          - Files in each shared drive
          - Files in My Drive (corpora=user)
        """
        try:
            async with httpx.AsyncClient() as client:
                try:
                    # 1) Generate entities for shared drives
                    async for drive_entity in self._generate_drive_entities(client):
                        yield drive_entity

                    # 2) For each shared drive, yield file entities
                    #    We'll re-list drives in memory so we don't have to fetch them again
                    drive_ids = []
                    async for drive_obj in self._list_drives(client):
                        drive_ids.append(drive_obj["id"])

                    for drive_id in drive_ids:
                        try:
                            async for file_entity in self._generate_file_entities(
                                client,
                                corpora="drive",
                                include_all_drives=True,
                                drive_id=drive_id,
                                context=f"drive {drive_id}",
                            ):
                                yield file_entity
                        except Exception as e:
                            self.logger.error(f"Error processing shared drive {drive_id}: {str(e)}")
                            # Continue with next drive
                            continue
                except Exception as e:
                    self.logger.error(f"Error in shared drives phase: {str(e)}")
                    # Continue to My Drive processing

                # 3) Finally, yield file entities for My Drive (corpora=user)
                try:
                    async for mydrive_file_entity in self._generate_file_entities(
                        client, corpora="user", include_all_drives=False, context="MY DRIVE"
                    ):
                        yield mydrive_file_entity
                except Exception as e:
                    self.logger.error(f"Error processing My Drive files: {str(e)}")

        except Exception as e:
            self.logger.error(f"Critical error in generate_entities: {str(e)}")

    async def _get_file_path(self, client: httpx.AsyncClient, file_obj: Dict) -> str:
        """Get full path of file by recursively fetching parent folders."""
        path_parts = [file_obj.get("name", "")]

        # Get parents from file object
        parents = file_obj.get("parents", [])
        if not parents:
            return path_parts[0]

        # Start with the first parent
        current_parent_id = parents[0]

        # Limit recursion depth to avoid potential infinite loops
        max_depth = 20
        depth = 0

        while current_parent_id and depth < max_depth:
            depth += 1

            # Check cache first
            if (
                hasattr(self, "_parent_folder_cache")
                and current_parent_id in self._parent_folder_cache
            ):
                cached_data = self._parent_folder_cache[current_parent_id]
                path_parts.insert(0, cached_data["name"])
                current_parent_id = cached_data["parent_id"]
                continue

            try:
                # Get folder information
                folder_url = f"https://www.googleapis.com/drive/v3/files/{current_parent_id}"
                folder_params = {"fields": "id,name,parents,mimeType"}

                folder_data = await self._get_with_auth(client, folder_url, params=folder_params)

                # Cache the folder data
                if hasattr(self, "_parent_folder_cache"):
                    parent_list = folder_data.get("parents", [])
                    self._parent_folder_cache[current_parent_id] = {
                        "name": folder_data.get("name", "") or "My Drive",
                        "parent_id": parent_list[0] if parent_list else None,
                    }

                # If this is the root folder or My Drive, stop recursion
                if folder_data.get("id") == "root" or not folder_data.get("parents"):
                    path_parts.insert(0, folder_data.get("name", "") or "My Drive")
                    break

                # Add folder name to path
                folder_name = folder_data.get("name", "")
                path_parts.insert(0, folder_name)

                # Move to parent folder
                parents = folder_data.get("parents", [])
                current_parent_id = parents[0] if parents else None

            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"HTTP error retrieving parent folder {current_parent_id}: "
                    f"Status {e.response.status_code}"
                )
                # Stop path building on error but return what we have
                break
            except Exception as e:
                self.logger.error(f"Error retrieving parent folder {current_parent_id}: {str(e)}")
                # Stop path building on error but return what we have
                break

        # Build path string
        return "/".join(path_parts)

    async def _should_include_file(self, client: httpx.AsyncClient, file_obj: Dict) -> bool:
        """Determine if a file should be included based on exclusion patterns."""
        file_name = file_obj.get("name", "unknown")

        # If skip_file_paths is enabled, skip path-based filtering
        if hasattr(self, "skip_file_paths") and self.skip_file_paths:
            # If no exclusion patterns or patterns don't apply without paths, include everything
            if not self.exclude_patterns:
                return True
            # Only check filename patterns
            for pattern in self.exclude_patterns:
                if self._path_matches_pattern(file_name, pattern):
                    return False
            return True

        # Get the full file path with async call
        file_path = await self._get_file_path(client, file_obj)

        # If no exclusion patterns, include everything
        if not self.exclude_patterns:
            return True

        # Check against each exclusion pattern
        for pattern in self.exclude_patterns:
            if self._path_matches_pattern(file_path, pattern):
                return False

        return True

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern using glob-style matching."""
        import fnmatch

        return fnmatch.fnmatch(path, pattern)
