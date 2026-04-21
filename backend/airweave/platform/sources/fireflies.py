"""Fireflies source implementation.

Syncs meeting transcripts from the Fireflies GraphQL API.
See https://docs.fireflies.ai/graphql-api/query/transcripts and
https://docs.fireflies.ai/schema/transcript.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import FirefliesAuthConfig
from airweave.platform.configs.config import FirefliesConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.fireflies import FirefliesTranscriptEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

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
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: FirefliesConfig,
    ) -> FirefliesSource:
        """Create and configure the Fireflies source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _graphql(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL request against the Fireflies API.

        Args:
            query: GraphQL query or mutation string (will be stripped).
            variables: Optional variables dict.

        Returns:
            JSON response body (data or errors).

        Raises:
            SourceAuthError: On 401 (credentials invalid or revoked).
            SourceError: On GraphQL-level errors.
        """
        payload: Dict[str, Any] = {"query": query.strip()}
        if variables:
            payload["variables"] = variables

        token = self._api_key
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        response = await self.http_client.post(
            FIREFLIES_GRAPHQL_URL,
            json=payload,
            headers=headers,
            timeout=30.0,
        )

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.post(
                FIREFLIES_GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=30.0,
            )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        data = response.json()
        if "errors" in data and data["errors"]:
            msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
            raise SourceError(
                f"Fireflies GraphQL errors: {msg}",
                source_short_name=self.short_name,
            )
        return data

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
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
        while True:
            variables = {"limit": TRANSCRIPTS_PAGE_SIZE, "skip": skip}
            try:
                data = await self._graphql(query, variables)
            except SourceAuthError:
                raise
            except SourceError:
                raise
            except Exception as e:
                self.logger.warning(f"Error fetching transcripts at skip={skip}: {e}")
                break
            transcripts = (data.get("data") or {}).get("transcripts") or []
            if not transcripts:
                break
            for t in transcripts:
                yield FirefliesTranscriptEntity.from_api(t)
            if len(transcripts) < TRANSCRIPTS_PAGE_SIZE:
                break
            skip += TRANSCRIPTS_PAGE_SIZE

    async def validate(self) -> None:
        """Validate credentials by running a minimal transcripts query."""
        query = """
        query Validate {
          transcripts(limit: 1, mine: true) {
            id
          }
        }
        """
        await self._graphql(query)
