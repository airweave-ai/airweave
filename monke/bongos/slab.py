"""Slab bongo implementation.

Creates, updates, and deletes test topics and posts via the Slab GraphQL API.
Schema: createTopic, createPost, deletePost, deleteTopic. We do not use updatePostContent
(Slab's API does not accept it reliably).
"""

"""NOTE
This E2E is simplified, since it excludes `topic` entities creation, modification, retrieval and deletion.

At the time of writing there seems to be a problem on the service's side, namely

```
curl -s -X POST 'https://api.slab.com/v1/graphql' -v \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{
    "query": "mutation($id: ID!, $delta: Json!) { updatePostContent(id: $id, delta: $delta) { id } }",
    "variables": {
      "id": "<POST-ID>",
      "delta": "{\"ops\":[{\"insert\":\"foobar\"}]}"
    }
  }'
```

leads to a timeout, most likely due to a bug in the service's implementation.

Ideally, this should be revisited later.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

# Per https://studio.apollographql.com/public/Slab/variant/current/home
SLAB_GRAPHQL_URL = "https://api.slab.com/v1/graphql"


class SlabBongo(BaseBongo):
    """Bongo for Slab: creates topics and posts with embedded verification tokens."""

    connector_type = "slab"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.api_key: str = (
            credentials.get("api_key")
            or credentials.get("access_token")
            or credentials.get("generic_api_key")
        )
        if not self.api_key:
            raise ValueError(
                "Missing Slab API token. Expected 'api_key' or 'access_token'. "
                f"Available: {list(credentials.keys())}"
            )
        self.entity_count = int(kwargs.get("entity_count", 2))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency = int(kwargs.get("max_concurrency", 2))
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 400))
        self.rate_limit_delay = rate_limit_ms / 1000.0
        self.last_request_time = 0.0

        self._topics: List[Dict[str, Any]] = []
        self._posts: List[Dict[str, Any]] = []

        self.logger = get_logger("slab_bongo")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def _graphql(
        self, client: httpx.AsyncClient, query: str, variables: Optional[Dict] = None
    ) -> Dict:
        await self._rate_limit()
        resp = await client.post(
            SLAB_GRAPHQL_URL,
            headers=self._headers(),
            json={"query": query, "variables": variables or {}},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            msg = "; ".join(e.get("message", "Unknown") for e in data["errors"])
            hint = ""
            if "FORBIDDEN" in msg.upper():
                hint = (
                    " Your Slab API token may be read-only or lack create/edit/delete scope. "
                    "Use a token with write access (see https://help.slab.com/en/articles/6545629-developer-tools-api-webhooks)."
                )
            raise RuntimeError(f"GraphQL errors: {msg}.{hint}")
        return data.get("data", {})

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create topics and posts with embedded tokens."""
        from monke.generation.slab import generate_slab_post, generate_slab_topic

        self.logger.info("Creating Slab topics and posts")
        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:
            for i in range(self.entity_count):
                async with semaphore:
                    token = str(uuid.uuid4())[:8]

                    # Create topic. Schema: createTopic(name: String!, description: Json, ...).
                    # Slab's Json scalar rejects plain strings for description; use name only.
                    topic_data = await generate_slab_topic(self.openai_model, token)
                    name = topic_data["name"]
                    if token not in name:
                        name = f"{name} {token}"
                    mut_topic = """
                    mutation($name: String!) {
                        createTopic(name: $name) {
                            id
                            name
                        }
                    }
                    """
                    variables_topic = {"name": name}
                    result = await self._graphql(client, mut_topic, variables_topic)
                    topic = result.get("createTopic")
                    if not topic or not topic.get("id"):
                        raise RuntimeError(f"createTopic failed: {result}")
                    topic_id = topic["id"]
                    self._topics.append(
                        {"id": topic_id, "name": topic["name"], "token": token}
                    )
                    entities.append({
                        "type": "topic",
                        "id": f"topic_{topic_id}",
                        "slab_id": topic_id,
                        "token": token,
                        "expected_content": token,
                    })

                    # Create post in this topic. Force token into title (content not submitted).
                    post_data = await generate_slab_post(self.openai_model, token)
                    title = post_data["title"]
                    if token not in title:
                        title = f"{title} {token}"
                    mut_post = """
                    mutation($title: String, $topicId: ID) {
                        createPost(title: $title, topicId: $topicId) {
                            id
                            title
                        }
                    }
                    """
                    result = await self._graphql(
                        client,
                        mut_post,
                        {"title": title, "topicId": topic_id},
                    )
                    post = result.get("createPost")
                    if not post or not post.get("id"):
                        raise RuntimeError(f"createPost failed: {result}")
                    post_id = post["id"]
                    # Skip updatePostContent: Slab's API does not accept it reliably; post has title only.

                    self._posts.append(
                        {"id": post_id, "title": post["title"], "token": token}
                    )
                    entities.append({
                        "type": "post",
                        "id": f"post_{post_id}",
                        "slab_id": post_id,
                        "token": token,
                        "expected_content": token,
                    })

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of posts. Skipped for Slab: updatePostContent is unreliable on the service."""
        return []

    async def delete_entities(self) -> List[str]:
        """Delete all created posts then topics."""
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete given entities; posts first, then topics.

        When a topic is deleted, we also delete the post we created for that topic
        (same index in _topics/_posts) and return both ids, so remaining_entities
        does not expect that post to still be in the index.
        """
        deleted: List[str] = []
        posts_to_delete = [e for e in entities if e.get("type") == "post"]
        topics_to_delete = [e for e in entities if e.get("type") == "topic"]

        # Cascade: for each topic we delete, also delete its corresponding post
        existing_post_slab_ids = {
            e.get("slab_id") or (e.get("id") or "").replace("post_", "")
            for e in posts_to_delete
        }
        for t in topics_to_delete:
            t_slab_id = t.get("slab_id") or (t.get("id") or "").replace("topic_", "")
            for i, top in enumerate(self._topics):
                if top.get("id") == t_slab_id and i < len(self._posts):
                    post_info = self._posts[i]
                    pid = post_info["id"]
                    if pid not in existing_post_slab_ids:
                        posts_to_delete.append({
                            "type": "post",
                            "id": f"post_{pid}",
                            "slab_id": pid,
                        })
                        existing_post_slab_ids.add(pid)
                    break

        async with httpx.AsyncClient() as client:
            for e in posts_to_delete:
                slab_id = e.get("slab_id") or e.get("id", "").replace("post_", "")
                if not slab_id:
                    continue
                try:
                    await self._graphql(
                        client,
                        "mutation($id: ID!) { deletePost(id: $id) { id } }",
                        {"id": slab_id},
                    )
                    deleted.append(e.get("id") or f"post_{slab_id}")
                except Exception as ex:
                    self.logger.warning(f"Delete post {slab_id}: {ex}")
            for e in topics_to_delete:
                slab_id = e.get("slab_id") or e.get("id", "").replace("topic_", "")
                if not slab_id:
                    continue
                try:
                    await self._graphql(
                        client,
                        "mutation($id: ID!) { deleteTopic(id: $id) { id } }",
                        {"id": slab_id},
                    )
                    deleted.append(e.get("id") or f"topic_{slab_id}")
                except Exception as ex:
                    self.logger.warning(f"Delete topic {slab_id}: {ex}")

        return deleted

    async def cleanup(self):
        """Remove all created topics and posts."""
        if self.created_entities:
            await self.delete_entities()
        self._topics.clear()
        self._posts.clear()
        self.created_entities = []
