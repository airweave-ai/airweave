"""Slite source implementation.

Syncs notes (documents) from Slite. Uses the Slite Public API v1.
API reference: https://developers.slite.com/
Authentication: API key via x-slite-api-key header.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import SliteAuthConfig
from airweave.platform.configs.config import SliteConfig
from airweave.platform.decorators import source
from airweave.platform.entities.slite import SliteNoteEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

SLITE_API_BASE = "https://api.slite.com/v1"


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
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SliteConfig,
    ) -> SliteSource:
        """Create and configure the Slite source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        instance._include_archived = config.include_archived
        return instance

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        """Build request headers. Slite uses x-slite-api-key (not Bearer)."""
        return {
            "x-slite-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Authenticated GET with retry on 429/5xx/timeout."""
        response = await self.http_client.get(
            url, headers=self._headers(), params=params, timeout=30.0
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _list_notes_page(
        self,
        cursor: Optional[str] = None,
        parent_note_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch one page of notes. GET /v1/notes with optional cursor and parentNoteId."""
        params: Dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if parent_note_id:
            params["parentNoteId"] = parent_note_id
        return await self._get(f"{SLITE_API_BASE}/notes", params=params or None)

    async def _get_note_by_id(self, note_id: str, format: str = "md") -> Dict[str, Any]:
        """Fetch a single note with content. GET /v1/notes/{noteId}?format=md."""
        return await self._get(
            f"{SLITE_API_BASE}/notes/{note_id}",
            params={"format": format},
        )

    async def _list_all_notes(self) -> AsyncGenerator[Dict[str, Any], None]:
        """List all notes via pagination. Yields each note."""
        cursor: Optional[str] = None
        seen_ids: set[str] = set()

        while True:
            page = await self._list_notes_page(cursor=cursor)
            notes = page.get("notes") or []
            for note in notes:
                nid = note.get("id")
                if nid and nid not in seen_ids:
                    seen_ids.add(nid)
                    yield note
            if not page.get("hasNextPage") or not page.get("nextCursor"):
                break
            cursor = page.get("nextCursor")

    # ------------------------------------------------------------------
    # Entity generation
    # ------------------------------------------------------------------

    async def _generate_note_entities(self) -> AsyncGenerator[SliteNoteEntity, None]:
        """List notes, fetch full content for each, yield SliteNoteEntity."""
        self.logger.info("Fetching Slite notes...")
        async for note in self._list_all_notes():
            note_id = note.get("id")
            if not note_id:
                continue

            archived_at = note.get("archivedAt")
            if archived_at and not self._include_archived:
                self.logger.debug(f"Skipping archived note: {note_id}")
                continue

            try:
                full_note = await self._get_note_by_id(note_id)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to fetch note {note_id}: {e}")
                continue

            yield SliteNoteEntity.from_api(full_note)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[SliteNoteEntity, None]:
        """Generate all note entities from Slite."""
        async for entity in self._generate_note_entities():
            yield entity

    async def validate(self) -> None:
        """Validate API key by listing one page of notes."""
        await self._list_notes_page()
