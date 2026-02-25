"""Slite source implementation.

Syncs notes (documents) from Slite. Uses the Slite Public API v1.
API reference: https://developers.slite.com/
Authentication: API key via x-slite-api-key header.
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.configs.auth import SliteAuthConfig
from airweave.platform.configs.config import SliteConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.slite import SliteNoteEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

SLITE_API_BASE = "https://api.slite.com/v1"


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string to datetime (naive UTC)."""
    if not s:
        return None
    try:
        # Slite returns "2024-01-01T00:00:00.000Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


@source(
    name="Slite",
    short_name="slite",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=None,
    auth_config_class=SliteAuthConfig,
    config_class=SliteConfig,
    labels=["Knowledge Base", "Documentation"],
    supports_continuous=False,
)
class SliteSource(BaseSource):
    """Slite source connector.

    Syncs notes (documents) from your Slite workspace. Uses a personal API key
    (Settings > API). List notes with optional parent filter, then fetches full
    content per note (markdown) for embedding.
    """

    @classmethod
    async def create(
        cls, credentials: SliteAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "SliteSource":
        """Create and configure the Slite source.

        Args:
            credentials: Slite auth config (API key).
            config: Optional source configuration (e.g., include_archived).

        Returns:
            Configured SliteSource instance.
        """
        instance = cls()
        instance.api_key = credentials.api_key
        config = config or {}
        instance.include_archived = config.get("include_archived", False)
        return instance

    def _headers(self) -> Dict[str, str]:
        """Build request headers. Slite uses x-slite-api-key (not Bearer)."""
        return {
            "x-slite-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Slite API."""
        try:
            response = await client.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Slite API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Slite API: {url}, {e}")
            raise

    async def _list_notes_page(
        self,
        client: httpx.AsyncClient,
        cursor: Optional[str] = None,
        parent_note_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch one page of notes. GET /v1/notes with optional cursor and parentNoteId."""
        params: Dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if parent_note_id:
            params["parentNoteId"] = parent_note_id
        return await self._get_with_auth(client, f"{SLITE_API_BASE}/notes", params=params or None)

    async def _get_note_by_id(
        self, client: httpx.AsyncClient, note_id: str, format: str = "md"
    ) -> Dict[str, Any]:
        """Fetch a single note with content. GET /v1/notes/{noteId}?format=md."""
        return await self._get_with_auth(
            client,
            f"{SLITE_API_BASE}/notes/{note_id}",
            params={"format": format},
        )

    async def _list_all_notes(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all notes (root and nested) via pagination. Then yield each note."""
        cursor: Optional[str] = None
        seen_ids: set = set()

        while True:
            page = await self._list_notes_page(client, cursor=cursor)
            notes = page.get("notes") or []
            for note in notes:
                nid = note.get("id")
                if nid and nid not in seen_ids:
                    seen_ids.add(nid)
                    yield note
            if not page.get("hasNextPage") or not page.get("nextCursor"):
                break
            cursor = page.get("nextCursor")

    async def _generate_note_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[SliteNoteEntity, None]:
        """List notes, fetch full content for each, yield SliteNoteEntity."""
        self.logger.info("Fetching Slite notes...")
        async for note in self._list_all_notes(client):
            note_id = note.get("id")
            if not note_id:
                continue
            archived_at = note.get("archivedAt")
            if archived_at and not getattr(self, "include_archived", False):
                self.logger.debug(f"Skipping archived note: {note_id}")
                continue
            try:
                full_note = await self._get_note_by_id(client, note_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.warning(f"Note not found (404): {note_id}, skipping")
                    continue
                raise
            breadcrumbs: List[Breadcrumb] = []
            parent_id = full_note.get("parentNoteId")
            if parent_id:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_id,
                        name=parent_id,
                        entity_type="SliteNoteEntity",
                    )
                )
            last_edited = _parse_iso(full_note.get("lastEditedAt"))
            updated = _parse_iso(full_note.get("updatedAt"))
            archived_dt = (
                _parse_iso(full_note.get("archivedAt")) if full_note.get("archivedAt") else None
            )
            owner = full_note.get("owner")
            if isinstance(owner, dict):
                owner = {k: v for k, v in owner.items() if v is not None}
            else:
                owner = None
            yield SliteNoteEntity(
                entity_id=note_id,
                breadcrumbs=breadcrumbs,
                note_id=note_id,
                name=full_note.get("title") or note_id,
                content=full_note.get("content"),
                parent_note_id=full_note.get("parentNoteId"),
                created_at=last_edited or updated,
                modified_at=last_edited,
                updated_at=updated,
                archived_at=archived_dt,
                review_state=full_note.get("reviewState"),
                owner=owner,
                columns=full_note.get("columns") or [],
                attributes=full_note.get("attributes") or [],
                web_url_value=full_note.get("url"),
            )

    async def generate_entities(self) -> AsyncGenerator[SliteNoteEntity, None]:
        """Generate all note entities from Slite."""
        async with self.http_client() as client:
            async for entity in self._generate_note_entities(client):
                yield entity

    async def validate(self) -> bool:
        """Validate API key by listing one page of notes."""
        try:
            async with self.http_client() as client:
                page = await self._list_notes_page(client)
                return "notes" in page
        except Exception as e:
            self.logger.error(f"Slite validation failed: {e}")
            return False
