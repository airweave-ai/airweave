"""Notion connector for syncing content from Notion workspaces to Airweave.

This module provides a comprehensive source implementation for extracting databases and pages
with full aggregated content from Notion, handling API rate limits, and converting API
responses to entity objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import NotionConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
    _extract_page_title,
    _extract_rich_text_plain,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="Notion",
    short_name="notion",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=NotionConfig,
    labels=["Knowledge Base", "Productivity"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.CONNECTION,
)
class NotionSource(BaseSource):
    """Notion source connector integrates with the Notion API to extract and synchronize content.

    Connects to your Notion workspace.

    It provides comprehensive access to databases, pages, and content with advanced content
    aggregation, lazy loading, and file processing capabilities for optimal performance.
    """

    TIMEOUT_SECONDS = 60.0

    class NotionAccessError(Exception):
        """Non-retryable access/shape error from Notion.

        Raised for permission or structural cases that won't succeed on retry
        (e.g., 403/404, or specific 400 validation for linked views).
        """

        def __init__(self, status: int, message: str, url: str):
            """Initialize with HTTP status, message, and request URL."""
            super().__init__(f"HTTP {status} - {message} ({url})")
            self.status = status
            self.message = message
            self.url = url

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: NotionConfig,
    ) -> NotionSource:
        """Create a new Notion source."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    async def validate(self) -> None:
        """Validate credentials by pinging the Notion current-user endpoint."""
        await self._get("https://api.notion.com/v1/users/me")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> dict:
        """Make an authenticated GET request to the Notion API."""
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
        }

        response = await self.http_client.get(url, headers=headers, timeout=self.TIMEOUT_SECONDS)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Notion — attempting token refresh")
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.get(
                url, headers=headers, timeout=self.TIMEOUT_SECONDS
            )

        if response.status_code != 200:
            msg = ""
            try:
                body_json = response.json()
                if isinstance(body_json, dict):
                    msg = str(body_json.get("message", ""))
            except Exception:
                pass

            is_pages = "/v1/pages/" in url
            is_databases = "/v1/databases/" in url

            if is_pages and response.status_code in (403, 404):
                raise NotionSource.NotionAccessError(
                    response.status_code, msg or "access denied", url
                )
            if is_databases and (
                response.status_code in (403, 404)
                or (
                    response.status_code == 400
                    and "does not contain any data sources" in (msg or "").lower()
                )
            ):
                raise NotionSource.NotionAccessError(
                    response.status_code, msg or "validation_error", url
                )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(self, url: str, json_data: dict) -> dict:
        """Make an authenticated POST request to the Notion API."""
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
        }

        response = await self.http_client.post(
            url, headers=headers, json=json_data, timeout=self.TIMEOUT_SECONDS
        )

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Notion POST — attempting token refresh")
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.post(
                url, headers=headers, json=json_data, timeout=self.TIMEOUT_SECONDS
            )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Search / query helpers
    # ------------------------------------------------------------------

    async def _search_objects(  # noqa: C901
        self, object_type: str
    ) -> AsyncGenerator[dict, None]:
        """Search for objects of a specific type, excluding archived objects."""
        url = "https://api.notion.com/v1/search"
        has_more = True
        start_cursor = None

        total_found = 0
        total_filtered = 0

        while has_more:
            json_data: Dict[str, Any] = {
                "filter": {"property": "object", "value": object_type},
                "page_size": 100,
            }
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            try:
                response = await self._post(url, json_data)
                results = response.get("results", [])
                total_found += len(results)

                self.logger.debug(f"Search returned {len(results)} {object_type}(s) in this batch")

                filtered_count = 0
                for obj in results:
                    is_archived = obj.get("archived", False)
                    is_trashed = obj.get("in_trash", False)

                    if is_archived or is_trashed:
                        filtered_count += 1
                        total_filtered += 1
                    else:
                        yield obj

                if filtered_count > 0:
                    self.logger.warning(
                        f"Filtered {filtered_count} {object_type}(s) in this batch "
                        f"(archived or trashed)"
                    )

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Search access issue for {object_type}: {e}")
                raise
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error searching for {object_type}: {e}")
                raise

        yielded_count = total_found - total_filtered
        self.logger.debug(
            f"Search complete for {object_type}: "
            f"found={total_found}, filtered={total_filtered}, yielded={yielded_count}"
        )

    async def _query_database_pages(  # noqa: C901
        self, database_id: str
    ) -> AsyncGenerator[dict, None]:
        """Query all pages in a database, excluding archived pages."""
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        has_more = True
        start_cursor = None

        total_found = 0
        total_filtered = 0

        while has_more:
            json_data: Dict[str, Any] = {"page_size": 100}
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            try:
                response = await self._post(url, json_data)
                results = response.get("results", [])
                total_found += len(results)

                filtered_count = 0
                for page in results:
                    is_archived = page.get("archived", False)
                    is_trashed = page.get("in_trash", False)

                    if is_archived or is_trashed:
                        filtered_count += 1
                        total_filtered += 1
                    else:
                        yield page

                if filtered_count > 0:
                    self.logger.warning(
                        f"Filtered {filtered_count} page(s) in this batch (archived or trashed)"
                    )

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Database query access issue for {database_id}: {e}")
                raise
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error querying database {database_id}: {e}")
                raise

        yielded_count = total_found - total_filtered
        self.logger.debug(
            f"Database query complete for {database_id}: "
            f"found={total_found}, filtered={total_filtered}, yielded={yielded_count}"
        )

    # ------------------------------------------------------------------
    # Child database processing
    # ------------------------------------------------------------------

    async def _process_child_databases(  # noqa: C901
        self, files: FileService | None = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process child databases discovered during page content extraction."""
        self.logger.debug("Processing child databases")

        while self._child_databases_to_process:
            unprocessed_databases = [
                db_id
                for db_id in self._child_databases_to_process
                if db_id not in self._processed_databases
            ]

            if not unprocessed_databases:
                break

            self.logger.debug(f"Processing {len(unprocessed_databases)} child databases")

            for database_id in unprocessed_databases:
                try:
                    self.logger.debug(f"Processing child database: {database_id}")

                    schema = await self._get(f"https://api.notion.com/v1/databases/{database_id}")

                    breadcrumbs = self._child_database_breadcrumbs.get(database_id, [])

                    database_entity = NotionDatabaseEntity.from_api(schema, breadcrumbs=breadcrumbs)
                    yield database_entity
                    self._processed_databases.add(database_id)

                    async for page in self._query_database_pages(database_id):
                        page_id = page["id"]
                        if page_id in self._processed_pages:
                            continue

                        try:
                            db_breadcrumb = Breadcrumb(
                                entity_id=database_id,
                                name=database_entity.title,
                                entity_type=NotionDatabaseEntity.__name__,
                            )
                            page_breadcrumbs = breadcrumbs + [db_breadcrumb]

                            (
                                page_entity,
                                file_entities,
                            ) = await self._create_comprehensive_page_entity(
                                page, page_breadcrumbs, database_id, schema
                            )
                            yield page_entity

                            for file_entity in file_entities:
                                processed = await self._process_and_yield_file(file_entity, files)
                                if processed:
                                    yield processed

                            self._processed_pages.add(page_id)

                        except NotionSource.NotionAccessError as e:
                            self.logger.warning(
                                f"Access issue processing child database page {page_id}: {e}"
                            )
                            continue
                        except SourceAuthError:
                            raise
                        except Exception as e:
                            self.logger.warning(
                                f"Error processing child database page {page_id}: {e}"
                            )
                            continue

                except NotionSource.NotionAccessError as e:
                    self.logger.warning(
                        f"Child database {database_id} not accessible ({e.status}). Skipping."
                    )
                    self._processed_databases.add(database_id)
                    continue
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Error processing child database {database_id}: {e}")
                    self._processed_databases.add(database_id)
                    continue

    # ------------------------------------------------------------------
    # Breadcrumbs
    # ------------------------------------------------------------------

    async def _build_page_breadcrumbs(self, page: dict) -> List[Breadcrumb]:
        """Build breadcrumbs for a page by traversing up the parent hierarchy."""
        breadcrumbs: List[Breadcrumb] = []
        current_page = page

        while True:
            parent = current_page.get("parent", {})
            parent_type = parent.get("type", "")

            if parent_type == "page_id":
                parent_id = parent.get("page_id")
                try:
                    parent_page = await self._get(f"https://api.notion.com/v1/pages/{parent_id}")
                    parent_title = _extract_page_title(parent_page) or "Untitled Page"
                    breadcrumbs.insert(
                        0,
                        Breadcrumb(
                            entity_id=parent_id,
                            name=parent_title,
                            entity_type=NotionPageEntity.__name__,
                        ),
                    )
                    current_page = parent_page
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Could not fetch parent page {parent_id}: {e}")
                    break
            elif parent_type == "database_id":
                break
            else:
                break

        return breadcrumbs

    # ------------------------------------------------------------------
    # Page entity creation with content aggregation
    # ------------------------------------------------------------------

    async def _create_comprehensive_page_entity(
        self,
        page: dict,
        breadcrumbs: List[Breadcrumb],
        database_id: Optional[str] = None,
        database_schema: Optional[dict] = None,
    ) -> Tuple[NotionPageEntity, List[NotionFileEntity]]:
        """Create a comprehensive page entity with full aggregated content."""
        page_id = page["id"]
        title = _extract_page_title(page)

        self.logger.debug(f"Processing page: {title} ({page_id})")

        self._child_databases_to_process.clear()

        content_result = await self._aggregate_page_content(page_id, breadcrumbs)

        property_entities: List[NotionPropertyEntity] = []
        formatted_properties: Dict[str, Any] = {}
        if database_id and database_schema:
            property_entities = await self._extract_page_properties(
                page, database_id, database_schema
            )
            formatted_properties = self._create_formatted_properties_dict(
                page.get("properties", {}), database_schema.get("properties", {})
            )

        properties_text = self._generate_properties_text_for_page(formatted_properties, title)

        page_entity = NotionPageEntity.from_api(
            page,
            breadcrumbs=breadcrumbs,
            content=content_result["content"],
            formatted_properties=formatted_properties,
            properties_text=properties_text,
            property_entities=property_entities,
            content_blocks_count=content_result["blocks_count"],
            max_depth=content_result["max_depth"],
        )

        files_with_breadcrumbs = []
        for file_entity in content_result["files"]:
            file_entity.breadcrumbs = breadcrumbs.copy()
            files_with_breadcrumbs.append(file_entity)

        self.logger.debug(
            f"Page entity created: {len(content_result['content'])} chars, "
            f"{content_result['blocks_count']} blocks, "
            f"{len(files_with_breadcrumbs)} files, "
            f"max depth {content_result['max_depth']}"
        )

        return page_entity, files_with_breadcrumbs

    async def _aggregate_page_content(
        self, page_id: str, page_breadcrumbs: List[Breadcrumb]
    ) -> Dict[str, Any]:
        """Aggregate all content from a page into a single markdown string."""
        content_parts: List[str] = []
        files: List[NotionFileEntity] = []
        blocks_count = 0
        max_depth = 0

        async for block_content in self._extract_blocks_recursive(page_id, 0, page_breadcrumbs):
            content_parts.append(block_content["content"])
            files.extend(block_content["files"])
            blocks_count += 1
            max_depth = max(max_depth, block_content["depth"])
            self._stats["total_blocks_processed"] += 1

        if max_depth > self._stats["max_page_depth"]:
            self._stats["max_page_depth"] = max_depth

        self._stats["total_files_found"] += len(files)

        full_content = "\n\n".join(filter(None, content_parts))
        cleaned_content = self.clean_content_for_embedding(full_content)

        return {
            "content": cleaned_content,
            "files": files,
            "blocks_count": blocks_count,
            "max_depth": max_depth,
        }

    async def _extract_blocks_recursive(
        self,
        block_id: str,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively extract and format blocks into markdown content."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        has_more = True
        start_cursor = None

        while has_more:
            url_with_params = url if not start_cursor else f"{url}?start_cursor={start_cursor}"

            try:
                response = await self._get(url_with_params)
                if not self._is_valid_response(response, block_id):
                    break

                blocks = response.get("results", [])
                async for result in self._process_blocks(blocks, block_id, depth, page_breadcrumbs):
                    yield result

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Access issue extracting blocks from {block_id}: {e}")
                break
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    f"Error extracting blocks from {block_id}: {type(e).__name__}: {e}"
                )
                break

    def _is_valid_response(self, response: Any, block_id: str) -> bool:
        """Validate API response format."""
        if not response or not isinstance(response, dict):
            self.logger.warning(
                f"Invalid response format for blocks from {block_id}: {type(response)}"
            )
            return False
        return True

    async def _process_blocks(
        self,
        blocks: List[dict],
        block_id: str,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a list of blocks and their children."""
        for block in blocks:
            if not block or not isinstance(block, dict):
                self.logger.warning(f"Skipping invalid block in {block_id}: {type(block)}")
                continue

            block_result = await self._format_block_content(block, depth, page_breadcrumbs)
            if block_result and block_result.get("content"):
                yield block_result

            if block.get("has_children", False) and block.get("id"):
                async for child_result in self._extract_blocks_recursive(
                    block["id"], depth + 1, page_breadcrumbs
                ):
                    yield child_result

    async def _format_block_content(
        self, block: dict, depth: int, page_breadcrumbs: List[Breadcrumb]
    ) -> Dict[str, Any]:
        """Format a single block into markdown content."""
        if not self._validate_block(block):
            return {"content": "", "files": [], "depth": depth}

        block_type = block.get("type", "")
        if not block_type:
            self.logger.warning(f"Block missing type field: {block.get('id', 'unknown')}")
            return {"content": "", "files": [], "depth": depth}

        block_content = block.get(block_type, {}) or {}
        content, files = self._dispatch_block_formatter(
            block_type, block_content, block, depth, page_breadcrumbs
        )

        return {"content": content, "files": files, "depth": depth}

    def _validate_block(self, block: dict) -> bool:
        """Validate block structure."""
        if not block or not isinstance(block, dict):
            self.logger.warning(f"Invalid block format: {type(block)}")
            return False
        return True

    def _dispatch_block_formatter(
        self,
        block_type: str,
        block_content: dict,
        block: dict,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> Tuple[str, List[NotionFileEntity]]:
        """Dispatch to appropriate block formatter based on type."""
        if block_type == "paragraph":
            return self._extract_rich_text_markdown(block_content.get("rich_text", [])), []
        if block_type in ["heading_1", "heading_2", "heading_3"]:
            return self._format_heading_block(block_content, block_type), []
        if block_type in ["bulleted_list_item", "numbered_list_item", "to_do"]:
            return self._format_list_blocks(block_content, block_type, depth), []
        if block_type in ["quote", "callout", "code"]:
            return self._format_text_blocks(block_content, block_type), []
        if block_type in ["image", "video", "file", "pdf"]:
            return self._format_file_block(block_content, block, block_type)
        if block_type in ["embed", "bookmark", "equation", "divider"]:
            return self._format_simple_blocks(block_content, block_type), []
        if block_type in ["child_page", "child_database"]:
            return (
                self._format_child_blocks(block_content, block, block_type, page_breadcrumbs),
                [],
            )
        return self._format_other_blocks(block_content, block_type), []

    def _format_heading_block(self, block_content: dict, block_type: str) -> str:
        """Format heading blocks."""
        level = int(block_type.split("_")[1])
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        prefix = "▸ " if block_content.get("is_toggleable", False) else ""
        return f"{'#' * level} {prefix}{text}"

    def _format_list_blocks(self, block_content: dict, block_type: str, depth: int) -> str:
        """Format list and todo blocks."""
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        indent = "  " * depth

        if block_type == "bulleted_list_item":
            return f"{indent}- {text}"
        elif block_type == "numbered_list_item":
            return f"{indent}1. {text}"
        else:  # to_do
            checkbox = "- [x]" if block_content.get("checked", False) else "- [ ]"
            return f"{indent}{checkbox} {text}"

    def _format_text_blocks(self, block_content: dict, block_type: str) -> str:
        """Format quote, callout, and code blocks."""
        if block_type == "quote":
            text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
            return f"> {text}"
        elif block_type == "callout":
            return self._format_callout_block(block_content)
        else:  # code
            return self._format_code_block(block_content)

    def _format_simple_blocks(self, block_content: dict, block_type: str) -> str:
        """Format simple blocks like embed, bookmark, equation, divider."""
        if block_type in ["embed", "bookmark"]:
            url = block_content.get("url", "")
            caption = _extract_rich_text_plain(block_content.get("caption", []))
            if len(url) > 200 or "?" in url and len(url.split("?", 1)[1]) > 100:
                content = f"[{block_type.title()}]"
            else:
                content = f"[{block_type.title()}]({url})"
            if caption:
                content += f" - {caption}"
            return content
        elif block_type == "equation":
            expression = block_content.get("expression", "")
            return f"$$\n{expression}\n$$"
        elif block_type == "divider":
            return "---"
        else:
            return "**Table of Contents**"

    def _format_child_blocks(
        self, block_content: dict, block: dict, block_type: str, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child page and database blocks."""
        if block_type == "child_page":
            title = block_content.get("title", "Untitled Page")
            return f"📄 **[{title}]** (Child Page)"
        else:
            return self._format_child_database_block(block_content, block, page_breadcrumbs)

    def _format_other_blocks(self, block_content: dict, block_type: str) -> str:
        """Format other block types including table, column, etc."""
        if block_type in ["table", "column_list"]:
            return f"**[{block_type.replace('_', ' ').title()}]**"
        elif block_type in ["table_row", "column"]:
            return ""
        elif block_type == "unsupported":
            return "*[Unsupported block type]*"
        else:
            return self._format_unknown_block(block_content, block_type)

    def _format_callout_block(self, block_content: dict) -> str:
        """Format callout blocks."""
        icon = block_content.get("icon", {})
        icon_text = icon.get("emoji", "💡") if icon.get("type") == "emoji" else "💡"
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        return f"**{icon_text} {text}**"

    def _format_code_block(self, block_content: dict) -> str:
        """Format code blocks."""
        language = block_content.get("language", "")
        code_text = _extract_rich_text_plain(block_content.get("rich_text", []))
        caption = _extract_rich_text_plain(block_content.get("caption", []))
        content = f"```{language}\n{code_text}\n```"
        if caption:
            content += f"\n*{caption}*"
        return content

    def _format_file_block(
        self, block_content: dict, block: dict, block_type: str
    ) -> Tuple[str, List[NotionFileEntity]]:
        """Format file blocks and return content and file entities."""
        file_entity = NotionFileEntity.from_api(
            block_content, parent_id=block["id"], breadcrumbs=[]
        )
        files = [file_entity]
        caption = _extract_rich_text_plain(block_content.get("caption", []))

        if block_type == "image":
            display_name = file_entity.name if file_entity.name != "Untitled File" else "Image"
            content = f"[Image: {display_name}]"
        else:
            content = f"[File: {file_entity.name}]"

        if caption:
            content += f" - {caption}"

        return content, files

    def _format_child_database_block(
        self, block_content: dict, block: dict, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child database blocks."""
        title = block_content.get("title", "Untitled Database")
        database_id = block["id"]

        self._child_databases_to_process.add(database_id)

        child_db_breadcrumbs = page_breadcrumbs.copy()
        self._child_database_breadcrumbs[database_id] = child_db_breadcrumbs

        self._stats["child_databases_found"] += 1
        return f"🗃️ **[{title}]** (Child Database)"

    def _format_unknown_block(self, block_content: dict, block_type: str) -> str:
        """Format unknown block types."""
        if "rich_text" in block_content:
            return self._extract_rich_text_markdown(block_content.get("rich_text", []))
        else:
            return f"*[{block_type.replace('_', ' ').title()}]*"

    # ------------------------------------------------------------------
    # Rich text extraction
    # ------------------------------------------------------------------

    def _extract_rich_text_markdown(self, rich_text: List[dict]) -> str:
        """Extract rich text and convert to markdown formatting."""
        if not rich_text or not isinstance(rich_text, list):
            return ""

        result_parts = []
        for text_obj in rich_text:
            if not text_obj or not isinstance(text_obj, dict):
                continue

            text = text_obj.get("plain_text", "")
            if not text:
                continue

            annotations = text_obj.get("annotations") or {}
            href = text_obj.get("href")
            formatted_text = self._apply_markdown_annotations(text, annotations, href)
            result_parts.append(formatted_text)

        return "".join(result_parts)

    def _apply_markdown_annotations(self, text: str, annotations: dict, href: str = None) -> str:
        """Apply markdown formatting based on annotations."""
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        if annotations.get("code"):
            text = f"`{text}`"
        if href:
            text = f"[{text}]({href})"
        return text

    # ------------------------------------------------------------------
    # Property extraction
    # ------------------------------------------------------------------

    async def _extract_page_properties(
        self, page: dict, database_id: str, database_schema: dict
    ) -> List[NotionPropertyEntity]:
        """Extract database page properties as structured entities."""
        page_id = page["id"]
        page_properties = page.get("properties", {})
        schema_properties = database_schema.get("properties", {})

        property_entities = []

        for prop_name, prop_value in page_properties.items():
            if prop_name in schema_properties:
                schema_prop = schema_properties[prop_name]

                try:
                    property_entity = self._create_property_entity(
                        prop_name, prop_value, schema_prop, page_id, database_id
                    )
                    property_entities.append(property_entity)

                except Exception as e:
                    self.logger.warning(
                        f"Error processing property {prop_name} for page {page_id}: {e}"
                    )
                    continue

        return property_entities

    def _create_property_entity(
        self, prop_name: str, prop_value: dict, schema_prop: dict, page_id: str, database_id: str
    ) -> NotionPropertyEntity:
        """Create a property entity from page property data."""
        prop_type = prop_value.get("type", "")
        formatted_value = self._format_property_value(prop_value, prop_type)
        schema_prop_id = schema_prop.get("id", prop_name)
        property_key = f"{page_id}_{schema_prop_id}"

        return NotionPropertyEntity(
            entity_id=property_key,
            breadcrumbs=[],
            name=prop_name,
            created_at=None,
            updated_at=None,
            property_key=property_key,
            property_id=schema_prop_id,
            property_name=prop_name,
            property_type=prop_type,
            page_id=page_id,
            database_id=database_id,
            value=prop_value.get(prop_type),
            formatted_value=formatted_value,
        )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _format_property_value(self, prop_value: dict, prop_type: str) -> str:
        """Format property value for human readability."""
        if not prop_value or prop_type not in prop_value:
            return ""

        value = prop_value[prop_type]

        formatters = {
            "title": lambda v: _extract_rich_text_plain(v),
            "rich_text": lambda v: _extract_rich_text_plain(v),
            "number": lambda v: str(v) if v is not None else "",
            "url": lambda v: str(v) if v is not None else "",
            "email": lambda v: str(v) if v is not None else "",
            "phone_number": lambda v: str(v) if v is not None else "",
            "checkbox": lambda v: "Yes" if v else "No",
            "select": lambda v: self._format_select_properties(v),
            "status": lambda v: self._format_select_properties(v),
            "multi_select": lambda v: ", ".join([opt.get("name", "") for opt in v]) if v else "",
            "date": lambda v: self._format_date_property(v),
            "people": lambda v: self._format_people_property(v),
            "files": lambda v: f"{len(v)} file(s)" if v else "0 files",
            "created_time": lambda v: v or "",
            "last_edited_time": lambda v: v or "",
            "created_by": lambda v: v.get("name", "Unknown User") if v else "",
            "last_edited_by": lambda v: v.get("name", "Unknown User") if v else "",
        }

        if prop_type in formatters:
            return formatters[prop_type](value)

        return self._format_complex_property_types(prop_type, value)

    def _format_complex_property_types(self, prop_type: str, value: Any) -> str:
        """Format complex property types that need special handling."""
        if prop_type == "relation":
            return f"{len(value)} relation(s)" if value else "0 relations"
        elif prop_type == "rollup":
            return self._format_rollup_property(value)
        elif prop_type == "formula":
            return self._format_formula_property(value)
        elif prop_type == "unique_id":
            return self._format_unique_id_property(value)
        elif prop_type == "verification":
            return self._format_verification_property(value)
        else:
            return str(value) if value else ""

    def _format_unique_id_property(self, value: dict) -> str:
        prefix = value.get("prefix", "")
        number = value.get("number", "")
        return f"{prefix}{number}" if prefix else str(number)

    def _format_verification_property(self, value: dict) -> str:
        state = value.get("state", "")
        return state.title() if state else ""

    def _format_select_properties(self, value: dict) -> str:
        return value.get("name", "") if value else ""

    def _format_date_property(self, value: dict) -> str:
        if value and value.get("start"):
            start = value["start"]
            end = value.get("end")
            return f"{start} - {end}" if end else start
        return ""

    def _format_people_property(self, value: List[dict]) -> str:
        names = []
        for person in value:
            if person.get("type") == "person":
                names.append(person.get("name", "Unknown"))
            elif person.get("type") == "bot":
                names.append(person.get("name", "Bot"))
        return ", ".join(names)

    def _format_formula_property(self, value: dict) -> str:
        formula_type = value.get("type", "")
        if formula_type in ["string", "number", "boolean", "date"]:
            return str(value.get(formula_type, ""))
        return ""

    def _format_rollup_property(self, value: dict) -> str:
        rollup_type = value.get("type", "")
        if rollup_type in ["string", "number", "boolean", "date"]:
            return str(value.get(rollup_type, ""))
        elif rollup_type == "array":
            return f"{len(value.get('array', []))} item(s)"
        return ""

    def _create_formatted_properties_dict(
        self, page_properties: dict, database_schema: dict
    ) -> Dict[str, Any]:
        """Create a clean, formatted properties dictionary for better searchability."""
        formatted: Dict[str, Any] = {}

        for prop_name, prop_value in page_properties.items():
            if not prop_value:
                continue

            prop_type = prop_value.get("type", "")
            formatted_value = self._format_property_value(prop_value, prop_type)

            if not formatted_value:
                continue

            formatted[prop_name] = formatted_value

            if prop_type in ["select", "status", "multi_select"] and prop_name in database_schema:
                schema_prop = database_schema[prop_name]
                if prop_type == "multi_select":
                    options = schema_prop.get("multi_select", {}).get("options", [])
                else:
                    options = schema_prop.get(prop_type, {}).get("options", [])

                if options:
                    formatted[f"{prop_name}_options"] = [
                        opt.get("name", "") for opt in options if opt.get("name")
                    ]

        return formatted

    def _generate_properties_text_for_page(
        self, properties: Dict[str, Any], page_title: str
    ) -> str:
        """Generate human-readable text from properties for embedding."""
        if not properties:
            return ""

        text_parts = []

        priority_keys = [
            "Product Name",
            "Name",
            "Title",
            "Status",
            "Priority",
            "Launch Status",
            "Owner",
            "Team",
            "Description",
        ]

        for key in priority_keys:
            if key in properties:
                value = properties[key]
                if value and str(value).strip():
                    if key in ["Product Name", "Name", "Title"] and value == page_title:
                        continue
                    text_parts.append(f"{key}: {value}")

        for key, value in properties.items():
            if key not in priority_keys and not key.endswith("_options"):
                if value and str(value).strip():
                    formatted_key = key.replace("_", " ").title()
                    text_parts.append(f"{formatted_key}: {value}")

        return " | ".join(text_parts) if text_parts else ""

    # ------------------------------------------------------------------
    # File processing
    # ------------------------------------------------------------------

    async def _process_and_yield_file(  # noqa: C901
        self, file_entity: NotionFileEntity, files: FileService | None = None
    ) -> Optional[NotionFileEntity]:
        """Process a file entity by downloading it and setting local_path."""
        try:
            if file_entity.needs_refresh():
                self.logger.warning(f"Skipping file {file_entity.name} - URL expired")
                return None

            if not file_entity.url or file_entity.url.startswith("http") is False:
                self.logger.debug(f"Skipping file {file_entity.name} - no valid download URL")
                return None

            if not files:
                return None

            try:
                await files.download_from_url(
                    entity=file_entity,
                    client=self.http_client,
                    auth=self.auth,
                    logger=self.logger,
                )

                if not file_entity.local_path:
                    raise ValueError(f"Download failed - no local path set for {file_entity.name}")

                self.logger.debug(
                    f"Successfully downloaded file {file_entity.name} "
                    f"to local_path: {file_entity.local_path}"
                )
                return file_entity

            except FileSkippedException as e:
                self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise
                self.logger.warning(f"Failed to download file {file_entity.name}: {e}")
                return None

        except NotionSource.NotionAccessError as e:
            self.logger.warning(f"Access issue processing file {file_entity.name}: {e}")
            return None
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing file {file_entity.name}: {e}")
            return None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Notion using streaming discovery."""
        self.logger.debug("Starting Notion entity generation with content aggregation")

        self._processed_pages: Set[str] = set()
        self._processed_databases: Set[str] = set()
        self._child_databases_to_process: Set[str] = set()
        self._child_database_breadcrumbs: Dict[str, List[Breadcrumb]] = {}
        self._stats: Dict[str, int] = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "databases_found": 0,
            "child_databases_found": 0,
            "pages_found": 0,
            "total_blocks_processed": 0,
            "total_files_found": 0,
            "max_page_depth": 0,
        }

        try:
            self.logger.debug("PHASE 1 & 2: Streaming database discovery and schema analysis")
            async for entity in self._stream_database_discovery(files):
                yield entity
            self.logger.debug(
                f"Phase 1 & 2 complete: {self._stats['databases_found']} databases found"
            )

            self.logger.debug("PHASE 3: Streaming standalone page discovery")
            async for entity in self._stream_page_discovery(files):
                yield entity
            self.logger.debug(
                f"Phase 3 complete: {self._stats['pages_found']} standalone pages found"
            )

            self.logger.debug("PHASE 4: Processing child databases")
            async for entity in self._process_child_databases(files):
                yield entity
            self.logger.debug(
                f"Phase 4 complete: {self._stats['child_databases_found']} child databases found"
            )

            self.logger.debug("Notion sync complete. Final stats:")
            for key, value in self._stats.items():
                self.logger.debug(f"   {key}: {value}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error during streaming Notion entity generation: {e}", exc_info=True
            )
            raise

    async def _stream_database_discovery(
        self, files: FileService | None = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Discover databases and delegate per-database processing."""
        self.logger.debug("Streaming database discovery...")

        async for database in self._search_objects("database"):
            database_id = database["id"]
            if database_id in self._processed_databases:
                continue
            self._stats["databases_found"] += 1
            async for entity in self._process_single_database(database_id, files):
                yield entity

    async def _process_single_database(  # noqa: C901
        self, database_id: str, files: FileService | None = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process one database: fetch schema, emit DB entity, pages, files, child DBs."""
        try:
            self.logger.debug(f"Fetching schema for database: {database_id}")
            schema = await self._get(f"https://api.notion.com/v1/databases/{database_id}")
            self._processed_databases.add(database_id)

            database_entity = NotionDatabaseEntity.from_api(schema, breadcrumbs=[])
            yield database_entity

            database_title = _extract_rich_text_plain(schema.get("title", []))
            self.logger.debug(f"Processing pages in database: {database_title}")

            async for page in self._query_database_pages(database_id):
                page_id = page["id"]
                if page_id in self._processed_pages:
                    continue
                try:
                    breadcrumbs = [
                        Breadcrumb(
                            entity_id=database_id,
                            name=database_title or "Untitled Database",
                            entity_type=NotionDatabaseEntity.__name__,
                        )
                    ]
                    page_entity, file_entities = await self._create_comprehensive_page_entity(
                        page, breadcrumbs, database_id, schema
                    )
                    yield page_entity
                    for file_entity in file_entities:
                        processed = await self._process_and_yield_file(file_entity, files)
                        if processed:
                            yield processed
                    self._processed_pages.add(page_id)
                    async for child_entity in self._process_child_databases(files):
                        yield child_entity
                except NotionSource.NotionAccessError as e:
                    self.logger.warning(f"Access issue processing database page {page_id}: {e}")
                    continue
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Error processing database page {page_id}: {e}")
                    continue
        except NotionSource.NotionAccessError as e:
            self.logger.warning(f"Access issue processing database {database_id}: {e}")
            return
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing database {database_id}: {e}")
            return

    async def _stream_page_discovery(
        self, files: FileService | None = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Stream page discovery and immediately yield page entities."""
        self.logger.debug("Streaming page discovery...")

        async for page in self._search_objects("page"):
            page_id = page["id"]
            if page_id in self._processed_pages:
                continue

            parent = page.get("parent", {})
            parent_type = parent.get("type", "")

            if parent_type == "database_id":
                continue

            self._stats["pages_found"] += 1

            try:
                full_page = await self._get(f"https://api.notion.com/v1/pages/{page_id}")

                breadcrumbs = await self._build_page_breadcrumbs(full_page)

                page_entity, file_entities = await self._create_comprehensive_page_entity(
                    full_page, breadcrumbs
                )
                yield page_entity

                for file_entity in file_entities:
                    processed = await self._process_and_yield_file(file_entity, files)
                    if processed:
                        yield processed

                self._processed_pages.add(page_id)

                async for child_entity in self._process_child_databases(files):
                    yield child_entity

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Access issue processing standalone page {page_id}: {e}")
                continue
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error processing standalone page {page_id}: {e}")
                continue
