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
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.excel import (
    ExcelTableEntity,
    ExcelWorkbookEntity,
    ExcelWorksheetEntity,
)
from airweave.platform.sources._microsoft_graph_files_base import (
    MicrosoftGraphFilesSource,
)
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
class ExcelSource(MicrosoftGraphFilesSource):
    """Microsoft Excel source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft Excel including workbooks, worksheets, and tables.

    It provides comprehensive access to Excel resources with proper token refresh
    and rate limiting.
    """

    # Supported Excel file extensions
    FILE_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".xlsb")

    # Configuration constants for optimization
    MAX_WORKSHEET_ROWS = 200  # Limit rows per worksheet to prevent huge entities
    MAX_TABLE_ROWS = 100  # Limit rows per table
    PAGE_SIZE_WORKSHEETS = 250  # Optimal page size for worksheets
    PAGE_SIZE_TABLES = 100  # Optimal page size for tables
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

    async def _generate_worksheet_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        workbook_breadcrumb: Breadcrumb,
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

                    # Handle exceptions from content fetch
                    if isinstance(cell_data, Exception):
                        self.logger.warning(
                            f"Failed to fetch content for worksheet {worksheet_name}: {cell_data}"
                        )
                        cell_data = None

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
    ) -> AsyncGenerator[ChunkEntity, None]:
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

                # Discover all Excel files recursively using base class method
                self.logger.info("Discovering Excel workbooks...")
                async for file_data in self._discover_files_recursive(client):
                    workbook_id = file_data["id"]
                    workbook_name = file_data.get("name", "Untitled Workbook")

                    # Create workbook entity
                    workbook_entity = ExcelWorkbookEntity(
                        entity_id=workbook_id,
                        breadcrumbs=[],
                        name=(
                            workbook_name.rsplit(".", 1)[0]
                            if "." in workbook_name
                            else workbook_name
                        ),
                        file_name=workbook_name,
                        web_url=file_data.get("webUrl"),
                        size=file_data.get("size"),
                        created_datetime=self._parse_datetime(file_data.get("createdDateTime")),
                        last_modified_datetime=self._parse_datetime(
                            file_data.get("lastModifiedDateTime")
                        ),
                        created_by=file_data.get("createdBy"),
                        last_modified_by=file_data.get("lastModifiedBy"),
                        parent_reference=file_data.get("parentReference"),
                        drive_id=file_data.get("parentReference", {}).get("driveId"),
                        description=file_data.get("description"),
                    )

                    entity_count += 1
                    self.logger.info(f"Yielding entity #{entity_count}: Workbook - {workbook_name}")
                    yield workbook_entity

                    # Create workbook breadcrumb
                    workbook_breadcrumb = Breadcrumb(
                        entity_id=workbook_id, name=workbook_name[:50], type="workbook"
                    )

                    # Generate worksheet entities for this workbook
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

                        # Generate table entities for this worksheet
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
