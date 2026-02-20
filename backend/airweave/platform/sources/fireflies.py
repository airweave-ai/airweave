"""Fireflies source implementation.

Syncs meeting transcripts from the Fireflies GraphQL API.
See https://docs.fireflies.ai/graphql-api/query/transcripts and
https://docs.fireflies.ai/schema/transcript.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.configs.auth import FirefliesAuthConfig
from airweave.platform.configs.config import FirefliesConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.fireflies import FirefliesTranscriptEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

FIREFLIES_GRAPHQL_URL = "https://api.fireflies.ai/graphql"
TRANSCRIPTS_PAGE_SIZE = 50


@source(
    name="Fireflies",
    short_name="fireflies",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=FirefliesAuthConfig,
    config_class=FirefliesConfig,
    labels=["Meetings", "Transcription", "Productivity"],
    supports_continuous=False,
)
class FirefliesSource(BaseSource):
    """Fireflies source connector.

    Syncs meeting transcripts from Fireflies.ai. Uses the GraphQL API with
    Bearer token (API key) authentication.
    """

    @classmethod
    async def create(
        cls,
        credentials: FirefliesAuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "FirefliesSource":
        """Create and configure the Fireflies source.

        Args:
            credentials: Fireflies API key from app.fireflies.ai/integrations.
            config: Optional source configuration (unused for now).

        Returns:
            Configured FirefliesSource instance.
        """
        instance = cls()
        api_key = (credentials.api_key or "").strip()
        if not api_key:
            raise ValueError(
                "Fireflies API key is required. Get it from app.fireflies.ai/integrations."
            )
        instance.api_key = api_key
        return instance

    async def _graphql(
        self, client: httpx.AsyncClient, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL request against the Fireflies API.

        Args:
            client: HTTP client.
            query: GraphQL query or mutation string (will be stripped).
            variables: Optional variables dict.

        Returns:
            JSON response body (data or errors).

        Raises:
            httpx.HTTPStatusError: On non-2xx response (message includes response body).
            ValueError: If the response contains GraphQL errors.
        """
        payload: Dict[str, Any] = {"query": query.strip()}
        if variables:
            payload["variables"] = variables
        response = await client.post(
            FIREFLIES_GRAPHQL_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            body = response.text
            try:
                err_json = response.json()
                if "errors" in err_json and err_json["errors"]:
                    messages = [e.get("message", str(e)) for e in err_json["errors"]]
                    body = "; ".join(messages)
            except Exception:
                pass
            raise httpx.HTTPStatusError(
                f"Fireflies API {response.status_code}: {body}",
                request=response.request,
                response=response,
            )
        data = response.json()
        if "errors" in data and data["errors"]:
            msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
            raise ValueError(f"Fireflies GraphQL errors: {msg}")
        return data

    @staticmethod
    def _parse_date(ms: Optional[float]) -> Optional[datetime]:
        """Convert milliseconds since epoch to UTC datetime."""
        if ms is None:
            return None
        try:
            return datetime.utcfromtimestamp(ms / 1000.0)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _normalize_action_items(value: Any) -> Optional[List[str]]:
        """Normalize action_items from API (string or list) to List[str]."""
        if value is None:
            return None
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            return [s.strip() for s in value.split("\n") if s.strip()] or None
        return None

    def _transcript_to_entity(self, t: Dict[str, Any]) -> FirefliesTranscriptEntity:
        """Map a raw transcript object from the API to FirefliesTranscriptEntity."""
        transcript_id = t.get("id") or ""
        title = t.get("title") or "Untitled meeting"
        date_ms = t.get("date")
        created_time = self._parse_date(date_ms)
        summary = t.get("summary") or {}
        sentences = t.get("sentences") or []
        content_parts = []
        for s in sentences:
            raw = (s.get("raw_text") or s.get("text") or "").strip()
            if raw:
                content_parts.append(raw)
        content = "\n".join(content_parts) if content_parts else None

        return FirefliesTranscriptEntity(
            entity_id=transcript_id,
            breadcrumbs=[],
            name=title,
            created_at=created_time,
            updated_at=created_time,
            transcript_id=transcript_id,
            title=title,
            organizer_email=t.get("organizer_email"),
            transcript_url=t.get("transcript_url"),
            participants=t.get("participants") or [],
            duration=t.get("duration"),
            date=date_ms,
            date_string=t.get("dateString"),
            created_time=created_time,
            speakers=t.get("speakers") or [],
            summary_overview=summary.get("overview") or summary.get("short_summary"),
            summary_keywords=summary.get("keywords") or [],
            summary_action_items=self._normalize_action_items(summary.get("action_items")),
            content=content,
            fireflies_users=t.get("fireflies_users") or [],
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate transcript entities from the Fireflies API.

        Paginates through the transcripts query (limit 50 per request).
        """
        query = """
        query Transcripts($limit: Int, $skip: Int) {
          transcripts(limit: $limit, skip: $skip, mine: true) {
            id
            title
            organizer_email
            transcript_url
            participants
            duration
            date
            dateString
            fireflies_users
            speakers { id name }
            summary {
              overview
              short_summary
              keywords
              action_items
            }
            sentences {
              raw_text
              text
              speaker_name
            }
          }
        }
        """
        skip = 0
        async with self.http_client() as client:
            while True:
                variables = {"limit": TRANSCRIPTS_PAGE_SIZE, "skip": skip}
                data = await self._graphql(client, query, variables)
                transcripts = (data.get("data") or {}).get("transcripts") or []
                if not transcripts:
                    break
                for t in transcripts:
                    yield self._transcript_to_entity(t)
                if len(transcripts) < TRANSCRIPTS_PAGE_SIZE:
                    break
                skip += TRANSCRIPTS_PAGE_SIZE

    async def validate(self) -> bool:
        """Validate credentials by running a minimal transcripts query.

        Returns:
            True if the API key is valid and the request succeeds.
        """
        query = """
        query Validate {
          transcripts(limit: 1, mine: true) {
            id
          }
        }
        """
        try:
            async with self.http_client() as client:
                await self._graphql(client, query)
            return True
        except (httpx.HTTPStatusError, ValueError):
            return False
