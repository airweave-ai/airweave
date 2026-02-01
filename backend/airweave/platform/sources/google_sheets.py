"""Google Sheets source implementation.

Retrieves Google Sheets spreadsheets from a user's Google Drive using the Drive and Sheets APIs:
  - Lists all Google Sheets spreadsheets (application/vnd.google-apps.spreadsheet)
  - Fetches spreadsheet metadata and sheet data
  - Extracts cell values for embedding and search

The spreadsheets and sheets are represented as entity objects that get processed through
Airweave's pipeline to create searchable chunks.

References:
    https://developers.google.com/sheets/api/reference/rest
    https://developers.google.com/drive/api/v3/reference/files
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.cursors import GoogleSheetsCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_sheets import (
    GoogleSheetsSheetEntity,
    GoogleSheetsSpreadsheetEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

# API endpoints
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"


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
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=GoogleSheetsCursor,
)
class GoogleSheetsSource(BaseSource):
    """Google Sheets source connector integrates with Google Sheets API to extract spreadsheets.

    Connects to your Google Drive account to retrieve Google Sheets spreadsheets.
    Spreadsheets and their sheets are processed through Airweave's pipeline to enable
    full-text semantic search across spreadsheet content.

    The connector handles:
    - Spreadsheet listing and filtering
    - Sheet metadata extraction
    - Cell data extraction for embedding
    - Incremental sync via Drive Changes API
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleSheetsSource":
        """Create a new Google Sheets source instance with the provided OAuth access token.

        Args:
            access_token: OAuth2 access token for Google APIs
            config: Optional configuration dict with:
                - include_trashed: Include trashed spreadsheets (default: False)
                - include_shared: Include shared spreadsheets (default: True)
                - max_rows_per_sheet: Maximum rows to read per sheet (default: 10000)
                - batch_size: Number of spreadsheets to process concurrently (default: 30)

        Returns:
            Configured GoogleSheetsSource instance
        """
        instance = cls()
        instance.access_token = access_token

        config = config or {}
        instance.include_trashed = config.get("include_trashed", False)
        instance.include_shared = config.get("include_shared", True)
        instance.max_rows_per_sheet = int(config.get("max_rows_per_sheet", 10000))

        # Concurrency configuration
        instance.batch_size = int(config.get("batch_size", 30))
        instance.batch_generation = bool(config.get("batch_generation", True))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        return instance

    async def validate(self) -> bool:
        """Validate the Google Sheets source connection.

        Tests the connection by making a simple API call to list drives.

        Returns:
            True if connection is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{DRIVE_API}/about?fields=user",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    # --- Incremental sync support (cursor field) ---
    def get_default_cursor_field(self) -> Optional[str]:
        """Default cursor field name for Google Sheets incremental sync.

        Uses the Drive Changes API page token for incremental syncing.

        Returns:
            Cursor field name: "start_page_token"
        """
        return "start_page_token"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate the cursor field for Google Sheets.

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If cursor field is not "start_page_token"
        """
        if cursor_field != "start_page_token":
            raise ValueError(
                f"Google Sheets only supports 'start_page_token' cursor field, got: {cursor_field}"
            )

    async def get_initial_cursor_value(self) -> Dict[str, Any]:
        """Get initial cursor value for incremental sync.

        Retrieves the current start page token from the Drive Changes API.

        Returns:
            Dict with start_page_token for tracking changes
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(
                f"{DRIVE_API}/changes/startPageToken",
                headers=headers,
            )

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    f"{DRIVE_API}/changes/startPageToken",
                    headers=headers,
                )

            response.raise_for_status()
            data = response.json()
            return {"start_page_token": data.get("startPageToken")}

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse RFC3339 timestamps returned by Google APIs."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    # --- Main sync method ---
    async def generate_entities(
        self, existing_cursor_value: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from Google Sheets spreadsheets.

        Args:
            existing_cursor_value: Optional cursor for incremental sync with start_page_token

        Yields:
            GoogleSheetsSpreadsheetEntity and GoogleSheetsSheetEntity objects
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # If we have a cursor, do incremental sync via changes API
            if existing_cursor_value and "start_page_token" in existing_cursor_value:
                start_token = existing_cursor_value["start_page_token"]
                self.logger.debug(f"Starting incremental sync from page token: {start_token}")

                async for entity in self._process_changes(client, start_token):
                    yield entity
            else:
                # Full sync: list all Google Sheets
                self.logger.debug("Starting full sync of Google Sheets")

                async for entity in self._list_and_process_spreadsheets(client):
                    yield entity

    # --- Incremental sync via Changes API ---
    async def _process_changes(
        self, client: httpx.AsyncClient, start_token: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process changes from the Drive Changes API.

        Args:
            client: HTTP client for API requests
            start_token: Starting page token for changes

        Yields:
            Entity objects for changed/new spreadsheets
        """
        url = f"{DRIVE_API}/changes"
        page_token = start_token
        latest_new_start = None

        while page_token:
            params = {
                "pageToken": page_token,
                "pageSize": 100,
                "includeItemsFromAllDrives": "true",
                "supportsAllDrives": "true",
                "fields": "nextPageToken, newStartPageToken, changes(fileId, removed, file(*))",
            }

            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()

            # Process changes
            changes = data.get("changes", [])
            for change in changes:
                file_data = change.get("file")
                removed = change.get("removed", False)

                # Only process Google Sheets files
                if (
                    file_data
                    and file_data.get("mimeType") == "application/vnd.google-apps.spreadsheet"
                ):
                    if not removed and not self._should_filter_spreadsheet(file_data):
                        async for entity in self._process_spreadsheet(client, file_data):
                            yield entity

            # Update pagination
            page_token = data.get("nextPageToken")
            if data.get("newStartPageToken"):
                latest_new_start = data["newStartPageToken"]

            if not page_token:
                break

        # Update cursor for next incremental sync
        if latest_new_start:
            self._latest_new_start_page_token = latest_new_start

    # --- Full sync: list all spreadsheets ---
    async def _list_and_process_spreadsheets(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """List all Google Sheets spreadsheets and create entities.

        Args:
            client: HTTP client for API requests

        Yields:
            Entity objects for each spreadsheet and its sheets
        """
        url = f"{DRIVE_API}/files"

        # Build query to filter for Google Sheets only
        query_parts = ["mimeType = 'application/vnd.google-apps.spreadsheet'"]
        if not self.include_trashed:
            query_parts.append("trashed = false")

        query = " and ".join(query_parts)

        params = {
            "pageSize": 100,
            "corpora": "user",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "q": query,
            "fields": (
                "nextPageToken, files(id, name, mimeType, description, starred, trashed, "
                "explicitlyTrashed, parents, shared, sharedWithMeTime, sharingUser, "
                "owners, permissions, webViewLink, iconLink, createdTime, modifiedTime, "
                "modifiedByMeTime, viewedByMeTime, size, version, capabilities)"
            ),
        }

        page_count = 0
        total_spreadsheets = 0

        while url:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            self.logger.debug(f"Listing spreadsheets page {page_count + 1}")

            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()

            files = data.get("files", [])
            page_count += 1
            total_spreadsheets += len(files)

            self.logger.debug(
                f"Page {page_count}: Found {len(files)} spreadsheets (total: {total_spreadsheets})"
            )

            # Process spreadsheets
            for file_data in files:
                if not self._should_filter_spreadsheet(file_data):
                    async for entity in self._process_spreadsheet(client, file_data):
                        yield entity

            # Check for next page
            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
            else:
                url = None

        self.logger.debug(
            f"Completed spreadsheet listing: {total_spreadsheets} total spreadsheets found"
        )

    def _should_filter_spreadsheet(self, file_data: Dict[str, Any]) -> bool:
        """Determine if a spreadsheet should be filtered out.

        Args:
            file_data: File metadata from Drive API

        Returns:
            True if spreadsheet should be filtered, False otherwise
        """
        # Filter trashed spreadsheets if configured
        if not self.include_trashed and file_data.get("trashed", False):
            return True

        # Filter shared spreadsheets if configured
        if not self.include_shared and file_data.get("shared", False):
            return True

        return False

    async def _process_spreadsheet(
        self, client: httpx.AsyncClient, file_data: Dict[str, Any]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single spreadsheet and generate entities.

        Args:
            client: HTTP client for API requests
            file_data: File metadata from Drive API

        Yields:
            GoogleSheetsSpreadsheetEntity and GoogleSheetsSheetEntity objects
        """
        try:
            spreadsheet_id = file_data["id"]
            spreadsheet_title = file_data.get("name", "Untitled Spreadsheet")

            # Parse timestamps
            created_time = self._parse_datetime(file_data.get("createdTime")) or datetime.utcnow()
            modified_time = self._parse_datetime(file_data.get("modifiedTime")) or created_time

            # Get spreadsheet details from Sheets API
            spreadsheet_data = await self._get_spreadsheet_metadata(client, spreadsheet_id)

            if not spreadsheet_data:
                self.logger.warning(f"Could not fetch spreadsheet metadata for {spreadsheet_id}")
                return

            sheets = spreadsheet_data.get("sheets", [])
            properties = spreadsheet_data.get("properties", {})

            # Create spreadsheet entity
            spreadsheet_entity = GoogleSheetsSpreadsheetEntity(
                breadcrumbs=[],
                spreadsheet_id=spreadsheet_id,
                title=spreadsheet_title,
                created_timestamp=created_time,
                modified_timestamp=modified_time,
                name=spreadsheet_title,
                created_at=created_time,
                updated_at=modified_time,
                locale=properties.get("locale"),
                time_zone=properties.get("timeZone"),
                sheet_count=len(sheets),
                owners=file_data.get("owners", []),
                shared=file_data.get("shared", False),
                web_view_link=file_data.get("webViewLink"),
                web_url_value=file_data.get("webViewLink"),
            )

            yield spreadsheet_entity

            # Create breadcrumb for sheets
            spreadsheet_breadcrumb = Breadcrumb(
                entity_id=spreadsheet_id,
                name=spreadsheet_title,
                entity_type=GoogleSheetsSpreadsheetEntity.__name__,
            )

            # Process each sheet
            for sheet in sheets:
                sheet_entity = await self._create_sheet_entity(
                    client,
                    spreadsheet_id,
                    spreadsheet_title,
                    sheet,
                    created_time,
                    modified_time,
                    spreadsheet_breadcrumb,
                )
                if sheet_entity:
                    yield sheet_entity

        except Exception as e:
            self.logger.error(
                f"Failed to process spreadsheet {file_data.get('id')}: {e}",
                exc_info=True,
            )

    async def _get_spreadsheet_metadata(
        self, client: httpx.AsyncClient, spreadsheet_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch spreadsheet metadata from Sheets API.

        Args:
            client: HTTP client for API requests
            spreadsheet_id: ID of the spreadsheet

        Returns:
            Spreadsheet metadata dict or None if failed
        """
        try:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(
                f"{SHEETS_API}/spreadsheets/{spreadsheet_id}",
                headers=headers,
                params={"fields": "properties,sheets.properties"},
            )

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    f"{SHEETS_API}/spreadsheets/{spreadsheet_id}",
                    headers=headers,
                    params={"fields": "properties,sheets.properties"},
                )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to fetch spreadsheet metadata: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching spreadsheet metadata: {e}")
            return None

    async def _create_sheet_entity(
        self,
        client: httpx.AsyncClient,
        spreadsheet_id: str,
        spreadsheet_title: str,
        sheet: Dict[str, Any],
        created_time: datetime,
        modified_time: datetime,
        spreadsheet_breadcrumb: Breadcrumb,
    ) -> Optional[GoogleSheetsSheetEntity]:
        """Create a GoogleSheetsSheetEntity from sheet metadata.

        Args:
            client: HTTP client for API requests
            spreadsheet_id: ID of the parent spreadsheet
            spreadsheet_title: Title of the parent spreadsheet
            sheet: Sheet metadata from Sheets API
            created_time: Spreadsheet creation time
            modified_time: Spreadsheet modification time
            spreadsheet_breadcrumb: Breadcrumb for the parent spreadsheet

        Returns:
            GoogleSheetsSheetEntity or None if creation fails
        """
        try:
            props = sheet.get("properties", {})
            sheet_id = str(props.get("sheetId", 0))
            sheet_title = props.get("title", "Sheet")
            sheet_type = props.get("sheetType", "GRID")
            sheet_index = props.get("index", 0)
            hidden = props.get("hidden", False)

            # Get grid properties
            grid_props = props.get("gridProperties", {})
            row_count = grid_props.get("rowCount", 0)
            column_count = grid_props.get("columnCount", 0)
            frozen_row_count = grid_props.get("frozenRowCount", 0)
            frozen_column_count = grid_props.get("frozenColumnCount", 0)

            # Create composite entity ID
            entity_id = f"{spreadsheet_id}:{sheet_id}"

            # Fetch cell data for this sheet
            cell_data, headers_list, data_preview = await self._get_sheet_data(
                client, spreadsheet_id, sheet_title
            )

            entity = GoogleSheetsSheetEntity(
                breadcrumbs=[spreadsheet_breadcrumb],
                sheet_id=entity_id,
                sheet_title=sheet_title,
                created_timestamp=created_time,
                modified_timestamp=modified_time,
                name=f"{spreadsheet_title} - {sheet_title}",
                created_at=created_time,
                updated_at=modified_time,
                spreadsheet_id=spreadsheet_id,
                spreadsheet_title=spreadsheet_title,
                sheet_index=sheet_index,
                sheet_type=sheet_type,
                row_count=row_count,
                column_count=column_count,
                frozen_row_count=frozen_row_count,
                frozen_column_count=frozen_column_count,
                hidden=hidden,
                headers=headers_list,
                data_preview=data_preview,
                cell_data=cell_data,
                web_url_value=(
                    f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={sheet_id}"
                ),
            )

            return entity

        except Exception as e:
            self.logger.error(
                f"Failed to create sheet entity: {e}",
                exc_info=True,
            )
            return None

    async def _get_sheet_data(
        self, client: httpx.AsyncClient, spreadsheet_id: str, sheet_title: str
    ) -> tuple[Optional[str], List[str], Optional[str]]:
        """Fetch cell data from a sheet.

        Args:
            client: HTTP client for API requests
            spreadsheet_id: ID of the spreadsheet
            sheet_title: Title of the sheet

        Returns:
            Tuple of (cell_data_text, headers_list, data_preview)
        """
        try:
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            # Fetch values from the sheet
            # Use A1 notation with max_rows limit
            range_notation = f"'{sheet_title}'!A1:ZZ{self.max_rows_per_sheet}"

            response = await client.get(
                f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                headers=headers,
                params={"valueRenderOption": "FORMATTED_VALUE"},
            )

            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/{range_notation}",
                    headers=headers,
                    params={"valueRenderOption": "FORMATTED_VALUE"},
                )

            if response.status_code != 200:
                self.logger.warning(f"Failed to fetch sheet data: {response.status_code}")
                return None, [], None

            data = response.json()
            values = data.get("values", [])

            if not values:
                return None, [], None

            # First row as headers
            headers_list = [str(cell) for cell in values[0]] if values else []

            # Format data as text for embedding
            lines = []
            for row_idx, row in enumerate(values):
                if row_idx == 0:
                    # Header row
                    lines.append("Headers: " + " | ".join(str(cell) for cell in row))
                else:
                    # Data row - format as "Column: Value" pairs
                    row_parts = []
                    for col_idx, cell in enumerate(row):
                        col_name = (
                            headers_list[col_idx]
                            if col_idx < len(headers_list)
                            else f"Col{col_idx + 1}"
                        )
                        row_parts.append(f"{col_name}: {cell}")
                    lines.append(" | ".join(row_parts))

            cell_data = "\n".join(lines)

            # Create a preview (first 5 rows)
            preview_lines = lines[:6] if len(lines) >= 6 else lines
            data_preview = "\n".join(preview_lines)

            return cell_data, headers_list, data_preview

        except Exception as e:
            self.logger.error(f"Error fetching sheet data: {e}")
            return None, [], None
