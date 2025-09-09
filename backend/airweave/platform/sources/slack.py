"""Slack source implementation (BYOC).

Minimal connector to fetch channels, messages, and users from Slack using
user-provided OAuth2 client credentials (BYOC). We assume long-lived access tokens
and rely on TokenManager if refresh is configured.
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.slack import (
    SlackChannelEntity,
    SlackMessageEntity,
    SlackUserEntity,
)
from airweave.platform.sources._base import BaseSource

# TODO: log number of api calls
# TODO: what calls do we make?
# TODO: can we batch?


@source(
    name="Slack",
    short_name="slack",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="SlackAuthConfig",
    config_class="SlackConfig",
    labels=["Communication", "Team Collaboration"],
)
class SlackSource(BaseSource):
    """Slack source implementation (BYOC)."""

    def __init__(self):
        """Initialize Slack source with API usage tracking state."""
        super().__init__()
        # Track API usage per method: { method: {"calls": int, "items": int} }
        self._api_stats: Dict[str, Dict[str, int]] = {}

    # ---------- API usage tracking helpers ----------
    def _extract_method_from_url(self, url: str) -> str:
        try:
            # Expecting .../api/{method}
            return url.split("/api/")[-1]
        except Exception:
            return url

    def _increment_api_call(self, method: str) -> int:
        stats = self._api_stats.setdefault(method, {"calls": 0, "items": 0})
        stats["calls"] += 1
        return stats["calls"]

    def _increment_item_count(self, method: str, amount: int) -> None:
        stats = self._api_stats.setdefault(method, {"calls": 0, "items": 0})
        stats["items"] += int(amount or 0)

    def _get_api_stats_snapshot(self) -> Dict[str, Dict[str, int]]:
        return {k: dict(v) for k, v in self._api_stats.items()}

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "SlackSource":
        """Create a new Slack source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make authenticated GET request to the Slack Web API with usage tracking."""
        token = await self.get_access_token()
        if not token:
            raise ValueError("No access token available for Slack API request")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        method = self._extract_method_from_url(url)
        call_index = self._increment_api_call(method)
        self.logger.debug(
            f"\n\nSlack API call #{call_index} to {method} with params={params or {}}\n\n"
        )

        response = await client.get(url, headers=headers, params=params)

        # Handle 429 Too Many Requests with Retry-After
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after is not None else 1.0
            except Exception:
                delay = 1.0
            self.logger.warning(
                f"Slack rate limited on {method} (429). Retry-After={retry_after}. "
                f"Sleeping {delay}s and retrying..."
            )
            await asyncio.sleep(delay)
            response = await client.get(url, headers=headers, params=params)

        # Handle 401 by attempting refresh via token manager
        if response.status_code == 401:
            new_token = await self.refresh_on_unauthorized()
            if not new_token:
                response.raise_for_status()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await client.get(url, headers=headers, params=params)

        response.raise_for_status()
        data = response.json()

        # Slack responses include "ok" to indicate success
        if not data.get("ok", False):
            # Gracefully handle not_in_channel
            if data.get("error") == "not_in_channel":
                self.logger.warning(
                    f"\n\nSlack API not_in_channel for {url} with params {params}\n\n"
                )
                return {"ok": True}
            raise httpx.HTTPError(f"Slack API error: {data}")
        return data

    async def _generate_channel_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        url = "https://slack.com/api/conversations.list"
        params: Dict[str, Any] = {"limit": 200}

        while True:
            data = await self._get_with_auth(client, url, params=params)
            channels = data.get("channels", []) or []
            self._increment_item_count("conversations.list", len(channels))
            self.logger.info(f"\n\nconversations.list page returned {len(channels)} channels\n\n")

            for channel in channels:
                yield SlackChannelEntity(
                    entity_id=channel["id"],
                    channel_id=channel["id"],
                    name=channel.get("name"),
                    is_channel=channel.get("is_channel", False),
                    is_group=channel.get("is_group", False),
                    is_im=channel.get("is_im", False),
                    is_mpim=channel.get("is_mpim", False),
                    is_archived=channel.get("is_archived", False),
                    created=channel.get("created"),
                    creator=channel.get("creator"),
                    members=channel.get("members", []),
                    topic=channel.get("topic"),
                    purpose=channel.get("purpose"),
                )

            next_cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        url = "https://slack.com/api/users.list"
        params: Dict[str, Any] = {"limit": 200}

        while True:
            data = await self._get_with_auth(client, url, params=params)
            members = data.get("members", []) or []
            self._increment_item_count("users.list", len(members))
            self.logger.info(f"\n\nusers.list page returned {len(members)} users\n\n")

            for member in members:
                profile = member.get("profile", {}) or {}
                yield SlackUserEntity(
                    entity_id=member["id"],
                    user_id=member["id"],
                    team_id=member.get("team_id"),
                    name=member.get("name"),
                    real_name=member.get("real_name"),
                    display_name=profile.get("display_name"),
                    is_bot=member.get("is_bot", False),
                    is_admin=member.get("is_admin", False),
                    is_owner=member.get("is_owner", False),
                    is_primary_owner=member.get("is_primary_owner", False),
                    is_restricted=member.get("is_restricted", False),
                    is_ultra_restricted=member.get("is_ultra_restricted", False),
                    updated=profile.get("updated"),
                )

            next_cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

    async def _generate_message_entities(
        self, client: httpx.AsyncClient, channel_id: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        url = "https://slack.com/api/conversations.history"
        params: Dict[str, Any] = {"channel": channel_id, "limit": 200}

        while True:
            try:
                data = await self._get_with_auth(client, url, params=params)
            except httpx.HTTPError as e:
                msg = str(e)
                if "not_in_channel" in msg:
                    self.logger.warning(
                        f"\n\nSkipping messages for channel {channel_id}: not_in_channel\n\n"
                    )
                    return
                raise

            messages = data.get("messages", []) or []
            # Track and log how many messages we retrieved with this call
            self._increment_item_count("conversations.history", len(messages))
            self.logger.info(
                (
                    f"\n\nconversations.history page for channel {channel_id} returned "
                    f"{len(messages)} messages\n\n"
                )
            )

            for message in messages:
                yield SlackMessageEntity(
                    entity_id=f"{channel_id}-{message.get('ts')}",
                    channel_id=channel_id,
                    user_id=message.get("user"),
                    text=message.get("text"),
                    ts=message.get("ts"),
                    thread_ts=message.get("thread_ts"),
                    team=message.get("team"),
                    attachments=message.get("attachments", []),
                    blocks=message.get("blocks", []),
                    files=message.get("files", []),
                    reactions=message.get("reactions", []),
                    is_bot=message.get("bot_id") is not None,
                    subtype=message.get("subtype"),
                    edited=message.get("edited"),
                )

            next_cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not next_cursor:
                break

            params["cursor"] = next_cursor

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Yield Slack channels with messages, then users (minimal test connector)."""
        async with httpx.AsyncClient() as client:
            # Channels and their messages
            async for channel in self._generate_channel_entities(client):
                yield channel
                # Messages for each channel
                async for msg in self._generate_message_entities(client, channel.channel_id):
                    yield msg

            # Users
            async for user in self._generate_user_entities(client):
                yield user

        # Emit summary of API usage
        stats = self._get_api_stats_snapshot()
        for method, s in stats.items():
            summary_msg = (
                f"\n\nSlack API summary for {method}: "
                f"calls={s.get('calls', 0)}, items={s.get('items', 0)}\n\n"
            )
            self.logger.info(summary_msg)
