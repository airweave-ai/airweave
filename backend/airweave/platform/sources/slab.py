"""Slab source implementation for Airweave platform.

Slab is a team wiki and knowledge base platform. This connector extracts:
- Topics (IDs via search(types: [TOPIC]), full data via topics(ids))
- Posts (IDs via search(types: [POST]), full data via posts(ids))

With an authenticated token, organization is queried with no arguments (token scopes
to one org). Topic and post IDs plus comment payloads are discovered via search();
full topic/post records via topics(ids) and posts(ids). Comments are only in search
results (no batch fetch). We emit SlabCommentEntity for every comment; when the API
does not provide comment.post, we use placeholder post_id/post_title so comments
are still synced.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import SlabAuthConfig
from airweave.platform.configs.config import SlabConfig
from airweave.platform.decorators import source
from airweave.platform.entities.slab import SlabCommentEntity, SlabPostEntity, SlabTopicEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

SLAB_GRAPHQL_URL = "https://api.slab.com/v1/graphql"
POSTS_IDS_BATCH_SIZE = 100


@source(
    name="Slab",
    short_name="slab",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=SlabAuthConfig,
    config_class=SlabConfig,
    labels=["Knowledge Base", "Documentation"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class SlabSource(BaseSource):
    """Slab source connector integrates with the Slab GraphQL API to extract knowledge base content.

    Connects to your Slab workspace and synchronizes topics and posts.
    Comments are included via search() results (CommentSearchResult) and synced.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SlabConfig,
    ) -> SlabSource:
        """Create a new Slab source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        instance._host = config.host
        return instance

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict:
        """Send authenticated GraphQL query to Slab API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        response = await self.http_client.post(
            SLAB_GRAPHQL_URL,
            headers=headers,
            json={"query": query, "variables": variables or {}},
            timeout=30.0,
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        result = response.json()

        if "errors" in result:
            errors = result["errors"]
            error_messages = [err.get("message", "Unknown error") for err in errors]
            is_org_null = all(
                err.get("path") == ["organization"]
                and "null" in (err.get("message") or "").lower()
                and "non-nullable" in (err.get("message") or "").lower()
                for err in errors
            )
            if is_org_null:
                self.logger.warning(
                    "Slab API returned no organization for host %s. "
                    "Check that the host matches your Slab workspace.",
                    self._host,
                )
                return {"organization": None}
            self.logger.warning(f"GraphQL errors: {error_messages}")
            raise ValueError(f"GraphQL errors: {', '.join(error_messages)}")

        return result.get("data", {})

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_organization(self) -> Dict[str, Any]:
        """Fetch organization (id, name, host). Token scopes to one org; no host argument."""
        result = await self._post("query { organization { id name host } }")
        return result.get("organization") or {}

    def _process_search_edge(
        self, edge: Dict[str, Any]
    ) -> Tuple[List[str], List[str], Optional[Dict[str, Any]]]:
        """Extract topic id, post id, and/or comment payload from one search edge."""
        node = edge.get("node") or {}
        tids: List[str] = []
        pids: List[str] = []
        comment_payload: Optional[Dict[str, Any]] = None
        if node.get("topic"):
            tid = (node["topic"] or {}).get("id")
            if tid:
                tids.append(tid)
        if node.get("post"):
            pid = (node["post"] or {}).get("id")
            if pid:
                pids.append(pid)
        if node.get("comment"):
            comment = node.get("comment") or {}
            comment_payload = {
                "node_content": node.get("content"),
                "comment": comment,
            }
        return (tids, pids, comment_payload)

    async def _fetch_topic_and_post_ids_via_search(
        self,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """Discover topic IDs, post IDs, and comment payloads via search (cursor pagination).

        Topics and posts are then fetched in full via topics(ids) and posts(ids).
        Comments exist only in search results; we return their payloads.
        """
        topic_ids: List[str] = []
        post_ids: List[str] = []
        comments: List[Dict[str, Any]] = []
        page_size = 100
        after: Optional[str] = None

        query = """
        query($query: String!, $first: Int!, $after: String) {
            search(query: $query, first: $first, after: $after) {
                pageInfo { hasNextPage endCursor }
                edges {
                    node {
                        ... on TopicSearchResult { topic { id } }
                        ... on PostSearchResult { post { id } }
                        ... on CommentSearchResult {
                            content
                            comment {
                                id
                                content
                                insertedAt
                                author { id name email }
                            }
                        }
                    }
                }
            }
        }
        """
        while True:
            variables: Dict[str, Any] = {"query": "*", "first": page_size}
            if after is not None:
                variables["after"] = after
            result = await self._post(query, variables)
            search_data = result.get("search") or {}
            page_info = search_data.get("pageInfo") or {}
            edges = search_data.get("edges") or []

            for edge in edges:
                tids, pids, comment_payload = self._process_search_edge(edge)
                topic_ids.extend(tids)
                post_ids.extend(pids)
                if comment_payload is not None:
                    comments.append(comment_payload)

            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
            if not after:
                break

        return topic_ids, post_ids, comments

    async def _fetch_topics_batch(self, topic_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch full topic details by IDs (schema: topics(ids: [ID!]!) max 100)."""
        if not topic_ids:
            return []
        query = """
        query($ids: [ID!]!) {
            topics(ids: $ids) {
                id
                name
                description
                insertedAt
                updatedAt
            }
        }
        """
        result = await self._post(query, {"ids": topic_ids})
        return result.get("topics") or []

    async def _fetch_posts_batch(self, post_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch full post details by IDs (schema: posts(ids: [ID!]!))."""
        if not post_ids:
            return []
        query = """
        query($ids: [ID!]!) {
            posts(ids: $ids) {
                id
                title
                content
                insertedAt
                updatedAt
                archivedAt
                publishedAt
                linkAccess
                owner {
                    id
                    name
                    email
                }
                topics {
                    id
                    name
                }
                banner {
                    original
                }
            }
        }
        """
        result = await self._post(query, {"ids": post_ids})
        return result.get("posts") or []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Generate all entities from Slab.

        organization(host) returns PublicOrganization (id, name, host only).
        Topic and post IDs are discovered via search(); full data via topics(ids)
        and posts(ids). Comments are collected from search results and yielded.
        """
        self.logger.info("Starting Slab entity generation")

        org = await self._fetch_organization()
        host = (org.get("host") or "").strip() or self._host

        topic_ids, post_ids, comment_payloads = await self._fetch_topic_and_post_ids_via_search()

        topics_by_id: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(topic_ids), POSTS_IDS_BATCH_SIZE):
            batch_ids = topic_ids[i : i + POSTS_IDS_BATCH_SIZE]
            batch = await self._fetch_topics_batch(batch_ids)
            for topic_data in batch:
                tid = topic_data.get("id")
                if tid:
                    topics_by_id[tid] = topic_data

        for topic_data in topics_by_id.values():
            yield SlabTopicEntity.from_api(topic_data, host=host)

        for i in range(0, len(post_ids), POSTS_IDS_BATCH_SIZE):
            batch_ids = post_ids[i : i + POSTS_IDS_BATCH_SIZE]
            posts = await self._fetch_posts_batch(batch_ids)
            for post_data in posts:
                yield SlabPostEntity.from_api(post_data, topics_by_id=topics_by_id, host=host)

        for payload in comment_payloads:
            entity = SlabCommentEntity.from_api(payload, host=host)
            if entity:
                yield entity

        self.logger.info(
            f"Slab sync complete. {len(topics_by_id)} topics, "
            f"{len(post_ids)} posts, {len(comment_payloads)} comments"
        )

    async def validate(self) -> None:
        """Verify credentials by querying the organization info."""
        await self._post("query { organization { id name host } }")
