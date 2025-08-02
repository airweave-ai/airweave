import httpx
import tenacity
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict
from tenacity import retry, stop_after_attempt, wait_exponential

from ..entities.evernote import EvernoteNote, EvernoteNotebook, EvernoteTag
from ..entities._base import ChunkEntity, Breadcrumb
from ._base import BaseSource, source, AuthType


@source("Evernote", "evernote", AuthType.oauth2_with_refresh)
class EvernoteSource(BaseSource):
    """Evernote source implementation."""

    BASE_URL = "https://api.evernote.com/edam/note"
    API_VERSION = "v1"

    @classmethod
    async def create(cls, access_token: str) -> "EvernoteSource":
        """Create a new source instance with authentication."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None) -> dict:
        """Make authenticated API request."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _generate_notebook_entities(self, client: httpx.AsyncClient) -> AsyncGenerator[EvernoteNotebook, None]:
        """Generate notebook entities."""
        url = f"{self.BASE_URL}/{self.API_VERSION}/notebooks"
        
        response = await self._get_with_auth(client, url)
        
        for notebook in response.get("notebooks", []):
            yield EvernoteNotebook(
                entity_id=notebook["guid"],
                name=notebook["name"],
                stack=notebook.get("stack"),
                created=datetime.fromtimestamp(notebook["created"] / 1000),
                updated=datetime.fromtimestamp(notebook["updated"] / 1000),
                shared=bool(notebook.get("sharedNotebooks")),
                content=notebook["name"],  # Using name as content for searchability
            )

    async def _generate_tag_entities(self, client: httpx.AsyncClient) -> AsyncGenerator[EvernoteTag, None]:
        """Generate tag entities."""
        url = f"{self.BASE_URL}/{self.API_VERSION}/tags"
        
        response = await self._get_with_auth(client, url)
        
        for tag in response.get("tags", []):
            yield EvernoteTag(
                entity_id=tag["guid"],
                name=tag["name"],
                parent_guid=tag.get("parentGuid"),
                update_sequence_num=tag["updateSequenceNum"],
                content=tag["name"],  # Using name as content for searchability
            )

    async def _generate_note_entities(self, client: httpx.AsyncClient) -> AsyncGenerator[EvernoteNote, None]:
        """Generate note entities."""
        url = f"{self.BASE_URL}/{self.API_VERSION}/notes"
        
        # Handle pagination
        offset = 0
        limit = 100
        
        while True:
            params = {
                "offset": offset,
                "limit": limit,
                "includeContent": True,
            }
            
            response = await self._get_with_auth(client, url, params)
            notes = response.get("notes", [])
            
            if not notes:
                break
                
            for note in notes:
                yield EvernoteNote(
                    entity_id=note["guid"],
                    title=note["title"],
                    content=note["content"],
                    created=datetime.fromtimestamp(note["created"] / 1000),
                    updated=datetime.fromtimestamp(note["updated"] / 1000),
                    notebook_guid=note["notebookGuid"],
                    tag_guids=note.get("tagGuids", []),
                    attributes=note.get("attributes"),
                )
            
            offset += len(notes)
            if len(notes) < limit:
                break

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Main entry point to generate all entities."""
        async with httpx.AsyncClient() as client:
            # First generate notebooks
            async for notebook in self._generate_notebook_entities(client):
                yield notebook
                
                # Create breadcrumb for notes
                notebook_breadcrumb = Breadcrumb(
                    entity_id=notebook.entity_id,
                    name=notebook.name,
                    type="notebook"
                )
            
            # Then generate tags
            async for tag in self._generate_tag_entities(client):
                yield tag
            
            # Finally generate notes with notebook breadcrumbs
            async for note in self._generate_note_entities(client):
                note.breadcrumbs = [notebook_breadcrumb]
                yield note 