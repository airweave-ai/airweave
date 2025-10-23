"""Microsoft Excel source implementation.

Retrieves data from Microsoft Excel, including:
 - Workbooks (Excel files the user has access to)
 - Worksheets within workbooks
 - Tables within worksheets (structured data)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/excel
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
  https://learn.microsoft.com/en-us/graph/api/workbook-list-worksheets
  https://learn.microsoft.com/en-us/graph/api/worksheet-list-tables
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.excel import (
    ExcelTableEntity,
    ExcelWorkbookEntity,
    ExcelWorksheetEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Microsoft Excel",
    short_name="excel",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="ExcelConfig",
    labels=["Productivity", "Spreadsheet", "Data Analysis"],
    supports_continuous=False,
)
class ExcelSource(BaseSource):
    """Microsoft Excel source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft Excel including workbooks, worksheets, and tables.

    It provides comprehensive access to Excel resources with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ExcelSource":
        """Create a new Microsoft Excel source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Microsoft Graph API
            config: Optional configuration parameters

        Returns:
            Configured ExcelSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                import asyncio

                await asyncio.sleep(float(retry_after))
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Provide more descriptive error messages for common OAuth scope issues
            error_msg = self._get_descriptive_error_message(url, str(e))
            self.logger.error(f"Error in API request to {url}: {error_msg}")
            raise

    def _get_descriptive_error_message(self, url: str, error: str) -> str:
        """Get descriptive error message for common OAuth scope issues.

        Args:
            url: The API URL that failed
            error: The original error message

        Returns:
            Enhanced error message with helpful guidance
        """
        # Check for 401 Unauthorized errors
        if "401" in error or "Unauthorized" in error:
            if "/workbook" in url or "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 Excel API requires specific OAuth scopes. Please ensure your auth "
                    "provider (Composio, Pipedream, etc.) includes the following scopes:\n"
                    "• Files.Read.All - Required to read Excel files from user's drive\n"
                    "• User.Read - Required to access user information\n"
                    "• offline_access - Required for token refresh\n\n"
                    "If using Composio, make sure to add 'Files.Read.All' to your "
                    "OneDrive integration scopes."
                )
            elif "/me" in url and "select=" in url:
                return (
                    f"{error}\n\n"
                    "🔧 User profile access requires the User.Read scope. Please ensure your auth "
                    "provider includes this scope in the OAuth configuration."
                )

        # Check for 403 Forbidden errors
        if "403" in error or "Forbidden" in error:
            if "/workbook" in url or "/drive" in url:
                return (
                    f"{error}\n\n"
                    "🔧 Excel access is forbidden. This usually means:\n"
                    "• The Files.Read.All scope is missing from your OAuth configuration\n"
                    "• The user hasn't granted permission to access Excel files\n"
                    "• The Excel service is not available for this user/tenant\n\n"
                    "Please check your OAuth scopes and user permissions."
                )

        # Return original error if no specific guidance available
        return error

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Microsoft Graph API format.

        Args:
            dt_str: DateTime string from API

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    async def _generate_workbook_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ExcelWorkbookEntity, None]:
        """Generate ExcelWorkbookEntity objects for Excel files in user's drive.

        Lists all files from the user's OneDrive and filters for Excel files.
        Uses list API (more reliable) as primary method, with search as fallback.

        Args:
            client: HTTP client for API requests

        Yields:
            ExcelWorkbookEntity objects
        """
        self.logger.info("Starting workbook entity generation")

        # Use list API as primary method (more reliable than search)
        # This lists all items in the root drive
        url = f"{self.GRAPH_BASE_URL}/me/drive/root/children"
        params = {"$top": 100}

        try:
            workbook_count = 0

            # Try listing root children first (most reliable)
            try:
                self.logger.info(f"Listing files from OneDrive root: {url}")
                data = await self._get_with_auth(client, url, params=params)
                self.logger.info(f"List API returned data with keys: {data.keys()}")
                items_from_list = data.get("value", [])
                self.logger.info(f"List found {len(items_from_list)} items in root")
            except Exception as list_error:
                # If list fails, fall back to search
                self.logger.warning(
                    f"List API failed with error: {list_error}, falling back to search"
                )
                url = f"{self.GRAPH_BASE_URL}/me/drive/root/search(q='.xlsx')"
                self.logger.info(f"Trying fallback search: {url}")
                data = await self._get_with_auth(client, url, params=params)
                self.logger.info(f"Search API returned data with keys: {data.keys()}")

            # Process results
            page_num = 0
            while url:
                page_num += 1
                if "value" not in data:
                    self.logger.error(
                        f"Page {page_num}: No 'value' in response! Keys: {list(data.keys())}"
                    )
                    self.logger.error(f"Full response: {data}")
                    break

                items = data.get("value", [])
                self.logger.info(
                    f"Page {page_num}: Retrieved {len(items)} items from drive "
                    f"(total workbooks so far: {workbook_count})"
                )

                for idx, item_data in enumerate(items):
                    file_name = item_data.get("name", "UNNAMED")
                    item_id = item_data.get("id", "NO_ID")

                    self.logger.info(
                        f"Page {page_num}, Item {idx + 1}/{len(items)}: "
                        f"name='{file_name}', id='{item_id[:20]}...', "
                        f"has_folder={'folder' in item_data}, "
                        f"keys={list(item_data.keys())[:5]}"
                    )

                    # Skip folders
                    if "folder" in item_data:
                        self.logger.info(f"  → Skipping FOLDER: {file_name}")
                        continue

                    # Only process Excel files
                    if not file_name.endswith((".xlsx", ".xlsm", ".xlsb")):
                        self.logger.info(f"  → Skipping NON-EXCEL: {file_name}")
                        continue

                    # This is an Excel file!
                    workbook_count += 1
                    workbook_id = item_data.get("id")
                    self.logger.info(f"  ✓ FOUND EXCEL FILE #{workbook_count}: {file_name}")
                    display_name = file_name.rsplit(".", 1)[0]  # Remove extension

                    self.logger.debug(f"Processing workbook #{workbook_count}: {display_name}")

                    yield ExcelWorkbookEntity(
                        entity_id=workbook_id,
                        breadcrumbs=[],
                        name=display_name,
                        file_name=file_name,
                        web_url=item_data.get("webUrl"),
                        size=item_data.get("size"),
                        created_datetime=self._parse_datetime(item_data.get("createdDateTime")),
                        last_modified_datetime=self._parse_datetime(
                            item_data.get("lastModifiedDateTime")
                        ),
                        created_by=item_data.get("createdBy"),
                        last_modified_by=item_data.get("lastModifiedBy"),
                        parent_reference=item_data.get("parentReference"),
                        drive_id=item_data.get("parentReference", {}).get("driveId"),
                        description=item_data.get("description"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink
                    # Fetch next page
                    data = await self._get_with_auth(client, url, params=params)
                else:
                    break

            if workbook_count == 0:
                self.logger.warning(
                    "⚠️  NO EXCEL FILES FOUND! "
                    "Check that you have .xlsx/.xlsm/.xlsb files in your OneDrive. "
                    "Files may need to be in the root folder or properly indexed for search."
                )
            else:
                self.logger.info(
                    f"✓ Completed workbook generation. Total workbooks found: {workbook_count}"
                )

        except Exception as e:
            self.logger.error(f"Error generating workbook entities: {str(e)}", exc_info=True)
            raise

    async def _generate_worksheet_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        workbook_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ExcelWorksheetEntity, None]:
        """Generate ExcelWorksheetEntity objects for worksheets in a workbook.

        Args:
            client: HTTP client for API requests
            workbook_id: ID of the workbook
            workbook_name: Name of the workbook
            workbook_breadcrumb: Breadcrumb for the workbook

        Yields:
            ExcelWorksheetEntity objects
        """
        self.logger.info(f"Starting worksheet entity generation for workbook: {workbook_name}")
        url = f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
        params = {"$top": 100}

        try:
            worksheet_count = 0
            while url:
                self.logger.debug(f"Fetching worksheets from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                worksheets = data.get("value", [])
                self.logger.info(
                    f"Retrieved {len(worksheets)} worksheets for workbook {workbook_name}"
                )

                for worksheet_data in worksheets:
                    worksheet_count += 1
                    worksheet_id = worksheet_data.get("id")
                    worksheet_name = worksheet_data.get("name", "Unknown Worksheet")

                    self.logger.debug(f"Processing worksheet #{worksheet_count}: {worksheet_name}")

                    # Fetch cell content from the worksheet's used range
                    cell_data = await self._fetch_worksheet_content(
                        client, workbook_id, worksheet_id, worksheet_name
                    )

                    yield ExcelWorksheetEntity(
                        entity_id=worksheet_id,
                        breadcrumbs=[workbook_breadcrumb],
                        workbook_id=workbook_id,
                        workbook_name=workbook_name,
                        name=worksheet_name,
                        position=worksheet_data.get("position"),
                        visibility=worksheet_data.get("visibility"),
                        range_address=cell_data.get("range_address") if cell_data else None,
                        cell_content=cell_data.get("formatted_text") if cell_data else None,
                        row_count=cell_data.get("row_count") if cell_data else None,
                        column_count=cell_data.get("column_count") if cell_data else None,
                        last_modified_datetime=self._parse_datetime(
                            worksheet_data.get("lastModifiedDateTime")
                        ),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.info(
                f"Completed worksheet generation for workbook {workbook_name}. "
                f"Total worksheets: {worksheet_count}"
            )

        except Exception as e:
            self.logger.error(
                f"Error generating worksheet entities for workbook {workbook_name}: {str(e)}"
            )
            # Don't raise - continue with other workbooks

    async def _generate_table_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        worksheet_id: str,
        worksheet_name: str,
        worksheet_breadcrumbs: list[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate table entities for tables in a worksheet.

        Args:
            client: HTTP client for API requests
            workbook_id: ID of the workbook
            workbook_name: Name of the workbook
            worksheet_id: ID of the worksheet
            worksheet_name: Name of the worksheet
            worksheet_breadcrumbs: Breadcrumbs for the worksheet

        Yields:
            ExcelTableEntity objects
        """
        self.logger.info(f"Starting table generation for worksheet: {worksheet_name}")
        url = (
            f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
            f"/workbook/worksheets/{worksheet_id}/tables"
        )
        params = {"$top": 50}

        try:
            table_count = 0
            while url:
                self.logger.debug(f"Fetching tables from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                tables = data.get("value", [])
                self.logger.info(f"Retrieved {len(tables)} tables for worksheet {worksheet_name}")

                for table_data in tables:
                    table_count += 1
                    table_id = table_data.get("id")
                    table_name = table_data.get("name", "Unknown Table")

                    self.logger.debug(f"Processing table #{table_count}: {table_name}")

                    # Fetch table data (rows)
                    table_content = await self._fetch_table_data(
                        client, workbook_id, table_id, table_name
                    )

                    # Get column information
                    columns_url = (
                        f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
                        f"/workbook/tables/{table_id}/columns"
                    )
                    try:
                        columns_data = await self._get_with_auth(client, columns_url)
                        column_names = [
                            col.get("name", "") for col in columns_data.get("value", [])
                        ]
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch columns for table {table_name}: {e}")
                        column_names = []

                    yield ExcelTableEntity(
                        entity_id=table_id,
                        breadcrumbs=worksheet_breadcrumbs,
                        workbook_id=workbook_id,
                        workbook_name=workbook_name,
                        worksheet_id=worksheet_id,
                        worksheet_name=worksheet_name,
                        name=table_name,
                        display_name=table_data.get("displayName"),
                        show_headers=table_data.get("showHeaders"),
                        show_totals=table_data.get("showTotals"),
                        style=table_data.get("style"),
                        highlight_first_column=table_data.get("highlightFirstColumn"),
                        highlight_last_column=table_data.get("highlightLastColumn"),
                        row_count=len(table_content.get("rows", [])) if table_content else None,
                        column_count=len(column_names),
                        column_names=column_names,
                        table_data=table_content.get("formatted_text") if table_content else None,
                        last_modified_datetime=self._parse_datetime(
                            table_data.get("lastModifiedDateTime")
                        ),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.info(
                f"Completed table generation for worksheet {worksheet_name}. "
                f"Total tables: {table_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating tables for worksheet {worksheet_name}: {str(e)}")
            # Don't raise - continue with other worksheets

    async def _fetch_table_data(
        self, client: httpx.AsyncClient, workbook_id: str, table_id: str, table_name: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the actual data from a table.

        Args:
            client: HTTP client for API requests
            workbook_id: ID of the workbook
            table_id: ID of the table
            table_name: Name of the table

        Returns:
            Dictionary containing rows and formatted text representation
        """
        try:
            # Get table rows
            rows_url = (
                f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
                f"/workbook/tables/{table_id}/rows"
            )
            rows_data = await self._get_with_auth(client, rows_url, params={"$top": 100})

            rows = rows_data.get("value", [])

            # Format data as text for embedding
            formatted_lines = []
            for idx, row in enumerate(rows[:100]):  # Limit to first 100 rows
                values = row.get("values", [[]])[0]  # Get first array of values
                row_text = " | ".join(str(v) if v is not None else "" for v in values)
                formatted_lines.append(f"Row {idx + 1}: {row_text}")

            formatted_text = "\n".join(formatted_lines)

            return {"rows": rows, "formatted_text": formatted_text}
        except Exception as e:
            self.logger.warning(f"Failed to fetch data for table {table_name}: {e}")
            return None

    async def _fetch_worksheet_content(
        self, client: httpx.AsyncClient, workbook_id: str, worksheet_id: str, worksheet_name: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the actual cell content from a worksheet's used range.

        Args:
            client: HTTP client for API requests
            workbook_id: ID of the workbook
            worksheet_id: ID of the worksheet
            worksheet_name: Name of the worksheet

        Returns:
            Dictionary containing range address, cell values, and formatted text
        """
        try:
            # Get the used range (cells with data)
            range_url = (
                f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
                f"/workbook/worksheets/{worksheet_id}/usedRange"
            )
            range_data = await self._get_with_auth(client, range_url)

            # Extract range information
            address = range_data.get("address", "")
            values = range_data.get("values", [])
            row_count = range_data.get("rowCount", 0)
            column_count = range_data.get("columnCount", 0)

            # Limit the data we extract (max 200 rows to prevent huge entities)
            max_rows = min(200, len(values))
            limited_values = values[:max_rows]

            # Format data as text for embedding
            formatted_lines = []
            for row_idx, row in enumerate(limited_values):
                # Convert each cell value to string
                row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                # Only add non-empty rows
                if row_text.strip().replace("|", "").strip():
                    formatted_lines.append(f"Row {row_idx + 1}: {row_text}")

            formatted_text = "\n".join(formatted_lines)

            # Only return content if there's actual data
            if formatted_text.strip():
                return {
                    "range_address": address,
                    "formatted_text": formatted_text,
                    "row_count": row_count,
                    "column_count": column_count,
                }
            else:
                self.logger.debug(f"Worksheet {worksheet_name} has no content in used range")
                return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Worksheet might be empty
                self.logger.debug(f"Worksheet {worksheet_name} has no used range (empty sheet)")
                return None
            else:
                self.logger.warning(
                    f"Failed to fetch content for worksheet {worksheet_name}: "
                    f"HTTP {e.response.status_code}"
                )
                return None
        except Exception as e:
            self.logger.warning(f"Failed to fetch content for worksheet {worksheet_name}: {e}")
            return None

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Microsoft Excel entities.

        Yields entities in the following order:
          - ExcelWorkbookEntity for user's Excel workbooks
          - ExcelWorksheetEntity for worksheets in each workbook
          - ExcelTableEntity for tables in each worksheet
        """
        self.logger.info("===== STARTING MICROSOFT EXCEL ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # 1) Generate workbook entities
                self.logger.info("Generating workbook entities...")
                async for workbook_entity in self._generate_workbook_entities(client):
                    entity_count += 1
                    self.logger.info(
                        f"Yielding entity #{entity_count}: Workbook - {workbook_entity.name}"
                    )
                    yield workbook_entity

                    # Create workbook breadcrumb
                    workbook_id = workbook_entity.entity_id
                    workbook_name = workbook_entity.name
                    workbook_breadcrumb = Breadcrumb(
                        entity_id=workbook_id, name=workbook_name[:50], type="workbook"
                    )

                    # 2) Generate worksheet entities for this workbook
                    async for worksheet_entity in self._generate_worksheet_entities(
                        client, workbook_id, workbook_name, workbook_breadcrumb
                    ):
                        entity_count += 1
                        self.logger.info(
                            f"Yielding entity #{entity_count}: Worksheet - {worksheet_entity.name}"
                        )
                        yield worksheet_entity

                        # Create worksheet breadcrumb
                        worksheet_id = worksheet_entity.entity_id
                        worksheet_name = worksheet_entity.name
                        worksheet_breadcrumb = Breadcrumb(
                            entity_id=worksheet_id, name=worksheet_name[:50], type="worksheet"
                        )
                        worksheet_breadcrumbs = [workbook_breadcrumb, worksheet_breadcrumb]

                        # 3) Generate table entities for this worksheet
                        async for table_entity in self._generate_table_entities(
                            client,
                            workbook_id,
                            workbook_name,
                            worksheet_id,
                            worksheet_name,
                            worksheet_breadcrumbs,
                        ):
                            entity_count += 1
                            self.logger.info(
                                f"Yielding entity #{entity_count}: Table - {table_entity.name}"
                            )
                            yield table_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT EXCEL ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Microsoft Excel OAuth2 token by pinging the drive endpoint.

        Returns:
            True if token is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/drive?$select=id",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
