"""Fireflies-specific bongo implementation.

Monke creates test transcripts by giving Fireflies a public audio URL; Fireflies
transcribes it and we poll until the transcript exists. Airweave then syncs only
the transcript text (no media). We need the audio URL only so Fireflies can create
a transcript for the test.

Create (upload URL + poll) → sync → verify → update → delete → cleanup.
Requires Fireflies paid plan for uploads.
"""

import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

FIREFLIES_GRAPHQL_URL = "https://api.fireflies.ai/graphql"
# deleteTranscript is rate-limited to 10/min
DELETE_RATE_LIMIT_SECONDS = 6.5
POLL_INTERVAL_SECONDS = 20


class FirefliesBongo(BaseBongo):
    """Bongo for Fireflies: upload audio URL, poll for transcript, update title, delete, cleanup."""

    connector_type = "fireflies"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Fireflies bongo.

        Args:
            credentials: Must contain api_key (Bearer).
            **kwargs: entity_count, audio_url, transcript_ready_timeout_seconds, etc.
        """
        super().__init__(credentials)
        self.api_key = credentials.get("api_key")
        if not self.api_key:
            raise ValueError(
                "Missing Fireflies api_key. Set MONKE_FIREFLIES_API_KEY."
            )

        self.entity_count = int(kwargs.get("entity_count", 1))
        # Public audio URL for Fireflies to transcribe (creates a transcript for the test)
        self.audio_url = (kwargs.get("audio_url") or "").strip() or os.getenv(
            "MONKE_FIREFLIES_AUDIO_URL", ""
        ).strip()
        if not self.audio_url:
            raise ValueError(
                "Fireflies test needs a public audio URL so Fireflies can create a transcript. "
                "Set audio_url in config or MONKE_FIREFLIES_AUDIO_URL."
            )
        self.transcript_ready_timeout_seconds = int(
            kwargs.get("transcript_ready_timeout_seconds", 300)
        )
        self.logger = get_logger("fireflies_bongo")

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def _graphql(
        self,
        client: httpx.AsyncClient,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL request. Raises on HTTP or GraphQL errors."""
        payload: Dict[str, Any] = {"query": query.strip()}
        if variables:
            payload["variables"] = variables
        resp = await client.post(
            FIREFLIES_GRAPHQL_URL,
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            body = resp.text
            try:
                err_json = resp.json()
                if "errors" in err_json and err_json["errors"]:
                    messages = [e.get("message", str(e)) for e in err_json["errors"]]
                    body = "; ".join(messages)
            except Exception:
                pass
            raise httpx.HTTPStatusError(
                f"Fireflies API {resp.status_code}: {body}",
                request=resp.request,
                response=resp,
            )
        data = resp.json()
        if "errors" in data and data["errors"]:
            messages = [e.get("message", str(e)) for e in data["errors"]]
            raise RuntimeError(f"Fireflies GraphQL errors: {'; '.join(messages)}")
        return data

    async def _upload_audio(
        self,
        client: httpx.AsyncClient,
        title: str,
        client_reference_id: Optional[str] = None,
    ) -> None:
        """Send audio URL to Fireflies; they transcribe it and create a transcript (queued)."""
        mutation = """
        mutation UploadAudio($input: AudioUploadInput) {
          uploadAudio(input: $input) {
            success
            title
            message
          }
        }
        """
        inp: Dict[str, Any] = {
            "url": self.audio_url,
            "title": title,
            "bypass_size_check": True,
        }
        if client_reference_id:
            inp["client_reference_id"] = client_reference_id
        await self._graphql(client, mutation, {"input": inp})

    async def _list_transcripts(
        self, client: httpx.AsyncClient, limit: int = 50, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Return list of transcripts (id, title) for mine: true."""
        query = """
        query Transcripts($limit: Int, $skip: Int) {
          transcripts(limit: $limit, skip: $skip, mine: true) {
            id
            title
          }
        }
        """
        data = await self._graphql(
            client, query, {"limit": limit, "skip": skip}
        )
        return (data.get("data") or {}).get("transcripts") or []

    async def _find_transcript_by_title(
        self, client: httpx.AsyncClient, title_substring: str
    ) -> Optional[Dict[str, Any]]:
        """Scan transcripts (paginated) and return first whose title contains title_substring."""
        skip = 0
        while True:
            batch = await self._list_transcripts(client, limit=50, skip=skip)
            if not batch:
                return None
            for t in batch:
                if title_substring in (t.get("title") or ""):
                    return t
            if len(batch) < 50:
                return None
            skip += 50

    async def _poll_for_transcript(
        self, client: httpx.AsyncClient, token: str, title: str
    ) -> Optional[str]:
        """Poll until a transcript with title containing token appears; return its id or None."""
        deadline = time.monotonic() + self.transcript_ready_timeout_seconds
        while time.monotonic() < deadline:
            transcript = await self._find_transcript_by_title(client, token)
            if transcript:
                return transcript.get("id")
            self.logger.info(
                f"   Waiting for transcript '{title}' to be ready (poll every {POLL_INTERVAL_SECONDS}s)..."
            )
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        return None

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Upload audio URL to Fireflies (title with token), poll until transcript exists."""
        self.logger.info(
            f"🥁 Creating {self.entity_count} Fireflies transcript(s) via upload + poll"
        )
        entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient() as client:
            for _ in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                title = f"Monke Test [{token}]"
                self.logger.info(f"   Uploading audio with title: {title}")
                await self._upload_audio(
                    client, title, client_reference_id=token
                )
                transcript_id = await self._poll_for_transcript(
                    client, token, title
                )
                if not transcript_id:
                    raise RuntimeError(
                        f"Transcript for '{title}' did not appear within "
                        f"{self.transcript_ready_timeout_seconds}s"
                    )
                self.logger.info(f"   ✅ Transcript ready: {transcript_id}")
                entities.append(
                    {
                        "type": "transcript",
                        "id": transcript_id,
                        "token": token,
                        "title": title,
                        "expected_content": token,
                    }
                )

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update meeting title for first transcript so token remains searchable."""
        if not self.created_entities:
            return []

        self.logger.info("🥁 Updating Fireflies transcript title(s)")
        updated: List[Dict[str, Any]] = []
        to_update = self.created_entities[:1]

        async with httpx.AsyncClient() as client:
            mutation = """
            mutation UpdateMeetingTitle($input: UpdateMeetingTitleInput!) {
              updateMeetingTitle(input: $input) {
                title
              }
            }
            """
            for entity in to_update:
                token = entity.get("token", "")
                new_title = f"Monke Test [{token}] (updated)"
                try:
                    await self._graphql(
                        client,
                        mutation,
                        {
                            "input": {
                                "id": entity["id"],
                                "title": new_title,
                            }
                        },
                    )
                    updated.append(
                        {**entity, "title": new_title, "expected_content": token}
                    )
                    self.logger.info(f"   ✅ Updated title: {entity['id']}")
                except Exception as e:
                    self.logger.warning(
                        f"   updateMeetingTitle failed (may require admin): {e}"
                    )
                    updated.append(entity)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created transcripts (rate-limited)."""
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete given transcripts via deleteTranscript; 10/min rate limit."""
        self.logger.info(f"🥁 Deleting {len(entities)} Fireflies transcript(s)")
        deleted: List[str] = []
        mutation = """
        mutation DeleteTranscript($id: String!) {
          deleteTranscript(id: $id) {
            title
          }
        }
        """
        async with httpx.AsyncClient() as client:
            for i, entity in enumerate(entities):
                if i > 0:
                    await asyncio.sleep(DELETE_RATE_LIMIT_SECONDS)
                try:
                    await self._graphql(
                        client, mutation, {"id": entity["id"]}
                    )
                    deleted.append(entity["id"])
                    self.logger.info(f"   ✅ Deleted: {entity['id']}")
                except Exception as e:
                    self.logger.warning(
                        f"   deleteTranscript failed for {entity['id']}: {e}"
                    )
        return deleted

    async def cleanup(self) -> None:
        """Find transcripts with 'Monke Test' in title and delete them (rate-limited)."""
        self.logger.info("🥁 Cleanup: removing any remaining Monke Test transcripts")
        async with httpx.AsyncClient() as client:
            to_delete: List[Dict[str, Any]] = []
            skip = 0
            while True:
                batch = await self._list_transcripts(client, limit=50, skip=skip)
                if not batch:
                    break
                for t in batch:
                    if "Monke Test" in (t.get("title") or ""):
                        to_delete.append(
                            {"id": t["id"], "title": t.get("title", "")}
                        )
                if len(batch) < 50:
                    break
                skip += 50

            if to_delete:
                mutation = """
                mutation DeleteTranscript($id: String!) {
                  deleteTranscript(id: $id) { title }
                }
                """
                for i, t in enumerate(to_delete):
                    if i > 0:
                        await asyncio.sleep(DELETE_RATE_LIMIT_SECONDS)
                    try:
                        await self._graphql(
                            client, mutation, {"id": t["id"]}
                        )
                        self.logger.info(f"   ✅ Cleanup deleted: {t['id']}")
                    except Exception as e:
                        self.logger.warning(
                            f"   Cleanup delete failed for {t['id']}: {e}"
                        )
            else:
                self.logger.info("   No Monke Test transcripts to clean up")
