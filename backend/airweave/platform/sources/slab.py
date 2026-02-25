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

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import SlabAuthConfig
from airweave.platform.configs.config import SlabConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.slab import SlabCommentEntity, SlabPostEntity, SlabTopicEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

# GraphQL endpoint for Slab API (per https://studio.apollographql.com/public/Slab/variant/current/home)
SLAB_GRAPHQL_URL = "https://api.slab.com/v1/graphql"
# Max post IDs per batch (schema constraint)
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

    def __init__(self):
        """Initialize the SlabSource with rate limiting state."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "topics_found": 0,
            "posts_found": 0,
            "comments_found": 0,
        }

    @classmethod
    async def create(
        cls,
        credentials: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> "SlabSource":
        """Create instance of the Slab source with authentication token and config.

        Args:
            credentials: SlabAuthConfig (with api_key) or raw API token string
                (e.g. when using token injection for sync).
            config: Optional configuration parameters.

        Returns:
            Configured SlabSource instance.
        """
        instance = cls()
        if isinstance(credentials, SlabAuthConfig):
            instance.api_key = credentials.api_key
        elif isinstance(credentials, str) and credentials.strip():
            instance.api_key = credentials.strip()
        elif isinstance(credentials, dict):
            # Auth provider (e.g. Pipedream) may pass dict with api_key or api_token
            token = (credentials.get("api_key") or credentials.get("api_token") or "").strip()
            if not token:
                raise ValueError(
                    "Slab source requires credentials dict with 'api_key' or 'api_token'"
                )
            instance.api_key = token
        else:
            raise ValueError(
                "Slab source requires SlabAuthConfig, a non-empty API token string, "
                "or a credentials dict with api_key/api_token"
            )
        config = config or {}
        instance.host = (config.get("host") or "app.slab.com").strip()
        return instance

    async def _wait_for_rate_limit(self):
        """Implement rate limiting for Slab API requests.

        Slab API has rate limits, so we implement basic throttling.
        """
        async with self._lock:
            current_time = asyncio.get_event_loop().time()

            # Remove old request times (keep last minute)
            minute_ago = current_time - 60
            self._request_times = [t for t in self._request_times if t > minute_ago]

            # If we've made many requests recently, wait
            if len(self._request_times) >= 60:  # 60 requests per minute
                wait_time = 1.0
                if self._request_times:
                    last_request = max(self._request_times)
                    sleep_time = last_request + wait_time - current_time
                    if sleep_time > 0:
                        self.logger.debug(f"Rate limit throttling. Waiting {sleep_time:.2f}s")
                        self._stats["rate_limit_waits"] += 1
                        await asyncio.sleep(sleep_time)

            # Record this request
            self._request_times.append(current_time)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_graphql(
        self, client: httpx.AsyncClient, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Send authenticated GraphQL query to Slab API with rate limiting.

        Args:
            client: HTTP client to use for the request
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            JSON response from the API

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        await self._wait_for_rate_limit()
        self._stats["api_calls"] += 1

        try:
            response = await client.post(
                SLAB_GRAPHQL_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={"query": query, "variables": variables or {}},
                timeout=30.0,
            )
            response.raise_for_status()

            result = response.json()

            # Check for GraphQL errors
            if "errors" in result:
                errors = result["errors"]
                error_messages = [err.get("message", "Unknown error") for err in errors]
                # When the API returns null for organization (wrong host or no access),
                # treat as "no organization" so validate() can return False without raising.
                is_org_null = all(
                    err.get("path") == ["organization"]
                    and "null" in (err.get("message") or "").lower()
                    and "non-nullable" in (err.get("message") or "").lower()
                    for err in errors
                )
                if is_org_null:
                    self.logger.warning(
                        "Slab API returned no organization for host %s. "
                        "Check that the host matches your Slab workspace "
                        "(e.g. from the URL when logged in) and that the API token has access.",
                        getattr(self, "host", "app.slab.com"),
                    )
                    return {"organization": None}
                self.logger.error(f"GraphQL errors: {error_messages}")
                raise httpx.HTTPStatusError(
                    f"GraphQL errors: {', '.join(error_messages)}",
                    request=response.request,
                    response=response,
                )

            return result.get("data", {})
        except httpx.HTTPStatusError as e:
            # Log error details
            try:
                error_content = e.response.json()
                self.logger.error(f"GraphQL API error: {error_content}")
            except Exception:
                self.logger.error(f"HTTP Error content: {e.response.text}")
            raise

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object.

        Args:
            datetime_str: ISO format datetime string

        Returns:
            datetime object or None if parsing fails
        """
        if not datetime_str:
            return None

        try:
            # Handle ISO format with timezone
            if datetime_str.endswith("Z"):
                datetime_str = datetime_str[:-1] + "+00:00"

            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))

            # Convert to UTC if it has timezone info, then make it naive
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

            return dt
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Could not parse datetime: {datetime_str}, error: {e}")
            return None

    @staticmethod
    def _quill_delta_to_plain_text(content: Any) -> str:
        """Convert Slab/Quill content (JSON delta) to plain text for embedding.

        Slab stores post content as Quill delta: array of ops, e.g.
        [{"insert": "Hello "}, {"insert": "World", "attributes": {"bold": true}}]
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        parts = []
        for op in content:
            if not isinstance(op, dict):
                continue
            insert = op.get("insert")
            if isinstance(insert, str):
                parts.append(insert)
            elif isinstance(insert, dict):
                # Embed (e.g. image) - optional label
                if "image" in insert:
                    parts.append("[image]")
                else:
                    parts.append("[embed]")
        return "".join(parts).strip()

    @staticmethod
    def _json_description_to_string(description: Any) -> Optional[str]:
        """Convert Topic.description (Json) to a single string for display/search."""
        if description is None:
            return None
        if isinstance(description, str):
            return description
        if isinstance(description, list):
            return " ".join(str(item) for item in description if item is not None).strip() or None
        if isinstance(description, dict):
            # Could be a delta or object; try to get text
            text = description.get("text") or description.get("content")
            if text:
                return str(text)
            return str(description)
        return str(description)

    async def validate(self) -> bool:
        """Verify credentials by querying the organization info.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with self.http_client() as client:
                # Authenticated token scopes to one org; organization takes no arguments.
                result = await self._post_graphql(
                    client,
                    "query { organization { id name host } }",
                    variables=None,
                )
                return "organization" in result and result["organization"] is not None
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return False

    async def _fetch_organization(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Fetch organization (id, name, host). Token scopes to one org; no host argument.

        Topic and post IDs are obtained via search(), not from organization.
        """
        query = """
        query {
            organization {
                id
                name
                host
            }
        }
        """
        result = await self._post_graphql(client, query, variables=None)
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
        self, client: httpx.AsyncClient
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """Discover topic IDs, post IDs, and full comment payloads via search (cursor pagination).

        Topics and posts are then fetched in full via topics(ids) and posts(ids).
        Comments exist only in search results (no batch API); we return their payloads.
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
            variables: Dict[str, Any] = {
                "query": "*",
                "first": page_size,
            }
            if after is not None:
                variables["after"] = after
            result = await self._post_graphql(client, query, variables)
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

        self._stats["topics_found"] = len(topic_ids)
        self._stats["comments_found"] = len(comments)
        return topic_ids, post_ids, comments

    async def _fetch_topics_batch(
        self, client: httpx.AsyncClient, topic_ids: List[str]
    ) -> List[Dict[str, Any]]:
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
        result = await self._post_graphql(client, query, {"ids": topic_ids})
        return result.get("topics") or []

    async def _fetch_posts_batch(
        self, client: httpx.AsyncClient, post_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Fetch full post details by IDs (schema: posts(ids: [ID!]!)).

        Args:
            client: HTTP client
            post_ids: 1–100 post IDs (schema constraint)

        Returns:
            List of Post objects with content, owner, topics, etc.
        """
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
        result = await self._post_graphql(client, query, {"ids": post_ids})
        posts = result.get("posts") or []
        self._stats["posts_found"] += len(posts)
        return posts

    def _build_post_url(self, host: str, post_id: str) -> str:
        """Build web URL for a post. Slab uses host and post id."""
        base = host if host.startswith("http") else f"https://{host}"
        return f"{base.rstrip('/')}/posts/{post_id}"

    def _build_topic_url(self, host: str, topic_id: str) -> str:
        """Build web URL for a topic."""
        base = host if host.startswith("http") else f"https://{host}"
        return f"{base.rstrip('/')}/t/{topic_id}"

    def _iter_topic_entities(
        self,
        all_topics: List[Dict[str, Any]],
        host: str,
    ) -> Generator[SlabTopicEntity, None, None]:
        """Yield SlabTopicEntity for each topic."""
        for topic_data in all_topics:
            topic_id = topic_data.get("id")
            topic_name = topic_data.get("name", "Untitled Topic")
            desc = self._json_description_to_string(topic_data.get("description"))
            yield SlabTopicEntity(
                entity_id=topic_id,
                breadcrumbs=[],
                topic_id=topic_id,
                name=topic_name,
                created_at=self._parse_datetime(topic_data.get("insertedAt")),
                updated_at=self._parse_datetime(topic_data.get("updatedAt")),
                description=desc,
                slug=None,
                web_url_value=self._build_topic_url(host, topic_id),
            )

    def _iter_post_entities(
        self,
        posts: List[Dict[str, Any]],
        topics_by_id: Dict[str, Dict[str, Any]],
        host: str,
    ) -> Generator[SlabPostEntity, None, None]:
        """Yield SlabPostEntity for each post."""
        for post_data in posts:
            post_id = post_data.get("id")
            post_title = post_data.get("title", "Untitled Post")
            post_topics = post_data.get("topics") or []
            first_topic = post_topics[0] if post_topics else {}
            topic_id = first_topic.get("id", "")
            topic_name = first_topic.get("name", "Unknown topic")
            content_plain = self._quill_delta_to_plain_text(post_data.get("content"))
            owner = post_data.get("owner") or {}
            author = (
                {
                    "id": owner.get("id"),
                    "name": owner.get("name"),
                    "email": owner.get("email"),
                }
                if owner
                else None
            )
            breadcrumbs = []
            if topic_id and topic_id in topics_by_id:
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=topic_id,
                        name=topics_by_id[topic_id].get("name", topic_name),
                        entity_type=SlabTopicEntity.__name__,
                    )
                )
            yield SlabPostEntity(
                entity_id=post_id,
                breadcrumbs=breadcrumbs,
                post_id=post_id,
                title=post_title,
                created_at=self._parse_datetime(post_data.get("insertedAt")),
                updated_at=self._parse_datetime(post_data.get("updatedAt")),
                content=content_plain or None,
                topic_id=topic_id or "",
                topic_name=topic_name,
                author=author,
                tags=[],
                slug=None,
                web_url_value=self._build_post_url(host, post_id),
            )

    def _iter_comment_entities(
        self,
        comment_payloads: List[Dict[str, Any]],
        host: str,
    ) -> Generator[SlabCommentEntity, None, None]:
        """Yield SlabCommentEntity for each comment from search payloads.

        When the API returns comment.post we use real post_id/post_title; otherwise
        we emit with placeholder values so comments are still synced.
        """
        base = host if host.startswith("http") else f"https://{host}"
        base_r = base.rstrip("/")
        for payload in comment_payloads:
            comment = payload.get("comment") or {}
            node_content = payload.get("node_content")
            comment_id = comment.get("id")
            if not comment_id:
                continue
            post_obj = comment.get("post") or {}
            post_id = (post_obj.get("id") or "").strip()
            post_title = (post_obj.get("title") or "").strip() or "Unknown post"
            content_json = comment.get("content") or node_content
            content_plain = self._quill_delta_to_plain_text(content_json) if content_json else ""
            author_data = comment.get("author") or {}
            author = (
                {
                    "id": author_data.get("id"),
                    "name": author_data.get("name"),
                    "email": author_data.get("email"),
                }
                if author_data
                else None
            )
            if post_id:
                comment_url = f"{base_r}/posts/{post_id}#comment-{comment_id}"
            else:
                comment_url = f"{base_r}/comments/{comment_id}"
            yield SlabCommentEntity(
                entity_id=comment_id,
                breadcrumbs=[],
                comment_id=comment_id,
                content=content_plain or "",
                created_at=self._parse_datetime(comment.get("insertedAt")),
                updated_at=None,
                post_id=post_id or "",
                post_title=post_title,
                topic_id=None,
                topic_name=None,
                author=author,
                web_url_value=comment_url,
            )

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all entities from Slab.

        organization(host) returns PublicOrganization (id, name, host only).
        Topic and post IDs are discovered via search(); full data via topics(ids)
        and posts(ids). Comments are collected from search results and yielded.

        Yields:
            SlabTopicEntity, SlabPostEntity, then SlabCommentEntity instances
        """
        self.logger.info("Starting Slab entity generation")

        try:
            async with self.http_client() as client:
                org = await self._fetch_organization(client)
                host = (org.get("host") or "").strip() or "app.slab.com"

                (
                    topic_ids,
                    post_ids,
                    comment_payloads,
                ) = await self._fetch_topic_and_post_ids_via_search(client)

                topics_by_id: Dict[str, Dict[str, Any]] = {}
                all_topics: List[Dict[str, Any]] = []
                for i in range(0, len(topic_ids), POSTS_IDS_BATCH_SIZE):
                    batch_ids = topic_ids[i : i + POSTS_IDS_BATCH_SIZE]
                    batch = await self._fetch_topics_batch(client, batch_ids)
                    for topic_data in batch:
                        tid = topic_data.get("id")
                        if tid:
                            topics_by_id[tid] = topic_data
                            all_topics.append(topic_data)

                for entity in self._iter_topic_entities(all_topics, host):
                    yield entity

                for i in range(0, len(post_ids), POSTS_IDS_BATCH_SIZE):
                    batch_ids = post_ids[i : i + POSTS_IDS_BATCH_SIZE]
                    posts = await self._fetch_posts_batch(client, batch_ids)
                    for entity in self._iter_post_entities(posts, topics_by_id, host):
                        yield entity

                for entity in self._iter_comment_entities(comment_payloads, host):
                    yield entity

            self.logger.info(
                f"Slab sync complete. Stats: {self._stats['topics_found']} topics, "
                f"{self._stats['posts_found']} posts, {self._stats['comments_found']} comments"
            )

        except Exception as e:
            self.logger.error(f"Error during Slab entity generation: {str(e)}", exc_info=True)
            raise
