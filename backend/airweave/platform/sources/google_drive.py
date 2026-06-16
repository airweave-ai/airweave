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

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import GoogleDriveConfig
from airweave.platform.cursors import GoogleDriveCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_drive import (
    GoogleDriveDriveEntity,
    GoogleDriveFileDeletionEntity,
    GoogleDriveFileEntity,
    _parse_drive_dt,
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

    drive_id_filter: Optional[str] = None

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GoogleDriveConfig,
    ) -> GoogleDriveSource:
        """Create a new Google Drive source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.include_patterns = config.include_patterns if config else []
        instance.drive_id_filter = config.drive_id if config else None
        instance.batch_size = 30
        instance.batch_generation = True
        instance.max_queue_size = 200
        instance.preserve_order = False
        instance.stop_on_error = False
        return instance

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Google Drive RFC3339 timestamps into aware datetimes."""
        return _parse_drive_dt(value)

    async def validate(self) -> None:
        """Validate credentials by pinging the shared drives list."""
        await self._get(
            "https://www.googleapis.com/drive/v3/drives",
            params={"pageSize": "1"},
        )

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated GET request to the Google Drive API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header from both real API and AirweaveHttpClient)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.
        """
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _list_drives(self) -> AsyncGenerator[Dict, None]:
        """List all shared drives (Drive objects) using pagination.

        GET https://www.googleapis.com/drive/v3/drives
        """
        url = "https://www.googleapis.com/drive/v3/drives"
        params = {"pageSize": 100}
        while url:
            data = await self._get(url, params=params)
            drives = data.get("drives", [])
            self.logger.debug(f"List drives page: returned {len(drives)} drives")
            for drive_obj in drives:
                yield drive_obj

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/drives"

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

    async def _generate_drive_entities(self) -> AsyncGenerator[GoogleDriveDriveEntity, None]:
        """Generate GoogleDriveDriveEntity objects for each shared drive."""
        async for drive_obj in self._list_drives():
            yield GoogleDriveDriveEntity(
                entity_id=drive_obj["id"],
                breadcrumbs=[],
                name=drive_obj.get("name", "Untitled Drive"),
                created_at=drive_obj.get("createdTime"),
                updated_at=None,
                kind=drive_obj.get("kind"),
                color_rgb=drive_obj.get("colorRgb"),
                hidden=drive_obj.get("hidden", False),
                org_unit_id=drive_obj.get("orgUnitId"),
            )

    # --- Changes API helpers ---
    async def _get_start_page_token(self) -> str:
        url = "https://www.googleapis.com/drive/v3/changes/startPageToken"
        params: Dict[str, Any] = {
            "supportsAllDrives": "true",
        }
        if self.drive_id_filter:
            params["driveId"] = self.drive_id_filter
        data = await self._get(url, params=params)
        token = data.get("startPageToken")
        if not token:
            raise ValueError("Failed to retrieve startPageToken from Drive API")
        return token

    async def _iterate_changes(self, start_token: str) -> AsyncGenerator[Dict, None]:
        """Iterate over all changes since the provided page token.

        Yields individual change objects. Stores the latest newStartPageToken on the instance
        for use after the stream completes.
        """
        url = "https://www.googleapis.com/drive/v3/changes"
        drive_id_filter = self.drive_id_filter
        params: Dict[str, Any] = {
            "pageToken": start_token,
            "includeRemoved": "true",
            # Must be "true" even when driveId is set — otherwise the API omits
            # shared-drive items entirely. driveId alone scopes changes to that drive.
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
        if drive_id_filter:
            params["driveId"] = drive_id_filter

        latest_new_start: Optional[str] = None

        while True:
            data = await self._get(url, params=params)
            for change in data.get("changes", []) or []:
                yield change

            next_token = data.get("nextPageToken")
            latest_new_start = data.get("newStartPageToken") or latest_new_start

            if next_token:
                params["pageToken"] = next_token
            else:
                break

        self._latest_new_start_page_token = latest_new_start

    def _get_cursor_start_page_token(self) -> Optional[str]:
        """Return the stored startPageToken if available."""
        if not self._cursor:
            return None
        token = self._cursor.data.get("start_page_token")
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
        if not self._cursor:
            return True

        file_id = file_obj.get("id")
        if not file_id:
            return True

        cursor_data = self._cursor.data
        file_metadata = cursor_data.get("file_metadata", {})
        stored_meta = file_metadata.get(file_id)

        if not stored_meta:
            return True

        current_modified = file_obj.get("modifiedTime")
        current_md5 = file_obj.get("md5Checksum")
        current_size = file_obj.get("size")

        if (
            stored_meta.get("modified_time") != current_modified
            or stored_meta.get("md5_checksum") != current_md5
            or stored_meta.get("size") != current_size
        ):
            return True

        return False

    def _store_file_metadata(self, file_obj: Dict) -> None:
        """Store file metadata in cursor for future change detection.

        Args:
            file_obj: File metadata from Google Drive API
        """
        if not self._cursor:
            return

        file_id = file_obj.get("id")
        if not file_id:
            return

        cursor_data = self._cursor.data
        file_metadata = cursor_data.get("file_metadata", {})

        file_metadata[file_id] = {
            "modified_time": file_obj.get("modifiedTime"),
            "md5_checksum": file_obj.get("md5Checksum"),
            "size": file_obj.get("size"),
        }

        self._cursor.update(file_metadata=file_metadata)

    async def _emit_changes_since_token(
        self,
        start_token: str,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit change entities (modifications, additions, and deletions) since the given token."""
        self.logger.info(
            f"Processing Drive changes since token {start_token[:20]}... (incremental sync)"
        )
        self._latest_new_start_page_token = None
        try:
            async for change in self._iterate_changes(start_token):
                entity = await self._build_entity_from_change(change, files=files)
                if entity:
                    yield entity
        except SourceAuthError:
            raise
        except SourceError as exc:
            if "HTTP 410" in str(exc):
                self.logger.warning(
                    "Stored startPageToken is no longer valid (410). Fetching a fresh token."
                )
                if self._cursor:
                    try:
                        fresh_token = await self._get_start_page_token()
                        if fresh_token:
                            self._cursor.update(start_page_token=fresh_token)
                    except Exception as token_error:
                        self.logger.warning(
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

        return GoogleDriveFileDeletionEntity.from_api(change)

    async def _build_entity_from_change(
        self,
        change: Dict,
        files: FileService | None = None,
    ) -> Optional[BaseEntity]:
        """Convert a Drive change object into an entity (file or deletion).

        Handles both deletions and modifications/additions. Uses metadata comparison
        to avoid downloading unchanged files during incremental sync.

        Args:
            change: Change object from Google Drive Changes API
            files: Optional file service for downloading changed files

        Returns:
            GoogleDriveFileEntity for changed files, GoogleDriveFileDeletionEntity for deletions,
            or None if file is unchanged or should be skipped
        """
        file_obj = change.get("file") or {}
        removed = change.get("removed", False)
        trashed = bool(file_obj.get("trashed")) or bool(file_obj.get("explicitlyTrashed"))
        change_type = change.get("changeType")

        is_deletion = removed or trashed or (change_type and change_type.lower() == "removed")
        if is_deletion:
            return self._build_deletion_entity_from_change(change)

        if not file_obj.get("id"):
            return None

        if file_obj.get("mimeType") == "application/vnd.google-apps.folder":
            return None

        if not self._has_file_changed(file_obj):
            self.logger.debug(f"File {file_obj.get('name')} unchanged (metadata match) - skipping")
            return None

        self.logger.debug(f"File {file_obj.get('name')} changed - processing")
        return await self._process_changed_file(file_obj, files=files)

    async def _store_next_start_page_token(self) -> None:
        """Persist the next startPageToken for future incremental runs."""
        if not self._cursor:
            return

        next_token = getattr(self, "_latest_new_start_page_token", None)
        if not next_token:
            try:
                next_token = await self._get_start_page_token()
            except Exception as exc:
                self.logger.warning(f"Failed to fetch startPageToken: {exc}")
                return

        if next_token:
            self._cursor.update(start_page_token=next_token)
            self.logger.debug(f"Saved startPageToken for next run: {next_token}")

    async def _list_files(
        self,
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
    ) -> AsyncGenerator[Dict, None]:
        """Generic method to list files with configurable parameters.

        Args:
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

        total_files_from_api = 0
        page_count = 0

        while url:
            try:
                data = await self._get(url, params=params)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error fetching files: {str(e)}")
                break

            files_in_page = data.get("files", [])
            page_count += 1
            files_count = len(files_in_page)
            total_files_from_api += files_count

            self.logger.debug(
                f"Google Drive API returned {files_count} files in page {page_count} ({context})"
            )

            for file_obj in files_in_page:
                yield file_obj

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token
            url = "https://www.googleapis.com/drive/v3/files"

        self.logger.debug(
            f"Google Drive API returned {total_files_from_api} total files across "
            f"{page_count} pages ({context})"
        )

    async def _list_folders(
        self,
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
            data = await self._get(url, params=params)
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
            data = await self._get(url, params=params)
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
        self.logger.debug(f"Resolve pattern: '{pattern}'")
        norm = pattern.strip().strip("/")
        segments = norm.split("/") if norm else []

        if not segments:
            return [], None

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
                        data = await self._get(url, params=params)
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
                    data = await self._get(url, params=params)
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

        parent_ids: Optional[List[str]] = None
        for seg in folder_segments:
            ids = await find_folders_by_name(parent_ids, seg)
            parent_ids = ids
            if not parent_ids:
                break

        if not folder_segments:
            return [], filename_glob or "*"

        self.logger.debug(
            f"Resolved pattern '{pattern}' to {len(parent_ids or [])} folder(s), "
            f"filename_glob={filename_glob}"
        )
        return parent_ids or [], filename_glob

    async def _traverse_and_yield_files(
        self,
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
            async for file_obj in self._list_files_in_folder(
                corpora, include_all_drives, drive_id, folder_id, name_token
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

            async for subfolder in self._list_folders(
                corpora, include_all_drives, drive_id, folder_id
            ):
                self.logger.debug(
                    f"Enqueue subfolder: {subfolder.get('name')} ({subfolder.get('id')})"
                )
                queue.append(subfolder["id"])

    def _build_file_entity(
        self, file_obj: Dict, parent_breadcrumb: Optional[Breadcrumb]
    ) -> Optional[GoogleDriveFileEntity]:
        """Helper to build a GoogleDriveFileEntity from a file API response object.

        Returns None for files that should be skipped (e.g., trashed files, videos).
        """
        mime_type = file_obj.get("mimeType", "")
        if mime_type.startswith("video/"):
            file_name = file_obj.get("name", "unknown")
            self.logger.debug(f"Skipping video file ({mime_type}): {file_name}")
            return None

        MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
        file_size = int(file_obj["size"]) if file_obj.get("size") else 0
        if file_size > MAX_FILE_SIZE_BYTES:
            file_name = file_obj.get("name", "unknown")
            size_mb = file_size / (1024 * 1024)
            self.logger.info(f"Skipping oversized file ({size_mb:.1f}MB, max 200MB): {file_name}")
            return None

        if not mime_type.startswith("application/vnd.google-apps.") and file_obj.get(
            "trashed", False
        ):
            return None

        breadcrumbs = [parent_breadcrumb] if parent_breadcrumb else []
        if not breadcrumbs and getattr(self, "_my_drive_breadcrumb", None):
            breadcrumbs = [self._my_drive_breadcrumb]

        return GoogleDriveFileEntity.from_api(file_obj, breadcrumbs=breadcrumbs)

    # ------------------------------
    # File download helper
    # ------------------------------
    async def _download_file(
        self,
        file_entity: GoogleDriveFileEntity,
        files: FileService | None,
    ) -> bool:
        """Download a file via FileService. Returns True if download succeeded.

        401 propagates (dead token). Other HTTP errors log a warning.
        """
        if not files:
            return False
        try:
            await files.download_from_url(
                entity=file_entity,
                client=self.http_client,
                auth=self.auth,
                logger=self.logger,
            )
            return bool(file_entity.local_path)
        except FileSkippedException as e:
            self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(f"Failed to download {file_entity.name}: {e}")
            return False

    # ------------------------------
    # Concurrency-aware processing
    # ------------------------------
    async def _process_file_batch(
        self,
        file_obj: Dict,
        parent_breadcrumb: Optional[Breadcrumb],
        files: FileService | None = None,
    ) -> Optional[GoogleDriveFileEntity]:
        """Build & process a single file (used by concurrent driver)."""
        try:
            file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
            if not file_entity:
                return None
            self.logger.debug(f"Processing file entity: {file_entity.file_id} '{file_entity.name}'")

            if await self._download_file(file_entity, files):
                self._store_file_metadata(file_obj)
                self.logger.debug(f"Successfully downloaded file: {file_entity.name}")
                return file_entity

            return None

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Failed to process file {file_obj.get('name', 'unknown')}: {str(e)}"
            )
            return None

    async def _process_changed_file(
        self,
        file_obj: Dict,
        parent_breadcrumb: Optional[Breadcrumb] = None,
        files: FileService | None = None,
    ) -> Optional[GoogleDriveFileEntity]:
        """Process a file that has changed based on metadata.

        This method is used during incremental sync to process files that have been
        identified as changed through metadata comparison.

        Args:
            file_obj: File metadata from Google Drive API
            parent_breadcrumb: Optional breadcrumb for parent folder
            files: Optional file service for downloading

        Returns:
            GoogleDriveFileEntity if processing succeeded, None if skipped or failed
        """
        file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
        if not file_entity:
            return None

        self.logger.debug(f"Processing changed file: {file_entity.file_id} '{file_entity.name}'")

        if await self._download_file(file_entity, files):
            self._store_file_metadata(file_obj)
            self.logger.debug(f"Successfully processed changed file: {file_entity.name}")
            return file_entity

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
        corpora: str,
        include_all_drives: bool,
        drive_id: Optional[str] = None,
        context: str = "",
        parent_breadcrumb: Optional[Breadcrumb] = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[GoogleDriveFileEntity, None]:
        """Generate file entities from a file listing."""
        try:
            if getattr(self, "batch_generation", False):

                async def _worker(file_obj: Dict):
                    ent = await self._process_file_batch(file_obj, parent_breadcrumb, files)
                    if ent is not None:
                        yield ent

                async for processed in self.process_entities_concurrent(
                    items=self._list_files(corpora, include_all_drives, drive_id, context),
                    worker=_worker,
                    batch_size=getattr(self, "batch_size", 30),
                    preserve_order=getattr(self, "preserve_order", False),
                    stop_on_error=getattr(self, "stop_on_error", False),
                    max_queue_size=getattr(self, "max_queue_size", 200),
                ):
                    yield processed
            else:
                async for file_obj in self._list_files(
                    corpora, include_all_drives, drive_id, context
                ):
                    try:
                        file_entity = self._build_file_entity(file_obj, parent_breadcrumb)
                        if not file_entity:
                            continue

                        if await self._download_file(file_entity, files):
                            self._store_file_metadata(file_obj)
                            yield file_entity

                    except SourceAuthError:
                        raise
                    except Exception as e:
                        error_context = f"in drive {drive_id}" if drive_id else "in MY DRIVE"
                        self.logger.warning(
                            f"Failed to process file {file_obj.get('name', 'unknown')} "
                            f"{error_context}: {str(e)}"
                        )
                        continue

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Critical exception in _generate_file_entities: {str(e)}")

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Google Drive entities.

        Behavior:
        - If no cursor token exists: perform a FULL sync (shared drives + files), then store
          the current startPageToken for the next incremental run.
        - If a cursor token exists: perform INCREMENTAL sync using the Changes API. Emit
          deletion entities for removed files and upsert entities for changed files.
        """
        self._cursor = cursor

        try:
            start_page_token = self._get_cursor_start_page_token()
            if start_page_token:
                self.logger.debug(f"Incremental sync using startPageToken={start_page_token}")
            else:
                self.logger.debug("Full sync (no stored startPageToken)")

            patterns: List[str] = getattr(self, "include_patterns", []) or []
            self.logger.debug(f"Include patterns: {patterns}")

            drive_id_filter: Optional[str] = self.drive_id_filter

            drive_objs: List[Dict[str, Any]] = []
            try:
                async for drive_obj in self._list_drives():
                    if drive_id_filter and drive_obj.get("id") != drive_id_filter:
                        continue
                    drive_objs.append(drive_obj)
                    yield self._build_drive_entity(drive_obj)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error generating drive entities: {str(e)}")

            if drive_id_filter and not drive_objs:
                self.logger.warning(
                    f"Configured drive_id '{drive_id_filter}' was not found among the shared "
                    "drives accessible to this account. Nothing will be synced. Verify the "
                    "drive ID and that the authenticated user has access."
                )

            self._setup_breadcrumbs(drive_objs)
            drive_breadcrumbs = self._drive_breadcrumbs
            drive_ids = [drive["id"] for drive in drive_objs]

            # INCREMENTAL MODE: Use Changes API exclusively
            if start_page_token:
                self.logger.info(
                    "Incremental sync mode - processing changes only"
                    f" (token={start_page_token[:20]}...)"
                )
                async for change_entity in self._emit_changes_since_token(
                    start_page_token, files=files
                ):
                    yield change_entity

            else:
                # FULL SYNC MODE: List all files (first run or forced full sync)
                self.logger.info("Full sync mode - listing all files")

                # If no include patterns: default behavior (all files in drives + My Drive)
                if not patterns:
                    for drive_id in drive_ids:
                        try:
                            drive_breadcrumb = drive_breadcrumbs.get(drive_id)
                            async for file_entity in self._generate_file_entities(
                                corpora="drive",
                                include_all_drives=True,
                                drive_id=drive_id,
                                context=f"drive {drive_id}",
                                parent_breadcrumb=drive_breadcrumb,
                                files=files,
                            ):
                                yield file_entity
                        except SourceAuthError:
                            raise
                        except Exception as e:
                            self.logger.warning(
                                f"Error processing shared drive {drive_id}: {str(e)}"
                            )
                            continue

                    if not drive_id_filter:
                        try:
                            async for mydrive_file_entity in self._generate_file_entities(
                                corpora="user",
                                include_all_drives=False,
                                context="MY DRIVE",
                                parent_breadcrumb=self._my_drive_breadcrumb,
                                files=files,
                            ):
                                yield mydrive_file_entity
                        except SourceAuthError:
                            raise
                        except Exception as e:
                            self.logger.warning(f"Error processing My Drive files: {str(e)}")

                # INCLUDE MODE: Resolve patterns and traverse only matched subtrees
                # Shared drives first
                for drive_id in drive_ids:
                    try:
                        drive_breadcrumb = drive_breadcrumbs.get(drive_id)
                        for p in patterns:
                            roots, fname_glob = await self._resolve_pattern_to_roots(
                                corpora="drive",
                                include_all_drives=True,
                                drive_id=drive_id,
                                pattern=p,
                            )
                            if roots:
                                if getattr(self, "batch_generation", False):

                                    async def _worker_traverse(
                                        file_obj: Dict, breadcrumb=drive_breadcrumb
                                    ):
                                        ent = await self._process_file_batch(
                                            file_obj, breadcrumb, files
                                        )
                                        if ent is not None:
                                            yield ent

                                    items_gen = self._traverse_and_yield_files(
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
                                    async for file_obj in self._traverse_and_yield_files(
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

                                        try:
                                            if await self._download_file(file_entity, files):
                                                yield file_entity
                                        except SourceAuthError:
                                            raise
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Download failed {file_entity.name}: {e}"
                                            )
                                            continue

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
                                            file_obj, breadcrumb, files
                                        )
                                        if ent is not None:
                                            yield ent

                                async for processed in self.process_entities_concurrent(
                                    items=self._list_files(
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

                                        try:
                                            if await self._download_file(file_entity, files):
                                                yield file_entity
                                        except SourceAuthError:
                                            raise
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Download failed {file_entity.name}: {e}"
                                            )
                                            continue

                    except SourceAuthError:
                        raise
                    except Exception as e:
                        self.logger.warning(f"Include mode error for drive {drive_id}: {str(e)}")

                # My Drive include patterns (skipped when scoped to a specific shared drive)
                try:
                    if drive_id_filter:
                        patterns_for_mydrive: List[str] = []
                    else:
                        patterns_for_mydrive = patterns
                    for p in patterns_for_mydrive:
                        roots, fname_glob = await self._resolve_pattern_to_roots(
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
                                    ent = await self._process_file_batch(
                                        file_obj, breadcrumb, files
                                    )
                                    if ent is not None:
                                        yield ent

                                items_gen_user = self._traverse_and_yield_files(
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

                                    try:
                                        if await self._download_file(file_entity, files):
                                            yield file_entity
                                    except SourceAuthError:
                                        raise
                                    except Exception as e:
                                        self.logger.warning(
                                            f"Failed to download file {file_entity.name}: {e}"
                                        )
                                        continue

                    filename_only_patterns = [p for p in patterns_for_mydrive if "/" not in p]
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
                                    ent = await self._process_file_batch(
                                        file_obj, breadcrumb, files
                                    )
                                    if ent is not None:
                                        yield ent

                            async for processed in self.process_entities_concurrent(
                                items=self._list_files(
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

                                    try:
                                        if await self._download_file(file_entity, files):
                                            yield file_entity
                                    except SourceAuthError:
                                        raise
                                    except Exception as e:
                                        self.logger.warning(
                                            f"Failed to download file {file_entity.name}: {e}"
                                        )
                                        continue

                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Include mode error for My Drive: {str(e)}")

            # Store the next start page token for future incremental syncs
            await self._store_next_start_page_token()

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Critical error in generate_entities: {str(e)}")
            from airweave.domains.sync_pipeline.exceptions import SyncFailureError

            raise SyncFailureError(f"Google Drive sync failed: {str(e)}") from e
