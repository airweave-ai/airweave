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

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.google_drive import (
    GoogleDriveDriveEntity,
    GoogleDriveFileEntity,
)
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
        # Server-side include patterns (preferred)
        instance.include_patterns = config.get("include_patterns", [])

        # Configurable concurrency for file processing
        # (used by BaseSource.process_entities_concurrent)
        # Default batch_size = 1 as requested
        instance.batch_size = int(config.get("batch_size", 30))

        instance.batch_generation = bool(config.get("batch_generation", True))

        return instance

    # --- Incremental sync support (cursor field) ---
    def get_default_cursor_field(self) -> Optional[str]:
        """Default cursor field name for Google Drive incremental sync.

        We use the Drive Changes API page token. The field stored in `cursor.cursor_data`
        will be keyed under this name.
        """
        return "start_page_token"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate the cursor field for Google Drive.

        Only the default field name is supported. Users may override but it must equal
        the expected key so that the system can find the stored token.
        """
        valid_field = self.get_default_cursor_field()
        if cursor_field != valid_field:
            raise ValueError(
                f"Invalid cursor field '{cursor_field}' for Google Drive. Use '{valid_field}'."
            )

    def _get_cursor_data(self) -> Dict[str, Any]:
        if self.cursor:
            return self.cursor.cursor_data or {}
        return {}

    def _update_cursor_data(self, new_token: str) -> None:
        if not self.cursor:
            return
        cursor_field = self.get_effective_cursor_field() or self.get_default_cursor_field()
        if not cursor_field:
            return
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}
        self.cursor.cursor_data[cursor_field] = new_token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get_with_auth(  # noqa: C901
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
            try:
                self.logger.debug(f"API GET {url} params={params if params else {}}")
            except Exception:
                pass
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
            self.logger.debug(f"List drives page: returned {len(drives)} drives")
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

    # --- Changes API helpers ---
    async def _get_start_page_token(self, client: httpx.AsyncClient) -> str:
        url = "https://www.googleapis.com/drive/v3/changes/startPageToken"
        params = {
            "supportsAllDrives": "true",
        }
        data = await self._get_with_auth(client, url, params=params)
        token = data.get("startPageToken")
        if not token:
            raise ValueError("Failed to retrieve startPageToken from Drive API")
        return token

    async def _iterate_changes(
        self, client: httpx.AsyncClient, start_token: str
    ) -> AsyncGenerator[Dict, None]:
        """Iterate over all changes since the provided page token.

        Yields individual change objects. Stores the latest newStartPageToken on the instance
        for use after the stream completes.
        """
        url = "https://www.googleapis.com/drive/v3/changes"
        params: Dict[str, Any] = {
            "pageToken": start_token,
            "includeRemoved": "true",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "pageSize": 1000,
            "fields": (
                "nextPageToken,newStartPageToken,"
                "changes(removed,fileId,changeType,file("
                "id,name,mimeType,description,trashed,explicitlyTrashed,"
                "parents,shared,webViewLink,iconLink,createdTime,modifiedTime,size,md5Checksum)"
                ")"
            ),
        }

        latest_new_start: Optional[str] = None

        while True:
            data = await self._get_with_auth(client, url, params=params)
            for change in data.get("changes", []) or []:
                yield change

            next_token = data.get("nextPageToken")
            latest_new_start = data.get("newStartPageToken") or latest_new_start

            if next_token:
                params["pageToken"] = next_token
            else:
                break

        # Persist for caller
        self._latest_new_start_page_token = latest_new_start

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

        self.logger.debug(
            f"List files start: corpora={corpora}, include_all_drives={include_all_drives}, "
            f"drive_id={drive_id}, base_q={params['q']}, context={context}"
        )

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
            self.logger.debug(
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
        self.logger.debug(
            f"\n\nGoogle Drive API returned {total_files_from_api} total files across "
            f"{page_count} pages ({context})\n\n"
        )

    async def _list_folders(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str],
        parent_id: Optional[str],
    ) -> AsyncGenerator[Dict, None]:
        """List folders under a given parent.

        If parent_id is None, returns all folders matching name in the scope.
        """
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "pageSize": 100,
            "corpora": corpora,
            "includeItemsFromAllDrives": str(include_all_drives).lower(),
            "supportsAllDrives": "true",
            "fields": "nextPageToken, files(id, name, parents)",
        }

        # Base folder query
        if parent_id:
            q = (
                f"'{parent_id}' in parents and "
                "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            )
        else:
            q = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        params["q"] = q

        if drive_id:
            params["driveId"] = drive_id

        self.logger.debug(
            (
                "List folders start: parent_id=%s, corpora=%s, drive_id=%s, q=%s"
                % (parent_id, corpora, drive_id, q)
            )
        )

        while url:
            data = await self._get_with_auth(client, url, params=params)
            folders = data.get("files", [])
            self.logger.debug(
                f"List folders page: parent_id={parent_id}, returned {len(folders)} folders"
            )
            for folder in folders:
                yield folder

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

    async def _list_files_in_folder(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str],
        parent_id: str,
        name_token: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """List files directly under a given folder.

        Optionally coarse filtered by a "name contains" token.
        """
        url = "https://www.googleapis.com/drive/v3/files"
        base_q = (
            f"'{parent_id}' in parents and "
            "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        )
        if name_token:
            safe_token = name_token.replace("'", "\\'")
            q = f"{base_q} and name contains '{safe_token}'"
        else:
            q = base_q

        params = {
            "pageSize": 100,
            "corpora": corpora,
            "includeItemsFromAllDrives": str(include_all_drives).lower(),
            "supportsAllDrives": "true",
            "q": q,
            "fields": (
                "nextPageToken, files("
                "id, name, mimeType, description, starred, trashed, "
                "explicitlyTrashed, parents, shared, webViewLink, iconLink, "
                "createdTime, modifiedTime, size, md5Checksum, webContentLink)"
            ),
        }
        if drive_id:
            params["driveId"] = drive_id

        self.logger.debug(
            f"List files-in-folder start: parent_id={parent_id}, name_token={name_token}, q={q}"
        )

        while url:
            data = await self._get_with_auth(client, url, params=params)
            files_in_page = data.get("files", [])
            self.logger.debug(
                (
                    "List files-in-folder page: parent_id=%s, returned %d files"
                    % (parent_id, len(files_in_page))
                )
            )
            for f in files_in_page:
                yield f

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

    def _extract_name_token_from_glob(self, pattern: str) -> Optional[str]:
        """Extract a coarse token for name contains from a glob (best-effort)."""
        import re

        # '*.pdf' -> '.pdf', 'report*' -> 'report'
        if pattern.startswith("*."):
            return pattern[1:]
        m = re.match(r"([^*?]+)[*?].*", pattern)
        if m:
            return m.group(1)
        if "*" not in pattern and "?" not in pattern and pattern:
            return pattern
        return None

    async def _traverse_and_yield_files(
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str],
        start_folder_ids: List[str],
        filename_glob: Optional[str],
        context: str,
    ) -> AsyncGenerator[Dict, None]:
        """BFS traversal from start folders yielding file objects.

        Final match is performed by filename glob.
        """
        import fnmatch
        from collections import deque

        name_token = self._extract_name_token_from_glob(filename_glob) if filename_glob else None

        self.logger.debug(
            f"Traverse start: roots={len(start_folder_ids)}, filename_glob={filename_glob}, "
            f"name_token={name_token}"
        )

        queue = deque(start_folder_ids)
        while queue:
            folder_id = queue.popleft()

            self.logger.debug(f"Scanning folder: {folder_id}")
            # Files directly in this folder
            async for file_obj in self._list_files_in_folder(
                client, corpora, include_all_drives, drive_id, folder_id, name_token
            ):
                file_name = file_obj.get("name", "")
                if filename_glob:
                    matched = fnmatch.fnmatch(file_name, filename_glob)
                    self.logger.debug(
                        f"Encountered file: {file_name} ({file_obj.get('id')}) "
                        f"matched={matched} pattern={filename_glob}"
                    )
                    if matched:
                        yield file_obj
                else:
                    self.logger.debug(
                        f"Encountered file: {file_name} ({file_obj.get('id')}) matched=True"
                    )
                    yield file_obj

            # Subfolders
            async for subfolder in self._list_folders(
                client, corpora, include_all_drives, drive_id, folder_id
            ):
                self.logger.debug(
                    f"Enqueue subfolder: {subfolder.get('name')} ({subfolder.get('id')})"
                )
                queue.append(subfolder["id"])

    async def _resolve_pattern_to_roots(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str],
        pattern: str,
    ) -> Tuple[List[str], Optional[str]]:
        """Resolve a simple path-like include pattern to starting folder IDs and a filename glob.

        Supports patterns like: 'Folder/*', 'Folder/Sub/file.pdf'.
        Folder segments are treated as exact names.
        The last segment may be a filename glob; if omitted, includes all files recursively.
        """
        # Normalize pattern and split
        self.logger.debug(f"Resolve pattern: '{pattern}'")
        norm = pattern.strip().strip("/")
        segments = norm.split("/") if norm else []

        if not segments:
            return [], None

        # Determine if last segment is a file glob (has '.' or wildcard) -> treat as filename glob
        last = segments[-1]
        filename_glob: Optional[str] = None
        folder_segments = segments
        if "." in last or "*" in last or "?" in last:
            filename_glob = last
            folder_segments = segments[:-1]
        self.logger.debug(
            f"Pattern segments: folders={folder_segments}, filename_glob={filename_glob}"
        )

        async def find_folders_by_name(  # noqa: C901
            parent_ids: Optional[List[str]], name: str
        ) -> List[str]:
            found: List[str] = []
            if parent_ids:
                for pid in parent_ids:
                    # List child folders with exact name under pid
                    url = "https://www.googleapis.com/drive/v3/files"
                    safe_name = name.replace("'", "\\'")
                    q = (
                        f"'{pid}' in parents and mimeType = 'application/vnd.google-apps.folder' "
                        f"and name = '{safe_name}' and trashed = false"
                    )
                    params = {
                        "pageSize": 100,
                        "corpora": corpora,
                        "includeItemsFromAllDrives": str(include_all_drives).lower(),
                        "supportsAllDrives": "true",
                        "q": q,
                        "fields": "nextPageToken, files(id)",
                    }
                    if drive_id:
                        params["driveId"] = drive_id

                    url_iter = url
                    while url_iter:
                        data = await self._get_with_auth(client, url_iter, params=params)
                        for f in data.get("files", []):
                            found.append(f["id"])
                        npt = data.get("nextPageToken")
                        if not npt:
                            break
                        params["pageToken"] = npt
                        url_iter = url
                self.logger.debug(
                    (
                        "find_folders_by_name: name='%s' under %d parents -> %d matches"
                        % (name, len(parent_ids), len(found))
                    )
                )
            else:
                # Search folders by exact name anywhere in scope
                url = "https://www.googleapis.com/drive/v3/files"
                safe_name = name.replace("'", "\\'")
                q = (
                    "mimeType = 'application/vnd.google-apps.folder' and "
                    f"name = '{safe_name}' and trashed = false"
                )
                params = {
                    "pageSize": 100,
                    "corpora": corpora,
                    "includeItemsFromAllDrives": str(include_all_drives).lower(),
                    "supportsAllDrives": "true",
                    "q": q,
                    "fields": "nextPageToken, files(id)",
                }
                if drive_id:
                    params["driveId"] = drive_id

                url_iter = url
                while url_iter:
                    data = await self._get_with_auth(client, url_iter, params=params)
                    for f in data.get("files", []):
                        found.append(f["id"])
                    npt = data.get("nextPageToken")
                    if not npt:
                        break
                    params["pageToken"] = npt
                    url_iter = url
                self.logger.debug(
                    f"find_folders_by_name: global name='{name}' -> {len(found)} matches"
                )
            return found

        parent_ids: Optional[List[str]] = None
        for seg in folder_segments:
            ids = await find_folders_by_name(parent_ids, seg)
            parent_ids = ids
            if not parent_ids:
                break

        # If no folder segments (pattern was just filename glob) return empty roots
        if not folder_segments:
            return [], filename_glob or "*"
        self.logger.debug(
            f"Resolved roots: count={len(parent_ids or [])}, filename_glob={filename_glob}"
        )
        return parent_ids or [], filename_glob

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

                    async def _worker(file_obj: Dict):
                        # MUST return an async iterator: yield 0..N entities
                        ent = await self._process_file_batch(client, file_obj)
                        if ent is not None:
                            yield ent

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

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:  # noqa: C901
        """Generate all Google Drive entities.

        Behavior:
        - If no cursor token exists: perform a FULL sync (shared drives + files), then store
          the current startPageToken for the next incremental run.
        - If a cursor token exists: perform INCREMENTAL sync using the Changes API. Emit
          deletion entities for removed files and upsert entities for changed files.
        """
        try:
            async with httpx.AsyncClient() as client:
                patterns: List[str] = getattr(self, "include_patterns", []) or []
                self.logger.debug(f"Include patterns: {patterns}")

                # 1) Always yield shared drives as entities
                try:
                    async for drive_entity in self._generate_drive_entities(client):
                        yield drive_entity
                except Exception as e:
                    self.logger.error(f"Error generating drive entities: {str(e)}")

                # Prepare shared drive IDs for file processing
                drive_ids: List[str] = []
                try:
                    async for drive_obj in self._list_drives(client):
                        drive_ids.append(drive_obj["id"])
                except Exception as e:
                    self.logger.error(f"Error listing shared drives: {str(e)}")

                # If no include patterns: default behavior (all files in drives + My Drive)
                if not patterns:
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
                            continue

                    try:
                        async for mydrive_file_entity in self._generate_file_entities(
                            client, corpora="user", include_all_drives=False, context="MY DRIVE"
                        ):
                            yield mydrive_file_entity
                    except Exception as e:
                        self.logger.error(f"Error processing My Drive files: {str(e)}")
                    return

                # INCLUDE MODE: Resolve patterns and traverse only matched subtrees
                # Shared drives first
                for drive_id in drive_ids:
                    try:
                        # Resolve and traverse per pattern to keep logic simple and precise
                        for p in patterns:
                            roots, fname_glob = await self._resolve_pattern_to_roots(
                                client,
                                corpora="drive",
                                include_all_drives=True,
                                drive_id=drive_id,
                                pattern=p,
                            )
                            if roots:
                                items = self._traverse_and_yield_files(
                                    client,
                                    corpora="drive",
                                    include_all_drives=True,
                                    drive_id=drive_id,
                                    start_folder_ids=list(set(roots)),
                                    filename_glob=fname_glob,
                                    context=f"drive {drive_id}",
                                )
                                # Process concurrently or sequentially based on flag
                                if getattr(self, "batch_generation", False):
                                    async for processed in self._process_items_concurrently(
                                        client, items
                                    ):
                                        yield processed
                                else:
                                    async for file_obj in items:
                                        processed_entity = await self._process_file_sequential(
                                            client, file_obj
                                        )
                                        if processed_entity:
                                            yield processed_entity

                        # Filename-only patterns (no folder segments) -> global name search
                        filename_only_patterns = [p for p in patterns if "/" not in p]
                        if filename_only_patterns:
                            import fnmatch as _fn

                            async def _filtered_items(
                                drive_id=drive_id, filename_only_patterns=filename_only_patterns
                            ):
                                async for file_obj in self._list_files(
                                    client,
                                    corpora="drive",
                                    include_all_drives=True,
                                    drive_id=drive_id,
                                    context=f"drive {drive_id}",
                                ):
                                    name = file_obj.get("name", "")
                                    matched = any(
                                        _fn.fnmatch(name, pat) for pat in filename_only_patterns
                                    )
                                    if matched:
                                        yield file_obj

                            if getattr(self, "batch_generation", False):
                                async for processed in self._process_items_concurrently(
                                    client, _filtered_items()
                                ):
                                    yield processed
                            else:
                                async for file_obj in _filtered_items():
                                    processed_entity = await self._process_file_sequential(
                                        client, file_obj
                                    )
                                    if processed_entity:
                                        yield processed_entity

                    except Exception as e:
                        self.logger.error(f"Include mode error for drive {drive_id}: {str(e)}")

                # My Drive include patterns
                try:
                    for p in patterns:
                        roots, fname_glob = await self._resolve_pattern_to_roots(
                            client,
                            corpora="user",
                            include_all_drives=False,
                            drive_id=None,
                            pattern=p,
                        )
                        if roots:
                            items = self._traverse_and_yield_files(
                                client,
                                corpora="user",
                                include_all_drives=False,
                                drive_id=None,
                                start_folder_ids=list(set(roots)),
                                filename_glob=fname_glob,
                                context="MY DRIVE",
                            )
                            if getattr(self, "batch_generation", False):
                                async for processed in self._process_items_concurrently(
                                    client, items
                                ):
                                    yield processed
                            else:
                                async for file_obj in items:
                                    processed_entity = await self._process_file_sequential(
                                        client, file_obj
                                    )
                                    if processed_entity:
                                        yield processed_entity

                    filename_only_patterns = [p for p in patterns if "/" not in p]
                    if filename_only_patterns:
                        import fnmatch as _fn

                        async def _filtered_items_user(
                            filename_only_patterns=filename_only_patterns,
                        ):
                            async for file_obj in self._list_files(
                                client,
                                corpora="user",
                                include_all_drives=False,
                                drive_id=None,
                                context="MY DRIVE",
                            ):
                                name = file_obj.get("name", "")
                                if any(_fn.fnmatch(name, pat) for pat in filename_only_patterns):
                                    yield file_obj

                        if getattr(self, "batch_generation", False):
                            async for processed in self._process_items_concurrently(
                                client, _filtered_items_user()
                            ):
                                yield processed
                        else:
                            async for file_obj in _filtered_items_user():
                                processed_entity = await self._process_file_sequential(
                                    client, file_obj
                                )
                                if processed_entity:
                                    yield processed_entity

                except Exception as e:
                    self.logger.error(f"Include mode error for My Drive: {str(e)}")

        except Exception as e:
            self.logger.error(f"Critical error in generate_entities: {str(e)}")

    async def _process_items_concurrently(
        self,
        client: httpx.AsyncClient,
        items: AsyncGenerator[Dict, None],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Helper to process file objects concurrently via worker pool."""

        async def _worker(file_obj: Dict):
            ent = await self._process_file_batch(client, file_obj)
            if ent is not None:
                yield ent

        async for processed in self.process_entities_concurrent(
            items=items,
            worker=_worker,
            batch_size=getattr(self, "batch_size", 30),
            preserve_order=False,
        ):
            yield processed
