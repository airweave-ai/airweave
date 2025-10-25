"""Google Sheets source implementation.

Retrieves data from a user's Google Sheets (read-only mode):
  - Spreadsheets from Google Drive (filtered by MIME type)
  - Spreadsheet metadata and content

Follows the same structure and pattern as other Google connector implementations
(e.g., Google Docs, Google Drive, Google Calendar). The entity schemas are defined in
entities/google_sheets.py.

Mirrors the Google Drive connector approach - treats Google Sheets spreadsheets as
regular files that get processed through Airweave's file processing pipeline.

Reference:
    https://developers.google.com/drive/api/v3/reference/files
    https://developers.google.com/sheets/api/reference/rest
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.google_sheets import GoogleSheetsSpreadsheetEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Google Sheets",
    short_name="google_sheets",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
        AuthenticationMethod.OAUTH_BYOC,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class="GoogleSheetsConfig",
    labels=["Productivity", "Spreadsheets"],
    supports_continuous=True,
)
class GoogleSheetsSource(BaseSource):
    """Google Sheets source connector integrates with Google Drive API.

    Connects to your Google Drive account to retrieve Google Sheets spreadsheets.
    Spreadsheets are exported as Excel and processed through Airweave's file
    processing pipeline to enable full-text semantic search across spreadsheet content.

    Mirrors the Google Drive connector approach - treats Google Sheets spreadsheets as
    regular files that get processed through the standard file processing pipeline.

    The connector handles:
    - Spreadsheet listing and filtering via Google Drive API
    - Content export and download (Excel format)
    - Metadata preservation (ownership, sharing, timestamps)
    - Incremental sync via Drive Changes API
    """

    # -----------------------
    # Construction / Config
    # -----------------------
    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleSheetsSource":
        """Create a new Google Sheets source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token

        # Configuration options
        config = config or {}
        instance.include_trashed = bool(config.get("include_trashed", False))
        instance.include_shared = bool(config.get("include_shared", True))

        return instance

    # -----------------------
    # HTTP helpers
    # -----------------------
    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True
    )
    async def _make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to Google APIs."""
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()

    # -----------------------
    # Validation
    # -----------------------
    async def validate(self) -> bool:
        """Validate the Google Sheets source connection."""
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/drive/v3/files?pageSize=1&q=mimeType='application/vnd.google-apps.spreadsheet'",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    # --- Incremental sync support (cursor field) ---
    def get_default_cursor_field(self) -> Optional[str]:
        """Return the default cursor field for incremental sync."""
        return "modified_time"

    # -----------------------
    # Data generation
    # -----------------------
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Google Sheets entities."""
        async for spreadsheet in self._fetch_spreadsheets():
            # Process the file entity (download and set local_path)
            processed_entity = await self.process_file_entity(
                file_entity=spreadsheet,
                access_token=await self.get_access_token(),
            )
            if processed_entity:
                yield processed_entity

    # -----------------------
    # Spreadsheet fetching
    # -----------------------
    async def _fetch_spreadsheets(self) -> AsyncGenerator[GoogleSheetsSpreadsheetEntity, None]:
        """Fetch Google Sheets spreadsheets from Google Drive."""
        query = self._build_spreadsheet_query()
        page_token = None

        while True:
            params = self._build_request_params(query, page_token)
            response = await self._make_spreadsheet_request(params)
            if not response:
                break

            files = response.get("files", [])
            if not files:
                break

            async for spreadsheet in self._process_spreadsheet_files(files):
                yield spreadsheet

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def _build_spreadsheet_query(self) -> str:
        """Build query for Google Sheets spreadsheets."""
        query_parts = ["mimeType='application/vnd.google-apps.spreadsheet'"]

        if not self.include_trashed:
            query_parts.append("trashed=false")

        if not self.include_shared:
            query_parts.append("'me' in owners")

        return " and ".join(query_parts)

    def _build_request_params(self, query: str, page_token: Optional[str]) -> Dict[str, Any]:
        """Build request parameters for Drive API."""
        params = {
            "q": query,
            "fields": (
                "nextPageToken,files(id,name,description,starred,trashed,"
                "explicitlyTrashed,shared,sharedWithMeTime,sharingUser,owners,"
                "permissions,parents,webViewLink,iconLink,createdTime,"
                "modifiedTime,modifiedByMeTime,viewedByMeTime,size,version)"
            ),
            "pageSize": 100,
            "orderBy": "modifiedTime desc",
        }

        if page_token:
            params["pageToken"] = page_token

        return params

    async def _make_spreadsheet_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make request to Drive API for spreadsheets."""
        try:
            return await self._make_request(
                "https://www.googleapis.com/drive/v3/files", params=params
            )
        except Exception as e:
            self.logger.error(f"Failed to fetch spreadsheets: {e}")
            return None

    async def _process_spreadsheet_files(
        self, files: List[Dict[str, Any]]
    ) -> AsyncGenerator[GoogleSheetsSpreadsheetEntity, None]:
        """Process spreadsheet files and yield entities."""
        for file_data in files:
            try:
                spreadsheet = await self._create_spreadsheet_entity(file_data)
                if spreadsheet:
                    yield spreadsheet
            except Exception as e:
                self.logger.error(f"Failed to create spreadsheet entity: {e}")
                continue

    async def _create_spreadsheet_entity(
        self, file_data: Dict[str, Any]
    ) -> Optional[GoogleSheetsSpreadsheetEntity]:
        """Create a GoogleSheetsSpreadsheetEntity from Drive API file data."""
        try:
            # Use standard Google Drive export URL (mirrors Google Drive connector)
            file_id = file_data["id"]
            download_url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                f"?mimeType=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Parse timestamps
            created_time = None
            if file_data.get("createdTime"):
                created_time = datetime.fromisoformat(
                    file_data["createdTime"].replace("Z", "+00:00")
                )

            modified_time = None
            if file_data.get("modifiedTime"):
                modified_time = datetime.fromisoformat(
                    file_data["modifiedTime"].replace("Z", "+00:00")
                )

            modified_by_me_time = None
            if file_data.get("modifiedByMeTime"):
                modified_by_me_time = datetime.fromisoformat(
                    file_data["modifiedByMeTime"].replace("Z", "+00:00")
                )

            viewed_by_me_time = None
            if file_data.get("viewedByMeTime"):
                viewed_by_me_time = datetime.fromisoformat(
                    file_data["viewedByMeTime"].replace("Z", "+00:00")
                )

            shared_with_me_time = None
            if file_data.get("sharedWithMeTime"):
                shared_with_me_time = datetime.fromisoformat(
                    file_data["sharedWithMeTime"].replace("Z", "+00:00")
                )

            # Create breadcrumbs
            breadcrumbs = []
            if file_data.get("parents"):
                # Add parent folder breadcrumbs (simplified)
                breadcrumbs.append(Breadcrumb(entity_id="root", name="Google Drive", type="folder"))

            return GoogleSheetsSpreadsheetEntity(
                entity_id=file_id,
                file_id=file_id,
                name=file_data.get("name", "Untitled Spreadsheet"),
                title=file_data.get("name", "Untitled Spreadsheet"),
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Standard Excel export
                description=file_data.get("description"),
                starred=file_data.get("starred", False),
                trashed=file_data.get("trashed", False),
                explicitly_trashed=file_data.get("explicitlyTrashed", False),
                shared=file_data.get("shared", False),
                shared_with_me_time=shared_with_me_time,
                sharing_user=file_data.get("sharingUser"),
                owners=file_data.get("owners", []),
                permissions=file_data.get("permissions"),
                parents=file_data.get("parents", []),
                web_view_link=file_data.get("webViewLink"),
                icon_link=file_data.get("iconLink"),
                created_time=created_time,
                modified_time=modified_time,
                modified_by_me_time=modified_by_me_time,
                viewed_by_me_time=viewed_by_me_time,
                size=file_data.get("size"),
                version=file_data.get("version"),
                export_mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Standard Excel export
                download_url=download_url,
                breadcrumbs=breadcrumbs,
                url=file_data.get("webViewLink"),
            )

        except Exception as e:
            self.logger.error(f"Error creating spreadsheet entity: {e}")
            return None
