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

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.cursors import GoogleDriveCursor
from airweave.platform.configs.config import GoogleDriveConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_drive import (
    GoogleDriveDriveEntity,
    GoogleDriveFileDeletionEntity,
    GoogleDriveFileEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Google Drive",
    short_name="google_drive",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
        AuthenticationMethod.OAUTH_BYOC,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=GoogleDriveConfig,
    labels=["File Storage"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=GoogleDriveCursor,
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

        config = config or {}
        instance.include_patterns = config.get("include_patterns", [])

        # Concurrency configuration
        instance.batch_size = int(config.get("batch_size", 30))
        instance.batch_generation = bool(config.get("batch_generation", True))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        return instance

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Google Drive RFC3339 timestamps into aware datetimes."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def validate(self) -> bool:
        """Validate the Google Drive source connection."""
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/drive/v3/drives?pageSize=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    @retry(
        stop=stop_after_attempt(5),  # Increased for aggressive rate limits
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(  # noqa: C901
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to the Google Drive API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header from both real API and AirweaveHttpClient)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.
        """
        # Get a valid token (will refresh if needed)
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
            # Log differently for rate limits (which will be retried)
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "unknown")
                self.logger.warning(
                    f"Rate limit hit (429) for Google Drive API: {url} "
                    f"(will retry after {retry_after}s)"
                )
            else:
                self.logger.error(
                    f"HTTP status error {e.response.status_code} from Google Drive API: {url}"
                )
            raise  # Re-raise for ALL HTTP errors (tenacity will retry 429s)
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

    def _build_drive_entity(self, drive_obj: Dict) -> GoogleDriveDriveEntity:
        """Build a GoogleDriveDriveEntity from API response."""
        created_time = self._parse_datetime(drive_obj.get("createdTime"))
        return GoogleDriveDriveEntity(
            breadcrumbs=[],
            drive_id=drive_obj["id"],
            title=drive_obj.get("name", "Untitled Drive"),
            created_time=created_time,
            kind=drive_obj.get("kind"),
            color_rgb=drive_obj.get("colorRgb"),
            hidden=drive_obj.get("hidden", False),
            org_unit_id=drive_obj.get("orgUnitId"),
        )

    async def _generate_drive_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GoogleDriveDriveEntity, None]:
        """Generate GoogleDriveDriveEntity objects for each shared drive."""
        async for drive_obj in self._list_drives(client):
            yield GoogleDriveDriveEntity(
                # Base fields
                entity_id=drive_obj["id"],
                breadcrumbs=[],
                name=drive_obj.get("name", "Untitled Drive"),
                created_at=drive_obj.get("createdTime"),
                updated_at=None,  # Drives don't have modified time
                # API fields
                kind=drive_obj.get("kind"),
                color_rgb=drive_obj.get("colorRgb"),
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

    def _get_cursor_start_page_token(self) -> Optional[str]:
        """Return the stored startPageToken if available."""
        if not self.cursor:
            return None
        token = self.cursor.data.get("start_page_token")
        if not token:
            return None
        return token

    def _has_file_changed(self, file_obj: Dict) -> bool:
        """Check if file metadata indicates change without downloading.

        Compares: modifiedTime, md5Checksum, size
        Returns True if file is new or changed, False if unchanged.

        Args:
            file_obj: File metadata from Google Drive API

        Returns:
            True if file should be processed (new or changed), False if unchanged
        """
        if not self.cursor:
            return True  # No cursor = treat as changed

        file_id = file_obj.get("id")
        if not file_id:
            return True

        cursor_data = self.cursor.data
        file_metadata = cursor_data.get("file_metadata", {})
        stored_meta = file_metadata.get(file_id)

        if not stored_meta:
            return True  # New file

        # Compare metadata
        current_modified = file_obj.get("modifiedTime")
        current_md5 = file_obj.get("md5Checksum")
        current_size = file_obj.get("size")

        if (
            stored_meta.get("modified_time") != current_modified
            or stored_meta.get("md5_checksum") != current_md5
            or stored_meta.get("size") != current_size
        ):
            return True

        return False  # Unchanged

    def _store_file_metadata(self, file_obj: Dict) -> None:
        """Store file metadata in cursor for future change detection.

        Args:
            file_obj: File metadata from Google Drive API
        """
        if not self.cursor:
            return

        file_id = file_obj.get("id")
        if not file_id:
            return

        cursor_data = self.cursor.data
        file_metadata = cursor_data.get("file_metadata", {})

        file_metadata[file_id] = {
            "modified_time": file_obj.get("modifiedTime"),
            "md5_checksum": file_obj.get("md5Checksum"),
            "size": file_obj.get("size"),
        }

        self.cursor.update(file_metadata=file_metadata)

    async def _emit_changes_since_token(
        self, client: httpx.AsyncClient, start_token: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit change entities (modifications, additions, and deletions) since the given token."""
        self.logger.info(
            f"📊 Processing Drive changes since token {start_token[:20]}... (incremental sync)"
        )
        # Reset token tracker before iterating
        self._latest_new_start_page_token = None
        try:
            async for change in self._iterate_changes(client, start_token):
                entity = await self._build_entity_from_change(change)
                if entity:
                    yield entity
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 410:
                # Token expired or invalid
                self.logger.warning(
                    "Stored startPageToken is no longer valid (410). Fetching a fresh token."
                )
                if self.cursor:
                    try:
                        fresh_token = await self._get_start_page_token(client)
                        if fresh_token:
                            self.cursor.update(start_page_token=fresh_token)
                    except Exception as token_error:
                        self.logger.error(
                            f"Failed to refresh startPageToken after 410: {token_error}"
                        )
            else:
                raise

    def _build_deletion_entity_from_change(
        self, change: Dict
    ) -> Optional[GoogleDriveFileDeletionEntity]:
        """Build a deletion entity from a Drive change object.

        Args:
            change: Change object from Google Drive Changes API

        Returns:
            GoogleDriveFileDeletionEntity if this is a valid deletion, None otherwise
        """
        file_obj = change.get("file") or {}
        file_id = change.get("fileId") or file_obj.get("id")

        if not file_id:
            self.logger.debug(
                "Drive change marked as deletion but missing fileId. Raw change: %s", change
            )
            return None

        label = file_obj.get("name") or file_id

        drive_id = file_obj.get("driveId") or change.get("driveId")
        parents = file_obj.get("parents") or []
        if not drive_id and parents:
            drive_id = parents[0]

        return GoogleDriveFileDeletionEntity(
            breadcrumbs=[],
            file_id=file_id,
            label=f"Deleted file {label}",
            drive_id=drive_id,
            deletion_status="removed",
        )

    async def _build_entity_from_change(self, change: Dict) -> Optional[BaseEntity]:
        """Convert a Drive change object into an entity (file or deletion).

        Handles both deletions and modifications/additions. Uses metadata comparison
        to avoid downloading unchanged files during incremental sync.

        Args:
            change: Change object from Google Drive Changes API

        Returns:
            GoogleDriveFileEntity for changed files, GoogleDriveFileDeletionEntity for deletions,
            or None if file is unchanged or should be skipped
        """
        file_obj = change.get("file") or {}
        removed = change.get("removed", False)
        trashed = bool(file_obj.get("trashed")) or bool(file_obj.get("explicitlyTrashed"))
        change_type = change.get("changeType")

        # Handle deletions first
        is_deletion = removed or trashed or (change_type and change_type.lower() == "removed")
        if is_deletion:
            return self._build_deletion_entity_from_change(change)

        # Handle modifications/additions
        if not file_obj.get("id"):
            return None

        # Skip folders (only process files)
        if file_obj.get("mimeType") == "application/vnd.google-apps.folder":
            return None

        # Check if file actually changed using metadata
        if not self._has_file_changed(file_obj):
            self.logger.debug(f"File {file_obj.get('name')} unchanged (metadata match) - skipping")
            return None

        # File changed - download and process
        self.logger.debug(f"File {file_obj.get('name')} changed - processing")
        return await self._process_changed_file(file_obj)

    async def _store_next_start_page_token(self, client: httpx.AsyncClient) -> None:
        """Persist the next startPageToken for future incremental runs."""
        if not self.cursor:
            return

        next_token = getattr(self, "_latest_new_start_page_token", None)
        if not next_token:
            try:
                next_token = await self._get_start_page_token(client)
            except Exception as exc:
                self.logger.error(f"Failed to fetch startPageToken: {exc}")
                return

        if next_token:
            self.cursor.update(start_page_token=next_token)
            self.logger.debug(f"Saved startPageToken for next run: {next_token}")

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

    async def _resolve_pattern_to_roots(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str],
        pattern: str,
    ) -> tuple[List[str], Optional[str]]:
        """Resolve a pattern like 'FOLDER/SUBFOLDER/*.pdf' to root folder IDs and filename glob.

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

        async def find_folders_by_name(parent_ids: Optional[List[str]], name: str) -> List[str]:  # noqa: C901
            """Find folders by exact name, either under specific parents or globally."""
            found: List[str] = []
            safe_name = name.replace("'", "\\'")

            if parent_ids:
                # Search under specific parent folders
                for pid in parent_ids:
                    url = "https://www.googleapis.com/drive/v3/files"
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
                        "fields": "nextPageToken, files(id, name)",
                    }
                    if drive_id:
                        params["driveId"] = drive_id

                    while url:
                        data = await self._get_with_auth(client, url, params=params)
                        for f in data.get("files", []):
                            found.append(f["id"])
                        npt = data.get("nextPageToken")
                        if not npt:
                            break
                        params["pageToken"] = npt

                self.logger.debug(
                    f"find_folders_by_name: name='{name}' under {len(parent_ids)} "
                    f"parents -> {len(found)} matches"
                )
            else:
                # Search folders by exact name anywhere in scope
                url = "https://www.googleapis.com/drive/v3/files"
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
                    "fields": "nextPageToken, files(id, name)",
                }
                if drive_id:
                    params["driveId"] = drive_id

                while url:
                    data = await self._get_with_auth(client, url, params=params)
                    for f in data.get("files", []):
                        found.append(f["id"])
                    npt = data.get("nextPageToken")
                    if not npt:
                        break
                    params["pageToken"] = npt

                self.logger.debug(
                    f"find_folders_by_name: global name='{name}' -> {len(found)} matches"
                )
            return found

        # Traverse folder hierarchy
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
            f"Resolved pattern '{pattern}' to {len(parent_ids or [])} folder(s), "
            f"filename_glob={filename_glob}"
        )
        return parent_ids or [], filename_glob

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

    def _build_file_entity(
        self, file_obj: Dict, parent_breadcrumb: Optional[Breadcrumb]
    ) -> Optional[GoogleDriveFileEntity]:
        """Helper to build a GoogleDriveFileEntity from a file API response object.

        Returns None for files that should be skipped (e.g., trashed files, videos).
        """
        # Skip all video files to prevent tmp storage issues
        mime_type = file_obj.get("mimeType", "")
        if mime_type.startswith("video/"):
            file_name = file_obj.get("name", "unknown")
            self.logger.debug(f"Skipping video file ({mime_type}): {file_name}")
            return None

        # Skip files larger than 200MB using metadata from the listing API
        MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
        file_size = int(file_obj["size"]) if file_obj.get("size") else 0
        if file_size > MAX_FILE_SIZE_BYTES:
            file_name = file_obj.get("name", "unknown")
            size_mb = file_size / (1024 * 1024)
            self.logger.info(f"Skipping oversized file ({size_mb:.1f}MB, max 200MB): {file_name}")
            return None

        # Create download URL based on file type
        download_url = None

        # Get the original file name
        file_name = file_obj.get("name", "Untitled")
        mime_type = file_obj.get("mimeType", "")

        if mime_type.startswith("application/vnd.google-apps."):
            # For Google native files, get the appropriate export format
            export_mime_type, file_extension = self._get_export_format_and_extension(mime_type)

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

        # Determine general file type from mime_type
        from airweave.platform.entities.utils import _determine_file_type_from_mime

        file_type = _determine_file_type_from_mime(mime_type)

        created_time = self._parse_datetime(file_obj.get("createdTime")) or datetime.utcnow()
        modified_time = self._parse_datetime(file_obj.get("modifiedTime")) or created_time
        modified_by_me_time = self._parse_datetime(file_obj.get("modifiedByMeTime"))
        viewed_by_me_time = self._parse_datetime(file_obj.get("viewedByMeTime"))
        shared_with_me_time = self._parse_datetime(file_obj.get("sharedWithMeTime"))

        breadcrumbs = [parent_breadcrumb] if parent_breadcrumb else []
        if not breadcrumbs and getattr(self, "_my_drive_breadcrumb", None):
            breadcrumbs = [self._my_drive_breadcrumb]

        return GoogleDriveFileEntity(
            breadcrumbs=breadcrumbs,
            file_id=file_obj["id"],
            title=file_obj.get("name", "Untitled"),
            created_time=created_time,
            modified_time=modified_time,
            name=file_name,  # Use the modified name with extension
            created_at=created_time,
            updated_at=modified_time,
            url=download_url,
            size=int(file_obj["size"]) if file_obj.get("size") else 0,
            file_type=file_type,
            mime_type=mime_type or "application/octet-stream",
            local_path=None,
            description=file_obj.get("description"),
            starred=file_obj.get("starred", False),
            trashed=file_obj.get("trashed", False),
            explicitly_trashed=file_obj.get("explicitlyTrashed", False),
            parents=file_obj.get("parents", []),
            owners=file_obj.get("owners", []),
            shared=file_obj.get("shared", False),
            web_view_link=file_obj.get("webViewLink"),
            icon_link=file_obj.get("iconLink"),
            md5_checksum=file_obj.get("md5Checksum"),
            shared_with_me_time=shared_with_me_time,
            modified_by_me_time=modified_by_me_time,
            viewed_by_me_time=viewed_by_me_time,
        )

    # ------------------------------
    # Concurrency-aware processing
    # ------------------------------
    async def _process_file_batch(
        self, file_obj: Dict, parent_breadcrumb: Optional[Breadcrumb]
    ) -> Optional[GoogleDriveFileEntity]:
        """Build & process a single file (used by concurrent driver)."""
        try:
            file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
            if not file_entity:
                return None
            self.logger.debug(f"Processing file entity: {file_entity.file_id} '{file_entity.name}'")

            # Download file using downloader
            try:
                await self.file_downloader.download_from_url(
                    entity=file_entity,
                    http_client_factory=self.http_client,
                    access_token_provider=self.get_access_token,
                    logger=self.logger,
                )

                # Verify download succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Download failed - no local path set for {file_entity.name}")

                # Store metadata for future change detection
                self._store_file_metadata(file_obj)

                self.logger.debug(f"Successfully downloaded file: {file_entity.name}")
                return file_entity

            except FileSkippedException as e:
                # Skipped unsupported or oversized file
                self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                return None

            except Exception as e:
                self.logger.error(f"Failed to download file {file_entity.name}: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to process file {file_obj.get('name', 'unknown')}: {str(e)}")
            return None

    async def _process_changed_file(
        self, file_obj: Dict, parent_breadcrumb: Optional[Breadcrumb] = None
    ) -> Optional[GoogleDriveFileEntity]:
        """Process a file that has changed based on metadata.

        This method is used during incremental sync to process files that have been
        identified as changed through metadata comparison.

        Args:
            file_obj: File metadata from Google Drive API
            parent_breadcrumb: Optional breadcrumb for parent folder

        Returns:
            GoogleDriveFileEntity if processing succeeded, None if skipped or failed
        """
        # Build entity
        file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
        if not file_entity:
            return None

        self.logger.debug(f"Processing changed file: {file_entity.file_id} '{file_entity.name}'")

        # Download file
        try:
            await self.file_downloader.download_from_url(
                entity=file_entity,
                http_client_factory=self.http_client,
                access_token_provider=self.get_access_token,
                logger=self.logger,
            )

            if not file_entity.local_path:
                raise ValueError(f"Download failed for {file_entity.name}")

            # Store metadata for future comparison
            self._store_file_metadata(file_obj)

            self.logger.debug(f"Successfully processed changed file: {file_entity.name}")
            return file_entity

        except FileSkippedException as e:
            self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to download changed file {file_entity.name}: {e}")
            return None

    def _setup_breadcrumbs(self, drive_objs: List[Dict[str, Any]]) -> None:
        """Setup breadcrumbs for drives and My Drive.

        Args:
            drive_objs: List of drive objects from Google Drive API
        """
        drive_breadcrumbs: Dict[str, Breadcrumb] = {}
        for drive_obj in drive_objs:
            drive_breadcrumbs[drive_obj["id"]] = Breadcrumb(
                entity_id=drive_obj["id"],
                name=drive_obj.get("name", "Untitled Drive"),
                entity_type=GoogleDriveDriveEntity.__name__,
            )

        self._drive_breadcrumbs = drive_breadcrumbs
        self._my_drive_breadcrumb = Breadcrumb(
            entity_id="my_drive",
            name="My Drive",
            entity_type=GoogleDriveDriveEntity.__name__,
        )

    async def _generate_file_entities(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
        parent_breadcrumb: Optional[Breadcrumb] = None,
    ) -> AsyncGenerator[GoogleDriveFileEntity, None]:
        """Generate file entities from a file listing."""
        try:
            if getattr(self, "batch_generation", False):
                # Concurrent flow
                async def _worker(file_obj: Dict):
                    ent = await self._process_file_batch(file_obj, parent_breadcrumb)
                    if ent is not None:
                        yield ent

                async for processed in self.process_entities_concurrent(
                    items=self._list_files(client, corpora, include_all_drives, drive_id, context),
                    worker=_worker,
                    batch_size=getattr(self, "batch_size", 30),
                    preserve_order=getattr(self, "preserve_order", False),
                    stop_on_error=getattr(self, "stop_on_error", False),
                    max_queue_size=getattr(self, "max_queue_size", 200),
                ):
                    yield processed
            else:
                # Sequential flow
                async for file_obj in self._list_files(
                    client, corpora, include_all_drives, drive_id, context
                ):
                    try:
                        file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
                        if not file_entity:
                            continue

                        # Download file using downloader
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

                            # Store metadata for future change detection
                            self._store_file_metadata(file_obj)

                            yield file_entity

                        except FileSkippedException as e:
                            # Skipped unsupported or oversized file
                            self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                            continue

                        except Exception as e:
                            self.logger.error(f"Failed to download file {file_entity.name}: {e}")
                            continue

                    except Exception as e:
                        error_context = f"in drive {drive_id}" if drive_id else "in MY DRIVE"
                        self.logger.error(
                            f"Failed to process file {file_obj.get('name', 'unknown')} "
                            f"{error_context}: {str(e)}"
                        )
                        continue

        except Exception as e:
            self.logger.error(f"Critical exception in _generate_file_entities: {str(e)}")
            # Don't re-raise - let the generator complete

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all Google Drive entities.

        Behavior:
        - If no cursor token exists: perform a FULL sync (shared drives + files), then store
          the current startPageToken for the next incremental run.
        - If a cursor token exists: perform INCREMENTAL sync using the Changes API. Emit
          deletion entities for removed files and upsert entities for changed files.
        """
        try:
            start_page_token = self._get_cursor_start_page_token()
            if start_page_token:
                self.logger.debug(f"📊 Incremental sync using startPageToken={start_page_token}")
            else:
                self.logger.debug("🔄 Full sync (no stored startPageToken)")

            async with self.http_client() as client:
                patterns: List[str] = getattr(self, "include_patterns", []) or []
                self.logger.debug(f"Include patterns: {patterns}")

                drive_objs: List[Dict[str, Any]] = []
                try:
                    async for drive_obj in self._list_drives(client):
                        drive_objs.append(drive_obj)
                        yield self._build_drive_entity(drive_obj)
                except Exception as e:
                    self.logger.error(f"Error generating drive entities: {str(e)}")

                # Setup breadcrumbs for navigation
                self._setup_breadcrumbs(drive_objs)
                drive_breadcrumbs = self._drive_breadcrumbs
                drive_ids = [drive["id"] for drive in drive_objs]

                # INCREMENTAL MODE: Use Changes API exclusively
                if start_page_token:
                    self.logger.info(
                        f"📊 Incremental sync mode - processing changes only (token={start_page_token[:20]}...)"
                    )
                    async for change_entity in self._emit_changes_since_token(
                        client, start_page_token
                    ):
                        yield change_entity

                else:
                    # FULL SYNC MODE: List all files (first run or forced full sync)
                    self.logger.info("🔄 Full sync mode - listing all files")

                    # If no include patterns: default behavior (all files in drives + My Drive)
                    if not patterns:
                        for drive_id in drive_ids:
                            try:
                                drive_breadcrumb = drive_breadcrumbs.get(drive_id)
                                async for file_entity in self._generate_file_entities(
                                    client,
                                    corpora="drive",
                                    include_all_drives=True,
                                    drive_id=drive_id,
                                    context=f"drive {drive_id}",
                                    parent_breadcrumb=drive_breadcrumb,
                                ):
                                    yield file_entity
                            except Exception as e:
                                self.logger.error(
                                    f"Error processing shared drive {drive_id}: {str(e)}"
                                )
                                continue

                        try:
                            async for mydrive_file_entity in self._generate_file_entities(
                                client,
                                corpora="user",
                                include_all_drives=False,
                                context="MY DRIVE",
                                parent_breadcrumb=self._my_drive_breadcrumb,
                            ):
                                yield mydrive_file_entity
                        except Exception as e:
                            self.logger.error(f"Error processing My Drive files: {str(e)}")

                    # INCLUDE MODE: Resolve patterns and traverse only matched subtrees
                    # Shared drives first
                    for drive_id in drive_ids:
                        try:
                            drive_breadcrumb = drive_breadcrumbs.get(drive_id)
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
                                    if getattr(self, "batch_generation", False):
                                        # Concurrent traversal
                                        async def _worker_traverse(
                                            file_obj: Dict, breadcrumb=drive_breadcrumb
                                        ):
                                            ent = await self._process_file_batch(
                                                file_obj, breadcrumb
                                            )
                                            if ent is not None:
                                                yield ent

                                        items_gen = self._traverse_and_yield_files(
                                            client,
                                            corpora="drive",
                                            include_all_drives=True,
                                            drive_id=drive_id,
                                            start_folder_ids=list(set(roots)),
                                            filename_glob=fname_glob,
                                            context=f"drive {drive_id}",
                                        )

                                        async for processed in self.process_entities_concurrent(
                                            items=items_gen,
                                            worker=_worker_traverse,
                                            batch_size=getattr(self, "batch_size", 30),
                                            preserve_order=getattr(self, "preserve_order", False),
                                            stop_on_error=getattr(self, "stop_on_error", False),
                                            max_queue_size=getattr(self, "max_queue_size", 200),
                                        ):
                                            yield processed
                                    else:
                                        # Sequential traversal
                                        async for file_obj in self._traverse_and_yield_files(
                                            client,
                                            corpora="drive",
                                            include_all_drives=True,
                                            drive_id=drive_id,
                                            start_folder_ids=list(set(roots)),
                                            filename_glob=fname_glob,
                                            context=f"drive {drive_id}",
                                        ):
                                            file_entity = self._build_file_entity(
                                                file_obj, drive_breadcrumb
                                            )
                                            if not file_entity:
                                                continue

                                            # Download file using downloader
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
                                                        f"Download failed - no local path set "
                                                        f"for {file_entity.name}"
                                                    )

                                                yield file_entity

                                            except FileSkippedException as e:
                                                # Skipped unsupported or oversized file
                                                self.logger.debug(
                                                    f"Skipping file {file_entity.name}: {e.reason}"
                                                )
                                                continue

                                            except Exception as e:
                                                self.logger.error(
                                                    f"Failed to download file {file_entity.name}: {e}"
                                                )
                                                continue

                            # Filename-only patterns (no folder segments) -> global name search
                            filename_only_patterns = [p for p in patterns if "/" not in p]
                            import fnmatch as _fn

                            for pat in filename_only_patterns:
                                if getattr(self, "batch_generation", False):

                                    async def _worker_match(
                                        file_obj: Dict,
                                        pattern=pat,
                                        breadcrumb=drive_breadcrumb,
                                    ):
                                        name = file_obj.get("name", "")
                                        if _fn.fnmatch(name, pattern):
                                            ent = await self._process_file_batch(
                                                file_obj, breadcrumb
                                            )
                                            if ent is not None:
                                                yield ent

                                    async for processed in self.process_entities_concurrent(
                                        items=self._list_files(
                                            client,
                                            corpora="drive",
                                            include_all_drives=True,
                                            drive_id=drive_id,
                                            context=f"drive {drive_id}",
                                        ),
                                        worker=_worker_match,
                                        batch_size=getattr(self, "batch_size", 30),
                                        preserve_order=getattr(self, "preserve_order", False),
                                        stop_on_error=getattr(self, "stop_on_error", False),
                                        max_queue_size=getattr(self, "max_queue_size", 200),
                                    ):
                                        yield processed
                                else:
                                    async for file_obj in self._list_files(
                                        client,
                                        corpora="drive",
                                        include_all_drives=True,
                                        drive_id=drive_id,
                                        context=f"drive {drive_id}",
                                    ):
                                        name = file_obj.get("name", "")
                                        if _fn.fnmatch(name, pat):
                                            file_entity = self._build_file_entity(
                                                file_obj, drive_breadcrumb
                                            )
                                            if not file_entity:
                                                continue

                                            # Download file using downloader
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
                                                        f"Download failed - no local path set "
                                                        f"for {file_entity.name}"
                                                    )

                                                yield file_entity

                                            except FileSkippedException as e:
                                                # Skipped unsupported or oversized file
                                                self.logger.debug(
                                                    f"Skipping file {file_entity.name}: {e.reason}"
                                                )
                                                continue

                                            except Exception as e:
                                                self.logger.error(
                                                    f"Failed to download file {file_entity.name}: {e}"
                                                )
                                                continue

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
                                if getattr(self, "batch_generation", False):

                                    async def _worker_traverse_user(
                                        file_obj: Dict, breadcrumb=self._my_drive_breadcrumb
                                    ):
                                        ent = await self._process_file_batch(file_obj, breadcrumb)
                                        if ent is not None:
                                            yield ent

                                    items_gen_user = self._traverse_and_yield_files(
                                        client,
                                        corpora="user",
                                        include_all_drives=False,
                                        drive_id=None,
                                        start_folder_ids=list(set(roots)),
                                        filename_glob=fname_glob,
                                        context="MY DRIVE",
                                    )

                                    async for processed in self.process_entities_concurrent(
                                        items=items_gen_user,
                                        worker=_worker_traverse_user,
                                        batch_size=getattr(self, "batch_size", 30),
                                        preserve_order=getattr(self, "preserve_order", False),
                                        stop_on_error=getattr(self, "stop_on_error", False),
                                        max_queue_size=getattr(self, "max_queue_size", 200),
                                    ):
                                        yield processed
                                else:
                                    async for file_obj in self._traverse_and_yield_files(
                                        client,
                                        corpora="user",
                                        include_all_drives=False,
                                        drive_id=None,
                                        start_folder_ids=list(set(roots)),
                                        filename_glob=fname_glob,
                                        context="MY DRIVE",
                                    ):
                                        file_entity = self._build_file_entity(
                                            file_obj, self._my_drive_breadcrumb
                                        )
                                        if not file_entity:
                                            continue

                                        # Download file using downloader
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
                                                    f"Download failed - no local path set "
                                                    f"for {file_entity.name}"
                                                )

                                            yield file_entity

                                        except FileSkippedException as e:
                                            # Skipped unsupported or oversized file
                                            self.logger.debug(
                                                f"Skipping file {file_entity.name}: {e.reason}"
                                            )
                                            continue

                                        except Exception as e:
                                            self.logger.error(
                                                f"Failed to download file {file_entity.name}: {e}"
                                            )
                                            continue

                        filename_only_patterns = [p for p in patterns if "/" not in p]
                        import fnmatch as _fn

                        for pat in filename_only_patterns:
                            if getattr(self, "batch_generation", False):

                                async def _worker_match_user(
                                    file_obj: Dict,
                                    pattern=pat,
                                    breadcrumb=self._my_drive_breadcrumb,
                                ):
                                    name = file_obj.get("name", "")
                                    if _fn.fnmatch(name, pattern):
                                        ent = await self._process_file_batch(file_obj, breadcrumb)
                                        if ent is not None:
                                            yield ent

                                async for processed in self.process_entities_concurrent(
                                    items=self._list_files(
                                        client,
                                        corpora="user",
                                        include_all_drives=False,
                                        drive_id=None,
                                        context="MY DRIVE",
                                    ),
                                    worker=_worker_match_user,
                                    batch_size=getattr(self, "batch_size", 30),
                                    preserve_order=getattr(self, "preserve_order", False),
                                    stop_on_error=getattr(self, "stop_on_error", False),
                                    max_queue_size=getattr(self, "max_queue_size", 200),
                                ):
                                    yield processed
                            else:
                                async for file_obj in self._list_files(
                                    client,
                                    corpora="user",
                                    include_all_drives=False,
                                    drive_id=None,
                                    context="MY DRIVE",
                                ):
                                    name = file_obj.get("name", "")
                                    if _fn.fnmatch(name, pat):
                                        file_entity = self._build_file_entity(
                                            file_obj, self._my_drive_breadcrumb
                                        )
                                        if not file_entity:
                                            continue

                                        # Download file using downloader
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
                                                    f"Download failed - no local path set "
                                                    f"for {file_entity.name}"
                                                )

                                            yield file_entity

                                        except FileSkippedException as e:
                                            # Skipped unsupported or oversized file
                                            self.logger.debug(
                                                f"Skipping file {file_entity.name}: {e.reason}"
                                            )
                                            continue

                                        except Exception as e:
                                            self.logger.error(
                                                f"Failed to download file {file_entity.name}: {e}"
                                            )
                                            continue

                    except Exception as e:
                        self.logger.error(f"Include mode error for My Drive: {str(e)}")

                # Store the next start page token for future incremental syncs
                await self._store_next_start_page_token(client)

        except Exception as e:
            self.logger.error(f"Critical error in generate_entities: {str(e)}")
            # Re-raise as SyncFailureError to explicitly fail the sync
            from airweave.platform.sync.exceptions import SyncFailureError

            raise SyncFailureError(f"Google Drive sync failed: {str(e)}") from e
