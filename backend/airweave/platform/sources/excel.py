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

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.excel import (
    ExcelTableEntity,
    ExcelWorkbookEntity,
    ExcelWorksheetEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Excel",
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
    supports_temporal_relevance=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class ExcelSource(BaseSource):
    """Microsoft Excel source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft Excel including workbooks, worksheets, and tables.

    It provides comprehensive access to Excel resources with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    # Configuration constants for optimization
    MAX_WORKSHEET_ROWS = 200  # Limit rows per worksheet to prevent huge entities
    MAX_TABLE_ROWS = 100  # Limit rows per table
    PAGE_SIZE_DRIVE = 250  # Optimal page size for drive items
    PAGE_SIZE_WORKSHEETS = 250  # Optimal page size for worksheets
    PAGE_SIZE_TABLES = 100  # Optimal page size for tables
    MAX_FOLDER_DEPTH = 5  # Limit recursive folder traversal depth
    CONCURRENT_WORKSHEET_FETCH = 5  # Concurrent worksheet content fetches

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
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
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

    async def _discover_excel_files_recursive(  # noqa: C901
        self, client: httpx.AsyncClient, folder_id: Optional[str] = None, depth: int = 0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively discover Excel files in drive folders.

        Args:
            client: HTTP client for API requests
            folder_id: ID of folder to search (None for root)
            depth: Current recursion depth

        Yields:
            DriveItem dictionaries for Excel files
        """
        if depth > self.MAX_FOLDER_DEPTH:
            self.logger.debug(f"Max folder depth {self.MAX_FOLDER_DEPTH} reached, skipping")
            return

        # Build URL for folder or root
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/me/drive/root/children"

        params = {"$top": self.PAGE_SIZE_DRIVE}

        try:
            # Process all pages in this folder
            while url:
                data = await self._get_with_auth(client, url, params=params)
                items = data.get("value", [])

                folders_to_traverse = []

                for item in items:
                    file_name = item.get("name", "")

                    # Check if it's an Excel file
                    if file_name.endswith((".xlsx", ".xlsm", ".xlsb")):
                        yield item

                    # Collect folders for recursive traversal
                    elif "folder" in item:
                        folders_to_traverse.append(item.get("id"))

                # Recursively process subfolders
                for subfolder_id in folders_to_traverse:
                    async for excel_file in self._discover_excel_files_recursive(
                        client, subfolder_id, depth + 1
                    ):
                        yield excel_file

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    params = None  # nextLink includes params

        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {str(e)}")

    async def _generate_workbook_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ExcelWorkbookEntity, None]:
        """Generate ExcelWorkbookEntity objects for Excel files in user's drive.

        Recursively searches OneDrive for Excel files and yields workbook entities.
        Uses optimized pagination and reduced logging for production scale.

        Args:
            client: HTTP client for API requests

        Yields:
            ExcelWorkbookEntity objects
        """
        self.logger.info("Starting workbook discovery")
        workbook_count = 0

        try:
            # Recursively discover all Excel files
            async for item_data in self._discover_excel_files_recursive(client):
                workbook_count += 1
                workbook_id = item_data.get("id")
                file_name = item_data.get("name", "Unknown")
                display_name = file_name.rsplit(".", 1)[0]  # Remove extension

                if workbook_count <= 10 or workbook_count % 50 == 0:
                    # Log first 10 and then every 50th workbook to reduce noise
                    self.logger.info(f"Found workbook #{workbook_count}: {display_name}")

                yield ExcelWorkbookEntity(
                    breadcrumbs=[],
                    id=workbook_id,
                    name=display_name,
                    created_datetime=self._parse_datetime(item_data.get("createdDateTime")),
                    last_modified_datetime=self._parse_datetime(
                        item_data.get("lastModifiedDateTime")
                    ),
                    file_name=file_name,
                    web_url_override=item_data.get("webUrl"),
                    size=item_data.get("size"),
                    created_by=item_data.get("createdBy"),
                    last_modified_by=item_data.get("lastModifiedBy"),
                    parent_reference=item_data.get("parentReference"),
                    drive_id=item_data.get("parentReference", {}).get("driveId"),
                    description=item_data.get("description"),
                )

            if workbook_count == 0:
                self.logger.warning(
                    "No Excel files found in OneDrive (searched root and subfolders)"
                )
            else:
                self.logger.info(f"Discovered {workbook_count} workbooks")

        except Exception as e:
            self.logger.error(f"Error generating workbook entities: {str(e)}", exc_info=True)
            raise

    async def _generate_worksheet_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        workbook_breadcrumb: Breadcrumb,
        workbook_web_url: Optional[str],
    ) -> AsyncGenerator[ExcelWorksheetEntity, None]:
        """Generate ExcelWorksheetEntity objects for worksheets in a workbook.

        Optimized with larger page sizes and concurrent content fetching.

        Args:
            client: HTTP client for API requests
            workbook_id: ID of the workbook
            workbook_name: Name of the workbook
            workbook_breadcrumb: Breadcrumb for the workbook

        Yields:
            ExcelWorksheetEntity objects
        """
        url = f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
        params = {"$top": self.PAGE_SIZE_WORKSHEETS}

        try:
            worksheet_count = 0
            worksheet_batch = []

            while url:
                data = await self._get_with_auth(client, url, params=params)
                worksheets = data.get("value", [])

                # Collect worksheets for batch processing
                for worksheet_data in worksheets:
                    worksheet_batch.append(worksheet_data)
                    worksheet_count += 1

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    params = None

            # Fetch worksheet content concurrently (in batches)
            for i in range(0, len(worksheet_batch), self.CONCURRENT_WORKSHEET_FETCH):
                batch = worksheet_batch[i : i + self.CONCURRENT_WORKSHEET_FETCH]

                # Fetch content for this batch concurrently
                content_tasks = [
                    self._fetch_worksheet_content(
                        client, workbook_id, ws.get("id"), ws.get("name", "Unknown")
                    )
                    for ws in batch
                ]
                content_results = await asyncio.gather(*content_tasks, return_exceptions=True)

                # Yield entities
                for worksheet_data, cell_data in zip(batch, content_results, strict=True):
                    worksheet_id = worksheet_data.get("id")
                    worksheet_name = worksheet_data.get("name", "Unknown Worksheet")
                    worksheet_web_url = None
                    if workbook_web_url and worksheet_name:
                        # Excel sheet names escape single quotes by doubling them inside the
                        # quoted sheet reference, e.g. "Bob's Sheet" -> 'Bob''s Sheet'!A1.
                        # We must perform this escaping before URL-encoding the activeCell.
                        safe_worksheet_name = worksheet_name.replace("'", "''")
                        worksheet_web_url = (
                            f"{workbook_web_url}&activeCell='{quote(safe_worksheet_name)}'!A1"
                        )

                    # Handle exceptions from content fetch
                    if isinstance(cell_data, Exception):
                        self.logger.warning(
                            f"Failed to fetch content for worksheet {worksheet_name}: {cell_data}"
                        )
                        cell_data = None

                    yield ExcelWorksheetEntity(
                        breadcrumbs=[workbook_breadcrumb],
                        id=worksheet_id,
                        name=worksheet_name,
                        workbook_id=workbook_id,
                        workbook_name=workbook_name,
                        position=worksheet_data.get("position"),
                        visibility=worksheet_data.get("visibility"),
                        range_address=cell_data.get("range_address") if cell_data else None,
                        cell_content=cell_data.get("formatted_text") if cell_data else None,
                        row_count=cell_data.get("row_count") if cell_data else None,
                        column_count=cell_data.get("column_count") if cell_data else None,
                        last_modified_datetime=self._parse_datetime(
                            worksheet_data.get("lastModifiedDateTime")
                        ),
                        web_url_override=worksheet_web_url,
                    )

            self.logger.debug(
                f"Processed {worksheet_count} worksheets for workbook {workbook_name}"
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
        worksheet_web_url: Optional[str],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate table entities for tables in a worksheet.

        Optimized with larger page size and concurrent fetching.

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
        url = (
            f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
            f"/workbook/worksheets/{worksheet_id}/tables"
        )
        params = {"$top": self.PAGE_SIZE_TABLES}

        try:
            table_count = 0
            while url:
                data = await self._get_with_auth(client, url, params=params)
                tables = data.get("value", [])

                for table_data in tables:
                    table_count += 1
                    table_id = table_data.get("id")
                    table_name = table_data.get("name", "Unknown Table")

                    # Fetch table data and columns concurrently
                    content_task = self._fetch_table_data(client, workbook_id, table_id, table_name)
                    columns_url = (
                        f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
                        f"/workbook/tables/{table_id}/columns"
                    )
                    columns_task = self._get_with_auth(client, columns_url)

                    # Fetch both concurrently
                    results = await asyncio.gather(
                        content_task, columns_task, return_exceptions=True
                    )
                    table_content = results[0] if not isinstance(results[0], Exception) else None
                    columns_data = results[1] if not isinstance(results[1], Exception) else None

                    # Extract column names
                    column_names = []
                    if columns_data:
                        column_names = [
                            col.get("name", "") for col in columns_data.get("value", [])
                        ]

                    yield ExcelTableEntity(
                        breadcrumbs=worksheet_breadcrumbs,
                        id=table_id,
                        name=table_name,
                        workbook_id=workbook_id,
                        workbook_name=workbook_name,
                        worksheet_id=worksheet_id,
                        worksheet_name=worksheet_name,
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
                        web_url_override=worksheet_web_url,
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    params = None

            if table_count > 0:
                self.logger.debug(f"Processed {table_count} tables for worksheet {worksheet_name}")

        except Exception as e:
            self.logger.warning(f"Error generating tables for worksheet {worksheet_name}: {str(e)}")
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
            rows_data = await self._get_with_auth(
                client, rows_url, params={"$top": self.MAX_TABLE_ROWS}
            )

            rows = rows_data.get("value", [])

            # Limit rows for entity size
            limited_rows = rows[: self.MAX_TABLE_ROWS]

            # Format data as text for embedding (optimized string building)
            formatted_lines = []
            for idx, row in enumerate(limited_rows):
                values = row.get("values", [[]])[0]
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

            # Limit the data we extract to prevent huge entities
            max_rows = min(self.MAX_WORKSHEET_ROWS, len(values))
            limited_values = values[:max_rows]

            # Format data as text for embedding (optimized string building)
            formatted_lines = []
            for row_idx, row in enumerate(limited_values):
                # Only include rows with at least one non-empty cell
                if any(cell for cell in row):
                    row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
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
                return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Worksheet might be empty
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

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
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
                    workbook_id = workbook_entity.id
                    workbook_name = workbook_entity.name
                    workbook_breadcrumb = Breadcrumb(
                        entity_id=workbook_id,
                        name=workbook_name,
                        entity_type="ExcelWorkbookEntity",
                    )
                    workbook_web_url = workbook_entity.web_url

                    # 2) Generate worksheet entities for this workbook
                    async for worksheet_entity in self._generate_worksheet_entities(
                        client,
                        workbook_id,
                        workbook_name,
                        workbook_breadcrumb,
                        workbook_web_url,
                    ):
                        entity_count += 1
                        self.logger.info(
                            f"Yielding entity #{entity_count}: Worksheet - {worksheet_entity.name}"
                        )
                        yield worksheet_entity

                        # Create worksheet breadcrumb
                        worksheet_id = worksheet_entity.id
                        worksheet_name = worksheet_entity.name
                        worksheet_breadcrumb = Breadcrumb(
                            entity_id=worksheet_id,
                            name=worksheet_name,
                            entity_type="ExcelWorksheetEntity",
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
                            worksheet_entity.web_url,
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
