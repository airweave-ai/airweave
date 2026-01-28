"""Miro source implementation for syncing boards, items, connectors, and tags."""

import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.miro import (
    MiroAppCardEntity,
    MiroBoardEntity,
    MiroCardEntity,
    MiroDocumentEntity,
    MiroFrameEntity,
    MiroImageEntity,
    MiroStickyNoteEntity,
    MiroTagEntity,
    MiroTextEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Miro",
    short_name="miro",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="MiroConfig",
    labels=["Collaboration", "Whiteboard"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class MiroSource(BaseSource):
    """Miro source connector integrates with the Miro API to extract and synchronize data.

    Connects to your Miro boards and syncs boards, sticky notes, cards, text items,
    frames, tags, app cards, documents, and images.
    """

    API_BASE = "https://api.miro.com/v2"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "MiroSource":
        """Create a new Miro source.

        Args:
            access_token: OAuth access token for Miro API
            config: Optional configuration parameters

        Returns:
            Configured MiroSource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        if config:
            instance.exclude_boards = config.get("exclude_boards", "")
        else:
            instance.exclude_boards = ""

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Miro API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters
        """
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                if self.token_manager:
                    try:
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)
                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Miro API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Miro API: {url}, {str(e)}")
            raise

    async def _paginate(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict, None]:
        """Handle Miro v2 cursor-based pagination.

        Yields individual items from paginated response.

        Args:
            client: HTTP client to use
            url: API endpoint URL
            params: Optional query parameters
        """
        params = dict(params) if params else {}
        params.setdefault("limit", 50)  # Miro default is 10, max is 50
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            response = await self._get_with_auth(client, url, params)

            for item in response.get("data", []):
                yield item

            cursor = response.get("cursor")
            if not cursor:
                break

    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object.

        Args:
            date_str: ISO format datetime string

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None
        try:
            # Handle ISO format with Z suffix
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    def _has_file_changed(self, item_id: str, modified_at: Optional[datetime]) -> bool:
        """Check if file metadata indicates change without downloading.

        Compares the modified_at timestamp against stored cursor data.
        Returns True if file is new or changed, False if unchanged.

        Args:
            item_id: Unique identifier for the file item
            modified_at: Current modified timestamp from API

        Returns:
            True if file should be processed (new or changed), False if unchanged
        """
        if not self.cursor:
            return True  # No cursor = first sync, treat as changed

        if not modified_at:
            return True  # No timestamp = can't compare, treat as changed

        file_metadata = self.cursor.data.get("file_metadata", {})
        stored_meta = file_metadata.get(item_id)

        if not stored_meta:
            return True  # New file

        stored_modified = stored_meta.get("modified_at")
        if stored_modified != modified_at.isoformat():
            return True  # File changed

        return False  # Unchanged

    def _store_file_metadata(
        self, item_id: str, modified_at: Optional[datetime], filename: Optional[str] = None
    ) -> None:
        """Store file metadata in cursor for future change detection.

        Args:
            item_id: Unique identifier for the file item
            modified_at: Modified timestamp from API
            filename: Extracted filename (for unchanged file retrieval)
        """
        if not self.cursor:
            return

        if not modified_at:
            return

        file_metadata = self.cursor.data.get("file_metadata", {})
        file_metadata[item_id] = {
            "modified_at": modified_at.isoformat(),
        }
        if filename:
            file_metadata[item_id]["filename"] = filename
        self.cursor.update(file_metadata=file_metadata)

    def _get_stored_filename(self, item_id: str) -> Optional[str]:
        """Get stored filename from cursor for unchanged files.

        Args:
            item_id: Unique identifier for the file item

        Returns:
            Stored filename or None if not found
        """
        if not self.cursor:
            return None

        file_metadata = self.cursor.data.get("file_metadata", {})
        stored_meta = file_metadata.get(item_id)

        if not stored_meta:
            return None

        return stored_meta.get("filename")

    @staticmethod
    def _strip_html(text: Optional[str]) -> str:
        """Strip HTML tags from text content.

        Args:
            text: HTML text content

        Returns:
            Plain text with HTML tags removed
        """
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", text).strip()

    async def _generate_board_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[MiroBoardEntity, None]:
        """Generate board entities for the authenticated user."""
        self.logger.info("Fetching Miro boards...")

        async for board in self._paginate(client, f"{self.API_BASE}/boards"):
            # Skip boards matching exclusion pattern
            if self.exclude_boards and self.exclude_boards in board.get("name", ""):
                self.logger.info(f"Skipping excluded board: {board.get('name')}")
                continue

            owner = board.get("owner", {})
            board_name = board.get("name", "Untitled Board")
            created_at = self._parse_datetime(board.get("createdAt"))
            modified_at = self._parse_datetime(board.get("modifiedAt"))

            yield MiroBoardEntity(
                # Base entity fields
                entity_id=board["id"],
                breadcrumbs=[],  # Root entity
                # API-specific fields
                board_id=board["id"],
                board_name=board_name,
                created_at=created_at,
                modified_at=modified_at,
                description=board.get("description"),
                team_id=board.get("team", {}).get("id") if board.get("team") else None,
                owner_id=owner.get("id"),
                owner_name=owner.get("name"),
                view_link=board.get("viewLink"),
            )

    async def _get_board_tags(self, client: httpx.AsyncClient, board_id: str) -> Dict[str, Dict]:
        """Fetch all tags for a board in a single API call.

        Args:
            client: HTTP client
            board_id: Board ID to fetch tags for

        Returns:
            Dict mapping tag ID to tag data
        """
        try:
            url = f"{self.API_BASE}/boards/{board_id}/tags"
            tags = []
            async for tag in self._paginate(client, url):
                tags.append(tag)
            return {tag["id"]: tag for tag in tags}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Tags endpoint may not be available for this board
                return {}
            self.logger.warning(f"Failed to fetch tags for board {board_id}: {e}")
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch tags for board {board_id}: {e}")
            return {}

    async def _get_item_tags(
        self, client: httpx.AsyncClient, board_id: str, item_id: str
    ) -> List[Dict]:
        """Fetch tags for a specific item on a board.

        Note: This method makes an API call per item. For bulk operations,
        use _get_board_tags to fetch all tags once and look up by ID.

        Args:
            client: HTTP client
            board_id: Board ID containing the item
            item_id: Item ID to get tags for

        Returns:
            List of tag dictionaries
        """
        try:
            url = f"{self.API_BASE}/boards/{board_id}/items/{item_id}/tags"
            response = await self._get_with_auth(client, url)
            return response.get("data", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Item may not have tags or endpoint may not be available
                return []
            self.logger.warning(f"Failed to fetch tags for item {item_id}: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"Failed to fetch tags for item {item_id}: {e}")
            return []

    async def _generate_sticky_note_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        board_tags: Dict[str, Dict],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroStickyNoteEntity, None]:
        """Generate sticky note entities for a board.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            board_tags: Pre-fetched tag lookup dict from _get_board_tags
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/sticky_notes"

        async for item in self._paginate(client, url):
            data = item.get("data", {})
            content = self._strip_html(data.get("content", "")) or "Empty sticky note"
            created_at = self._parse_datetime(item.get("createdAt"))
            modified_at = self._parse_datetime(item.get("modifiedAt"))

            # Get tags from item data if available, lookup from board_tags
            item_tags = item.get("tags", [])
            tags = [board_tags.get(t.get("id"), t) for t in item_tags if t.get("id")]

            # Extract parent frame info
            parent = item.get("parent", {})
            parent_frame_id = parent.get("id") if parent else None
            parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

            # Build breadcrumbs including parent frame if present
            item_breadcrumbs = list(board_breadcrumbs)
            if parent_frame_id and parent_frame_title:
                item_breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_frame_id,
                        name=parent_frame_title,
                        entity_type="MiroFrameEntity",
                    )
                )

            yield MiroStickyNoteEntity(
                # Base entity fields
                entity_id=item["id"],
                breadcrumbs=item_breadcrumbs,
                # API-specific fields
                item_id=item["id"],
                content=content,
                created_at=created_at,
                modified_at=modified_at,
                board_id=board_id,
                board_name=board_name,
                frame_id=parent_frame_id,
                frame_title=parent_frame_title,
                created_by=item.get("createdBy"),
                modified_by=item.get("modifiedBy"),
                tags=tags,
            )

    async def _generate_card_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        board_tags: Dict[str, Dict],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroCardEntity, None]:
        """Generate card entities for a board.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            board_tags: Pre-fetched tag lookup dict from _get_board_tags
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/cards"

        async for item in self._paginate(client, url):
            data = item.get("data", {})
            title = self._strip_html(data.get("title", "")) or "Untitled Card"
            description = self._strip_html(data.get("description", "")) or None
            created_at = self._parse_datetime(item.get("createdAt"))
            modified_at = self._parse_datetime(item.get("modifiedAt"))

            # Get tags from item data if available, lookup from board_tags
            item_tags = item.get("tags", [])
            tags = [board_tags.get(t.get("id"), t) for t in item_tags if t.get("id")]

            # Extract parent frame info
            parent = item.get("parent", {})
            parent_frame_id = parent.get("id") if parent else None
            parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

            # Build breadcrumbs including parent frame if present
            item_breadcrumbs = list(board_breadcrumbs)
            if parent_frame_id and parent_frame_title:
                item_breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_frame_id,
                        name=parent_frame_title,
                        entity_type="MiroFrameEntity",
                    )
                )

            yield MiroCardEntity(
                # Base entity fields
                entity_id=item["id"],
                breadcrumbs=item_breadcrumbs,
                # API-specific fields
                item_id=item["id"],
                title=title,
                created_at=created_at,
                modified_at=modified_at,
                board_id=board_id,
                board_name=board_name,
                frame_id=parent_frame_id,
                frame_title=parent_frame_title,
                description=description,
                due_date=data.get("dueDate"),
                assignee_id=data.get("assigneeId"),
                fields=data.get("fields", []),
                tags=tags,
                created_by=item.get("createdBy"),
                modified_by=item.get("modifiedBy"),
            )

    async def _generate_text_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroTextEntity, None]:
        """Generate text entities for a board.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/texts"

        async for item in self._paginate(client, url):
            data = item.get("data", {})
            content = self._strip_html(data.get("content", ""))

            if not content:
                continue  # Skip empty text items

            created_at = self._parse_datetime(item.get("createdAt"))
            modified_at = self._parse_datetime(item.get("modifiedAt"))

            # Extract parent frame info
            parent = item.get("parent", {})
            parent_frame_id = parent.get("id") if parent else None
            parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

            # Build breadcrumbs including parent frame if present
            item_breadcrumbs = list(board_breadcrumbs)
            if parent_frame_id and parent_frame_title:
                item_breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_frame_id,
                        name=parent_frame_title,
                        entity_type="MiroFrameEntity",
                    )
                )

            yield MiroTextEntity(
                # Base entity fields
                entity_id=item["id"],
                breadcrumbs=item_breadcrumbs,
                # API-specific fields
                item_id=item["id"],
                content=content,
                created_at=created_at,
                modified_at=modified_at,
                board_id=board_id,
                board_name=board_name,
                frame_id=parent_frame_id,
                frame_title=parent_frame_title,
                created_by=item.get("createdBy"),
                modified_by=item.get("modifiedBy"),
            )

    async def _generate_frame_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroFrameEntity, None]:
        """Generate frame entities for a board.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            frame_lookup: Dict mapping frame_id -> frame_title for nested frames
        """
        url = f"{self.API_BASE}/boards/{board_id}/frames"

        async for item in self._paginate(client, url):
            data = item.get("data", {})
            title = data.get("title", "Untitled Frame")
            created_at = self._parse_datetime(item.get("createdAt"))
            modified_at = self._parse_datetime(item.get("modifiedAt"))

            # Extract parent frame info (for nested frames)
            parent = item.get("parent", {})
            parent_frame_id = parent.get("id") if parent else None
            parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

            # Build breadcrumbs including parent frame if present
            item_breadcrumbs = list(board_breadcrumbs)
            if parent_frame_id and parent_frame_title:
                item_breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_frame_id,
                        name=parent_frame_title,
                        entity_type="MiroFrameEntity",
                    )
                )

            yield MiroFrameEntity(
                # Base entity fields
                entity_id=item["id"],
                breadcrumbs=item_breadcrumbs,
                # API-specific fields
                item_id=item["id"],
                title=title,
                created_at=created_at,
                modified_at=modified_at,
                board_id=board_id,
                board_name=board_name,
                frame_id=parent_frame_id,
                frame_title=parent_frame_title,
                format=data.get("format"),
                frame_type=data.get("type"),
                created_by=item.get("createdBy"),
                modified_by=item.get("modifiedBy"),
            )

    async def _generate_tag_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[MiroTagEntity, None]:
        """Generate tag entities for a board."""
        url = f"{self.API_BASE}/boards/{board_id}/tags"

        try:
            async for item in self._paginate(client, url):
                snapshot_time = datetime.now(timezone.utc)
                title = item.get("title", "Untitled Tag")

                yield MiroTagEntity(
                    # Base entity fields
                    entity_id=item["id"],
                    breadcrumbs=board_breadcrumbs,
                    # API-specific fields
                    tag_id=item["id"],
                    title=title,
                    created_at=snapshot_time,
                    modified_at=snapshot_time,
                    board_id=board_id,
                    board_name=board_name,
                )
        except httpx.HTTPStatusError as e:
            # Tags endpoint may not be available for all boards
            if e.response.status_code == 404:
                self.logger.debug(f"Tags not available for board {board_id}")
            else:
                raise

    async def _generate_app_card_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroAppCardEntity, None]:
        """Generate app card entities for a board (Jira, GitHub, Asana integrations).

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/app_cards"

        try:
            async for item in self._paginate(client, url):
                data = item.get("data", {})
                title = self._strip_html(data.get("title", "")) or "Untitled App Card"
                description = self._strip_html(data.get("description", "")) or None
                created_at = self._parse_datetime(item.get("createdAt"))
                modified_at = self._parse_datetime(item.get("modifiedAt"))

                # Extract parent frame info
                parent = item.get("parent", {})
                parent_frame_id = parent.get("id") if parent else None
                parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

                # Build breadcrumbs including parent frame if present
                item_breadcrumbs = list(board_breadcrumbs)
                if parent_frame_id and parent_frame_title:
                    item_breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent_frame_id,
                            name=parent_frame_title,
                            entity_type="MiroFrameEntity",
                        )
                    )

                yield MiroAppCardEntity(
                    # Base entity fields
                    entity_id=item["id"],
                    breadcrumbs=item_breadcrumbs,
                    # API-specific fields
                    item_id=item["id"],
                    title=title,
                    created_at=created_at,
                    modified_at=modified_at,
                    board_id=board_id,
                    board_name=board_name,
                    frame_id=parent_frame_id,
                    frame_title=parent_frame_title,
                    description=description,
                    status=data.get("status"),
                    fields=data.get("fields", []),
                    owned=data.get("owned"),
                    created_by=item.get("createdBy"),
                    modified_by=item.get("modifiedBy"),
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.debug(f"App cards not available for board {board_id}")
            else:
                raise

    async def _generate_document_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroDocumentEntity, None]:
        """Generate document entities for a board (PDFs, DOCXs, etc.).

        Uses redirect=true to download files directly via API redirect,
        extracting filename from Content-Disposition header.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/documents"

        try:
            async for item in self._paginate(client, url):
                data = item.get("data", {})

                # Parse timestamps early for change detection
                created_at = self._parse_datetime(item.get("createdAt"))
                modified_at = self._parse_datetime(item.get("modifiedAt"))

                # Check if file has changed since last sync
                file_changed = self._has_file_changed(item["id"], modified_at)
                stored_filename = None
                if not file_changed:
                    # Get stored filename for unchanged files
                    stored_filename = self._get_stored_filename(item["id"])
                    self.logger.debug(f"Document {item['id']} unchanged, skipping download")

                # Extract documentUrl from data object
                document_url = data.get("documentUrl", "")
                if not document_url:
                    self.logger.warning(
                        f"No documentUrl for document {item['id']} on board {board_id}"
                    )
                    continue

                # Use redirect=true for direct download (API returns 307 redirect)
                # Filename will be extracted from Content-Disposition header
                if "redirect=false" in document_url:
                    document_url = document_url.replace("redirect=false", "redirect=true")
                elif "redirect=" not in document_url:
                    # Add redirect=true if not present
                    separator = "&" if "?" in document_url else "?"
                    document_url = f"{document_url}{separator}redirect=true"

                # Extract parent frame info
                parent = item.get("parent", {})
                parent_frame_id = parent.get("id") if parent else None
                parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

                # Build breadcrumbs including parent frame if present
                item_breadcrumbs = list(board_breadcrumbs)
                if parent_frame_id and parent_frame_title:
                    item_breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent_frame_id,
                            name=parent_frame_title,
                            entity_type="MiroFrameEntity",
                        )
                    )

                # Get title from API data
                title = data.get("title") or item["id"]

                file_entity = MiroDocumentEntity(
                    # Base entity fields
                    entity_id=item["id"],
                    breadcrumbs=item_breadcrumbs,
                    # Use stored filename for unchanged files, otherwise extract during download
                    name=stored_filename,
                    # FileEntity fields
                    url=document_url,  # API URL with redirect=true
                    size=0,  # Size not provided by API
                    file_type="document",
                    mime_type=None,
                    local_path=None,
                    # API-specific fields
                    item_id=item["id"],
                    title=title,
                    created_at=created_at,
                    modified_at=modified_at,
                    board_id=board_id,
                    board_name=board_name,
                    frame_id=parent_frame_id,
                    frame_title=parent_frame_title,
                    created_by=item.get("createdBy"),
                    modified_by=item.get("modifiedBy"),
                )

                # Only download if file has changed
                if file_changed:
                    # Download file using downloader
                    # Auth token needed for initial request, API redirects to file
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
                                f"Download failed - no local path set for document {item['id']}"
                            )

                        # Store metadata (including filename) for future change detection
                        self._store_file_metadata(
                            item["id"], modified_at, filename=file_entity.name
                        )

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping document {item['id']}: {e.reason}")
                        continue

                    except Exception as e:
                        self.logger.error(
                            f"Failed to download document {item['id']} from board {board_id}: {e}"
                        )
                        # Continue with next document, don't fail entire sync
                        continue

                # Always yield entity (even unchanged ones need to be "kept" in sync)
                yield file_entity

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.debug(f"Documents not available for board {board_id}")
            else:
                raise

    async def _generate_image_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_name: str,
        board_breadcrumbs: List[Breadcrumb],
        frame_lookup: Dict[str, str],
    ) -> AsyncGenerator[MiroImageEntity, None]:
        """Generate image entities for a board.

        Uses format=original for full resolution and redirect=true to download
        files directly via API redirect, extracting filename from Content-Disposition.

        Args:
            client: HTTP client
            board_id: Board ID
            board_name: Board name
            board_breadcrumbs: Breadcrumbs for hierarchy
            frame_lookup: Dict mapping frame_id -> frame_title for parent relationships
        """
        url = f"{self.API_BASE}/boards/{board_id}/images"

        try:
            async for item in self._paginate(client, url):
                data = item.get("data", {})

                # Parse timestamps early for change detection
                created_at = self._parse_datetime(item.get("createdAt"))
                modified_at = self._parse_datetime(item.get("modifiedAt"))

                # Check if file has changed since last sync
                file_changed = self._has_file_changed(item["id"], modified_at)
                stored_filename = None
                if not file_changed:
                    # Get stored filename for unchanged files
                    stored_filename = self._get_stored_filename(item["id"])
                    self.logger.debug(f"Image {item['id']} unchanged, skipping download")

                # Extract imageUrl from data object
                image_url = data.get("imageUrl", "")
                if not image_url:
                    self.logger.warning(f"No imageUrl for image {item['id']} on board {board_id}")
                    continue

                # Request original format (not preview) for full resolution
                if "format=preview" in image_url:
                    image_url = image_url.replace("format=preview", "format=original")

                # Use redirect=true for direct download (API returns 307 redirect)
                # Filename will be extracted from Content-Disposition header
                if "redirect=false" in image_url:
                    image_url = image_url.replace("redirect=false", "redirect=true")
                elif "redirect=" not in image_url:
                    # Add redirect=true if not present
                    separator = "&" if "?" in image_url else "?"
                    image_url = f"{image_url}{separator}redirect=true"

                # Extract parent frame info
                parent = item.get("parent", {})
                parent_frame_id = parent.get("id") if parent else None
                parent_frame_title = frame_lookup.get(parent_frame_id) if parent_frame_id else None

                # Build breadcrumbs including parent frame if present
                item_breadcrumbs = list(board_breadcrumbs)
                if parent_frame_id and parent_frame_title:
                    item_breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent_frame_id,
                            name=parent_frame_title,
                            entity_type="MiroFrameEntity",
                        )
                    )

                # Get title from API data
                title = data.get("title") or item["id"]

                file_entity = MiroImageEntity(
                    # Base entity fields
                    entity_id=item["id"],
                    breadcrumbs=item_breadcrumbs,
                    # Use stored filename for unchanged files, otherwise extract during download
                    name=stored_filename,
                    # FileEntity fields
                    url=image_url,  # API URL with format=original&redirect=true
                    size=0,  # Size not provided by API
                    file_type="image",
                    mime_type=None,
                    local_path=None,
                    # API-specific fields
                    item_id=item["id"],
                    title=title,
                    created_at=created_at,
                    modified_at=modified_at,
                    board_id=board_id,
                    board_name=board_name,
                    frame_id=parent_frame_id,
                    frame_title=parent_frame_title,
                    created_by=item.get("createdBy"),
                    modified_by=item.get("modifiedBy"),
                )

                # Only download if file has changed
                if file_changed:
                    # Download file using downloader
                    # Auth token needed for initial request, API redirects to file
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
                                f"Download failed - no local path set for image {item['id']}"
                            )

                        # Store metadata (including filename) for future change detection
                        self._store_file_metadata(
                            item["id"], modified_at, filename=file_entity.name
                        )

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping image {item['id']}: {e.reason}")
                        continue

                    except Exception as e:
                        self.logger.error(
                            f"Failed to download image {item['id']} from board {board_id}: {e}"
                        )
                        # Continue with next image, don't fail entire sync
                        continue

                # Always yield entity (even unchanged ones need to be "kept" in sync)
                yield file_entity

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.debug(f"Images not available for board {board_id}")
            else:
                raise

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Miro."""
        self.logger.info("Starting Miro sync")

        async with self.http_client() as client:
            async for board_entity in self._generate_board_entities(client):
                yield board_entity

                board_breadcrumb = Breadcrumb(
                    entity_id=board_entity.board_id,
                    name=board_entity.board_name,
                    entity_type="MiroBoardEntity",
                )
                board_breadcrumbs = [board_breadcrumb]
                board_id = board_entity.board_id
                board_name = board_entity.board_name

                self.logger.info(f"Processing board: {board_name}")

                # Fetch all board tags once to avoid N+1 queries
                board_tags = await self._get_board_tags(client, board_id)

                # Generate frames FIRST to build lookup for parent relationships
                # The frame_lookup maps frame_id -> frame_title for child items
                frame_lookup: Dict[str, str] = {}
                try:
                    async for frame in self._generate_frame_entities(
                        client, board_id, board_name, board_breadcrumbs, frame_lookup
                    ):
                        # Store in lookup for child items to reference
                        frame_lookup[frame.item_id] = frame.title
                        yield frame
                except Exception as e:
                    self.logger.error(f"Failed to generate frames for board {board_name}: {e}")

                # Generate sticky notes with error isolation
                try:
                    async for sticky_note in self._generate_sticky_note_entities(
                        client, board_id, board_name, board_breadcrumbs, board_tags, frame_lookup
                    ):
                        yield sticky_note
                except Exception as e:
                    self.logger.error(
                        f"Failed to generate sticky notes for board {board_name}: {e}"
                    )

                # Generate cards with error isolation
                try:
                    async for card in self._generate_card_entities(
                        client, board_id, board_name, board_breadcrumbs, board_tags, frame_lookup
                    ):
                        yield card
                except Exception as e:
                    self.logger.error(f"Failed to generate cards for board {board_name}: {e}")

                # Generate text items with error isolation
                try:
                    async for text in self._generate_text_entities(
                        client, board_id, board_name, board_breadcrumbs, frame_lookup
                    ):
                        yield text
                except Exception as e:
                    self.logger.error(f"Failed to generate text items for board {board_name}: {e}")

                # Generate tags with error isolation
                try:
                    async for tag in self._generate_tag_entities(
                        client, board_id, board_name, board_breadcrumbs
                    ):
                        yield tag
                except Exception as e:
                    self.logger.error(f"Failed to generate tags for board {board_name}: {e}")

                # Generate app cards (Jira, GitHub, Asana integrations) with error isolation
                try:
                    async for app_card in self._generate_app_card_entities(
                        client, board_id, board_name, board_breadcrumbs, frame_lookup
                    ):
                        yield app_card
                except Exception as e:
                    self.logger.error(f"Failed to generate app cards for board {board_name}: {e}")

                # Generate documents with error isolation
                try:
                    async for document in self._generate_document_entities(
                        client, board_id, board_name, board_breadcrumbs, frame_lookup
                    ):
                        yield document
                except Exception as e:
                    self.logger.error(f"Failed to generate documents for board {board_name}: {e}")

                # Generate images with error isolation
                try:
                    async for image in self._generate_image_entities(
                        client, board_id, board_name, board_breadcrumbs, frame_lookup
                    ):
                        yield image
                except Exception as e:
                    self.logger.error(f"Failed to generate images for board {board_name}: {e}")

        self.logger.info("Miro sync completed")

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Miro's boards endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.API_BASE}/boards?limit=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
