"""Discord source implementation.

Retrieves data (read-only) from a user's Discord account:
    - Guilds (Servers)
    - Channels (within each guild)
    - Messages (within each channel)
    - Users/Members (within each guild)

References:
    https://discord.com/developers/docs
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities.discord import (
    DiscordChannelEntity,
    DiscordGuildEntity,
    DiscordMessageEntity,
    DiscordUserEntity,
)
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)

@source(
    "Discord", "discord", AuthType.oauth2_with_refresh_rotating , labels=["Communication" , "Team Collaboration"]
)
class DiscordSource(BaseSource):
    """Discord source implementation.

    This connector retrieves hierarchical data from Discord's REST API:
        - Guilds (Servers)
        - Channels (within each guild)
        - Messages (within each channel)
        - Users/Members (within each guild)
    """

    BASE_URL = "https://discord.com/api/v10/"

    @classmethod
    async def create(cls, access_token: str) -> "DiscordSource":
        """Create a new Discord source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _make_request(
        self, client: httpx.AsyncClient, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to the Discord API."""
        url = f"{self.BASE_URL}{endpoint}"
        logger.debug(f"Making request to: {url}")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = await client.request(method, url, headers=headers, params=params)
        logger.debug(f"Response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def _fetch_guilds(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch guilds the authenticated user is a member of."""
        logger.info("Fetching Guild entities")
        data = await self._make_request(client, "GET", "users/@me/guilds")
        for guild in data:
            yield guild

    async def _generate_channel_entities(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate channel entities for a guild."""
        logger.info(f"Generating Channel entities for guild: {guild_id}")
        data = await self._make_request(client, "GET", f"guilds/{guild_id}/channels")
        for channel in data:
            if channel["type"] in [0, 5, 10, 11, 12]:  # Text, announcement, or thread channels
                yield channel

    async def _generate_message_entities(
        self, client: httpx.AsyncClient, channel_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate message entities for a channel."""
        logger.info(f"Generating Message entities for channel: {channel_id}")
        last_message_id = None
        while True:
            params = {"limit": 100}
            if last_message_id:
                params["before"] = last_message_id
            data = await self._make_request(client, "GET", f"channels/{channel_id}/messages", params=params)
            messages = data
            if not messages:
                break
            for message in messages:
                yield message
            last_message_id = messages[-1]["id"]

    async def _generate_member_entities(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate member entities for a guild."""
        logger.info(f"Generating Member entities for guild: {guild_id}")
        after = None
        while True:
            params = {"limit": 1000}
            if after:
                params["after"] = after
            data = await self._make_request(client, "GET", f"guilds/{guild_id}/members", params=params)
            members = data
            if not members:
                break
            for member in members:
                yield member
            after = members[-1]["user"]["id"]

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all Discord entities (Guilds, Channels, Messages, Members)."""
        logger.info("Generating Discord entities")
        async with httpx.AsyncClient() as client:
            # Generate Guild entities
            async for guild in self._fetch_guilds(client):
                guild_entity = DiscordGuildEntity(
                    entity_id=guild["id"],
                    guild_id=guild["id"],
                    name=guild["name"],
                    icon=guild.get("icon"),
                    owner_id=guild["owner_id"],
                    members=guild.get("members", []),
                    roles=guild.get("roles", []),
                    region=guild.get("region"),
                )
                yield guild_entity

                # Generate Channel entities
                async for channel in self._generate_channel_entities(client, guild["id"]):
                    channel_entity = DiscordChannelEntity(
                        entity_id=channel["id"],
                        channel_id=channel["id"],
                        guild_id=guild["id"],
                        name=channel["name"],
                        type=channel["type"],
                        private=channel.get("permission_overwrites", []) != [],
                        permissions=channel.get("permission_overwrites", []),
                        topic=channel.get("topic"),
                        position=channel.get("position", 0),
                    )
                    yield channel_entity

                    # Generate Message entities
                    async for message in self._generate_message_entities(client, channel["id"]):
                        message_entity = DiscordMessageEntity(
                            entity_id=message["id"],
                            message_id=message["id"],
                            channel_id=channel["id"],
                            guild_id=guild["id"] if channel["type"] != 1 else None,
                            content=message["content"],
                            author=message["author"],
                            timestamp=message["timestamp"],
                            edited_timestamp=message.get("edited_timestamp"),
                            mentions=message.get("mentions", []),
                            reactions=message.get("reactions", []),
                            attachments=message.get("attachments", []),
                            embeds=message.get("embeds", []),
                            pinned=message.get("pinned", False),
                            type=message["type"],
                        )
                        yield message_entity

                # Generate Member entities
                async for member in self._generate_member_entities(client, guild["id"]):
                    user = member["user"]
                    member_entity = DiscordUserEntity(
                        entity_id=user["id"],
                        user_id=user["id"],
                        username=user["username"],
                        discriminator=user.get("discriminator"),
                        global_name=user.get("global_name"),
                        avatar=user.get("avatar"),
                        bot=user.get("bot", False),
                        roles=member.get("roles", []),
                        joined_at=member.get("joined_at"),
                        guild_id=guild["id"],
                    )
                    yield member_entity