"""Google Sheets source implementation.

Retrieves data from Google Sheets:
  - Spreadsheets (from Google Drive)
  - Worksheets within spreadsheets
  - Cell data from worksheets

References:
    https://developers.google.com/sheets/api/reference/rest
    https://developers.google.com/drive/api/v3/reference/files/list
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_sheets import (
    GoogleSheetsSpreadsheetEntity,
    GoogleSheetsWorksheetEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType
from pydantic import BaseModel, Field


class GoogleSheetsCursor(BaseModel):
    """Cursor for Google Sheets incremental sync."""

    next_page_token: Optional[str] = Field(None, description="Next page token for initial list")
    start_page_token: Optional[str] = Field(None, description="Start page token for changes API")


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
    cursor_class=GoogleSheetsCursor,
    labels=["Spreadsheet", "Productivity"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
)
class GoogleSheetsSource(BaseSource):
    """Google Sheets source connector."""

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleSheetsSource":
        instance = cls()
        instance.access_token = access_token
        config = config or {}
        instance.include_trashed = config.get("include_trashed", False)
        instance.include_shared = config.get("include_shared", True)
        return instance

    async def validate(self) -> bool:
        """Validate connection by listing a single file."""
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/drive/v3/files?pageSize=1&q=mimeType='application/vnd.google-apps.spreadsheet'",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Authenticated GET request with retry logic."""
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            
            if response.status_code == 401:
                await self.refresh_on_unauthorized()
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params, timeout=30.0)

            if response.status_code == 429:
                import asyncio
                retry_after = int(response.headers.get("Retry-After", 60))
                await asyncio.sleep(retry_after)
                response = await client.get(url, headers=headers, params=params, timeout=30.0)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"API request failed: {url} - {str(e)}")
            raise

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def generate_entities(
        self, existing_cursor_value: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for Google Sheets."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            async for spreadsheet in self._list_spreadsheets(client):
                yield spreadsheet
                async for worksheet in self._process_spreadsheet(client, spreadsheet):
                    yield worksheet

    async def _list_spreadsheets(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GoogleSheetsSpreadsheetEntity, None]:
        """List all Google Sheets files from Drive."""
        url = "https://www.googleapis.com/drive/v3/files"
        query = "mimeType = 'application/vnd.google-apps.spreadsheet'"
        if not self.include_trashed:
            query += " and trashed = false"

        params = {
            "q": query,
            "pageSize": 100,
            "fields": "nextPageToken, files(id, name, createdTime, modifiedTime, owners, webViewLink)",
        }

        while url:
            data = await self._get_with_auth(client, url, params=params)
            files = data.get("files", [])

            for f in files:
                yield GoogleSheetsSpreadsheetEntity(
                    breadcrumbs=[],
                    spreadsheet_id=f["id"],
                    title=f.get("name", "Untitled Spreadsheet"),
                    created_time=self._parse_datetime(f.get("createdTime")),
                    modified_time=self._parse_datetime(f.get("modifiedTime")),
                    owner=f.get("owners", [{}])[0].get("emailAddress"),
                    url=f.get("webViewLink"),
                    name=f.get("name", "Untitled Spreadsheet"), # Required base field
                )

            next_token = data.get("nextPageToken")
            if not next_token:
                break
            params["pageToken"] = next_token

    async def _process_spreadsheet(
        self, client: httpx.AsyncClient, spreadsheet: GoogleSheetsSpreadsheetEntity
    ) -> AsyncGenerator[GoogleSheetsWorksheetEntity, None]:
        """Fetch sheets and content for a specific spreadsheet."""
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.spreadsheet_id}"
        
        try:
            data = await self._get_with_auth(client, url)
            sheets = data.get("sheets", [])
            sheet_title = data.get("properties", {}).get("title", spreadsheet.title)

            spreadsheet_breadcrumb = Breadcrumb(
                entity_id=spreadsheet.spreadsheet_id,
                name=sheet_title,
                entity_type="google_sheet_spreadsheet",
            )

            for sheet in sheets:
                props = sheet.get("properties", {})
                sheet_id = props.get("sheetId")
                title = props.get("title")
                
                # Fetch values
                values_url = f"{url}/values/{title}"
                try:
                    values_data = await self._get_with_auth(client, values_url)
                    rows = values_data.get("values", [])
                    
                    # Format as text
                    formatted_text = ""
                    for i, row in enumerate(rows):
                        formatted_text += f"Row {i+1}: {' | '.join(str(c) for c in row)}\n"

                    yield GoogleSheetsWorksheetEntity(
                        breadcrumbs=[spreadsheet_breadcrumb],
                        spreadsheet_id=spreadsheet.spreadsheet_id,
                        sheet_id=sheet_id,
                        title=title,
                        index=props.get("index"),
                        row_count=props.get("gridProperties", {}).get("rowCount"),
                        column_count=props.get("gridProperties", {}).get("columnCount"),
                        values=formatted_text,
                        url=f"{spreadsheet.url}#gid={sheet_id}",
                        name=f"{sheet_title} - {title}", # Unique name
                    )

                except Exception as e:
                    self.logger.warning(f"Failed to fetch values for sheet {title}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to process spreadsheet {spreadsheet.spreadsheet_id}: {e}")
