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
from typing import Any, AsyncGenerator, Dict, List, Optional

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

    # Configuration constants for optimization
    MAX_WORKSHEET_ROWS = 200  # Limit rows per worksheet to prevent huge entities
    MAX_TABLE_ROWS = 100  # Limit rows per table
    PAGE_SIZE_WORKSHEETS = 250  # Optimal page size for worksheets
    PAGE_SIZE_TABLES = 100  # Optimal page size for tables
    CONCURRENT_WORKSHEET_FETCH = 5  # Concurrent worksheet content fetches

    # Supported Excel file extensions
    FILE_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".xlsb")

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

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Microsoft Excel entities.

        Yields:
            ExcelWorkbookEntity, ExcelWorksheetEntity, and ExcelTableEntity objects
        """
        self.logger.info("===== STARTING MICROSOFT EXCEL ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Discover all Excel workbooks recursively
                self.logger.info("Discovering Excel workbooks...")
                async for file_data in self._discover_files_recursive(client):
                    workbook_id = file_data["id"]
                    workbook_name = file_data.get("name", "Untitled Workbook")

                    # Create workbook entity
                    workbook_entity = ExcelWorkbookEntity(
                        entity_id=workbook_id,
                        name=workbook_name.rsplit(".", 1)[0]
                        if "." in workbook_name
                        else workbook_name,
                        file_name=workbook_name,
                        web_url=file_data.get("webUrl"),
                        size=file_data.get("size"),
                        created_datetime=self._parse_datetime(file_data.get("createdDateTime")),
                        last_modified_datetime=self._parse_datetime(
                            file_data.get("lastModifiedDateTime")
                        ),
                        created_by=file_data.get("createdBy"),
                        last_modified_by=file_data.get("lastModifiedBy"),
                        drive_id=file_data.get("parentReference", {}).get("driveId"),
                        folder_path=file_data.get("parentReference", {})
                        .get("path", "")
                        .replace("/drive/root:", ""),
                    )

                    entity_count += 1
                    self.logger.info(f"Yielding entity #{entity_count}: Workbook - {workbook_name}")
                    yield workbook_entity

                    workbook_breadcrumb = Breadcrumb(
                        entity_id=workbook_id, name=workbook_name, type="workbook"
                    )

                    # Generate worksheet entities for this workbook
                    async for worksheet_entity in self._generate_worksheet_entities(
                        client, workbook_id, workbook_name, [workbook_breadcrumb]
                    ):
                        entity_count += 1
                        yield worksheet_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT EXCEL ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def _generate_worksheet_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        workbook_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate worksheet entities for a workbook."""
        try:
            # Fetch worksheets
            worksheets_url = (
                f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
            )
            params = {"$top": self.PAGE_SIZE_WORKSHEETS}

            worksheets_data = await self._get_with_auth(client, worksheets_url, params)
            worksheets = worksheets_data.get("value", [])

            self.logger.info(f"Found {len(worksheets)} worksheets in workbook '{workbook_name}'")

            # Process worksheets concurrently
            tasks = []
            for worksheet_data in worksheets:
                task = self._process_worksheet(
                    client, workbook_id, workbook_name, worksheet_data, workbook_breadcrumbs
                )
                tasks.append(task)

            # Gather results from concurrent processing
            for coro in asyncio.as_completed(tasks):
                worksheet_entity, table_entities = await coro
                if worksheet_entity:
                    yield worksheet_entity
                for table_entity in table_entities:
                    yield table_entity

        except Exception as e:
            self.logger.warning(f"Error fetching worksheets for workbook {workbook_name}: {str(e)}")

    async def _process_worksheet(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        workbook_name: str,
        worksheet_data: Dict[str, Any],
        workbook_breadcrumbs: List[Breadcrumb],
    ) -> tuple:
        """Process a single worksheet and its tables."""
        worksheet_id = worksheet_data.get("id")
        worksheet_name = worksheet_data.get("name", "Sheet")

        try:
            # Get worksheet content (used range)
            content_url = (
                f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/"
                f"worksheets/{worksheet_id}/usedRange"
            )
            content_data = await self._get_with_auth(client, content_url)

            # Extract rows
            values = content_data.get("values", [])
            row_count = len(values)
            column_count = len(values[0]) if values else 0

            # Limit rows
            if row_count > self.MAX_WORKSHEET_ROWS:
                self.logger.debug(
                    f"Worksheet '{worksheet_name}' has {row_count} rows, "
                    f"limiting to {self.MAX_WORKSHEET_ROWS}"
                )
                values = values[: self.MAX_WORKSHEET_ROWS]

            # Create worksheet entity
            worksheet_entity = ExcelWorksheetEntity(
                entity_id=worksheet_id,
                breadcrumbs=workbook_breadcrumbs,
                name=worksheet_name,
                workbook_id=workbook_id,
                workbook_name=workbook_name,
                position=worksheet_data.get("position", 0),
                visibility=worksheet_data.get("visibility", "visible"),
                row_count=row_count,
                column_count=column_count,
                content=values,
            )

            self.logger.info(f"Processed worksheet '{worksheet_name}' ({row_count} rows)")

            # Generate table entities for this worksheet
            worksheet_breadcrumb = Breadcrumb(
                entity_id=worksheet_id, name=worksheet_name, type="worksheet"
            )
            breadcrumbs = [*workbook_breadcrumbs, worksheet_breadcrumb]

            table_entities = []
            async for table_entity in self._generate_table_entities(
                client, workbook_id, worksheet_id, worksheet_name, breadcrumbs
            ):
                table_entities.append(table_entity)

            return worksheet_entity, table_entities

        except Exception as e:
            self.logger.warning(f"Error processing worksheet '{worksheet_name}': {str(e)}")
            return None, []

    async def _generate_table_entities(
        self,
        client: httpx.AsyncClient,
        workbook_id: str,
        worksheet_id: str,
        worksheet_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ExcelTableEntity, None]:
        """Generate table entities for a worksheet."""
        try:
            # Fetch tables
            tables_url = (
                f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/"
                f"worksheets/{worksheet_id}/tables"
            )
            params = {"$top": self.PAGE_SIZE_TABLES}

            tables_data = await self._get_with_auth(client, tables_url, params)
            tables = tables_data.get("value", [])

            for table_data in tables:
                table_id = table_data.get("id")
                table_name = table_data.get("name", "Table")

                try:
                    # Get table rows
                    rows_url = (
                        f"{self.GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/"
                        f"tables/{table_id}/rows"
                    )
                    rows_data = await self._get_with_auth(client, rows_url)
                    rows = rows_data.get("value", [])

                    # Limit rows
                    if len(rows) > self.MAX_TABLE_ROWS:
                        rows = rows[: self.MAX_TABLE_ROWS]

                    # Extract row values
                    row_values = [row.get("values", [[]])[0] for row in rows]

                    # Create table entity
                    table_entity = ExcelTableEntity(
                        entity_id=table_id,
                        breadcrumbs=breadcrumbs,
                        name=table_name,
                        workbook_id=workbook_id,
                        worksheet_id=worksheet_id,
                        worksheet_name=worksheet_name,
                        row_count=len(row_values),
                        column_count=len(row_values[0]) if row_values else 0,
                        header_row=table_data.get("headerRowVisible", True),
                        content=row_values,
                    )

                    self.logger.info(f"Processed table '{table_name}' ({len(row_values)} rows)")
                    yield table_entity

                except Exception as e:
                    self.logger.warning(f"Error processing table '{table_name}': {str(e)}")
                    continue

        except Exception as e:
            self.logger.debug(f"No tables found in worksheet '{worksheet_name}': {str(e)}")
