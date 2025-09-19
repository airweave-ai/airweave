"""Discord source implementation (Bot token).

Reads guilds (by ID), channels, threads, and messages using REST.
- Auth: Authorization: Bot <token>
- Messages: GET /channels/{channel_id}/messages with before/after & limit (1–100)
- Threads: GET /guilds/{guild_id}/threads/active
- Rate limits: back off on HTTP 429 using Retry-After.

Docs (reference):
- Bot auth header & usage: Discord developer docs / Social SDK How-To.
- Messages params (before/after/limit up to 100): Messages resource.
- Active guild threads: Guild resource / Threads topic.
- Rate limits & Retry-After: Support/dev article on bot rate limiting.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.discord import (
    DiscordChannelEntity,
    DiscordGuildEntity,
    DiscordMessageEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Discord",
    short_name="discord",
    auth_type=AuthType.api_key,
    auth_config_class="DiscordAuthConfig",
    config_class="DiscordConfig",
    labels=["Chat", "Community"],
)
class DiscordSource(BaseSource):
    """Discord source connector (REST + Bot token)."""

    API_BASE = "https://discord.com/api/v10"

    # Parent channel types that are directly messageable via /channels/{id}/messages
    MESSAGEABLE_PARENT_TYPES = {0, 5}  # GUILD_TEXT=0, GUILD_ANNOUNCEMENT=5
    # Thread channel types
    THREAD_TYPES = {10, 11, 12}  # AnnouncementThread, PublicThread, PrivateThread
    # Forum/media parents hold messages in threads, not the parent itself
    THREAD_PARENTS = {15, 16}  # FORUM=15, MEDIA=16

    @classmethod
    async def create(cls, api_key: str, config: Optional[Dict[str, Any]] = None) -> "DiscordSource":
        """Create the source with a Bot token and parsed config."""
        inst = cls()
        inst.bot_token = api_key
        cfg = config or {}

        inst.guild_ids: List[str] = cfg.get("guild_ids", []) or []
        inst.channel_ids: List[str] = cfg.get("channel_ids", []) or []

        inst.include_threads: bool = bool(cfg.get("include_threads", True))
        inst.include_attachments_metadata: bool = bool(
            cfg.get("include_attachments_metadata", True)
        )
        inst.include_bot_authors: bool = bool(cfg.get("include_bot_authors", True))
        inst.message_types: List[int] = cfg.get("message_types", []) or []

        inst.page_size: int = int(cfg.get("page_size", 100) or 100)
        inst.page_size = (
            1 if inst.page_size < 1 else (100 if inst.page_size > 100 else inst.page_size)
        )

        inst.max_messages_per_channel: Optional[int] = (
            int(cfg["max_messages_per_channel"]) if cfg.get("max_messages_per_channel") else None
        )
        inst.after_message_id: Optional[str] = cfg.get("after_message_id") or None

        if not inst.guild_ids:
            raise ValueError("Discord: 'guild_ids' cannot be empty for bot-token crawl.")

        return inst

    # ---------- Incremental cursors ----------
    def get_default_cursor_field(self) -> Optional[str]:
        """Persist a mapping {channel_id: last_seen_message_id}."""
        return "per_channel_last_id"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate that the cursor field matches the expected field name.

        Args:
            cursor_field: The cursor field name to validate.

        Raises:
            ValueError: If the cursor field doesn't match the expected field.
        """
        if cursor_field != self.get_default_cursor_field():
            raise ValueError(
                f"Invalid cursor field '{cursor_field}'. Use '{self.get_default_cursor_field()}'."
            )

    def _get_channel_cursors(self) -> Dict[str, str]:
        data = self.cursor.cursor_data if self.cursor and self.cursor.cursor_data else {}
        return data.get(self.get_default_cursor_field(), {}) or {}

    def _save_channel_cursors(self, mapping: Dict[str, str]) -> None:
        if not self.cursor:
            return
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}
        self.cursor.cursor_data[self.get_default_cursor_field()] = mapping

    # ---------- HTTP helper ----------
    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any] | List[Any]]:
        """Bot-authenticated request with 429 backoff."""
        url = f"{self.API_BASE}{path}"
        headers = {"Authorization": f"Bot {self.bot_token}"}

        while True:
            resp = await client.request(method, url, headers=headers, params=params, timeout=30.0)

            if resp.status_code == 429:
                # Respect per-route/global rate limit via Retry-After (header or JSON)
                try:
                    data = resp.json()
                    retry_after = float(data.get("retry_after", 1.0))
                except Exception:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                self.logger.warning(f"429 on {method} {path}; sleeping {retry_after}s")
                await asyncio.sleep(max(0.0, retry_after) + 0.05)
                continue

            if resp.status_code in (401, 403):
                self.logger.warning(f"{resp.status_code} on {method} {path} (permissions/token?)")
                return None

            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return None

    # ---------- Discord REST calls ----------
    async def _get_guild(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> Optional[Dict[str, Any]]:
        return await self._request(client, "GET", f"/guilds/{guild_id}")

    async def _get_guild_channels(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> List[Dict[str, Any]]:
        data = await self._request(client, "GET", f"/guilds/{guild_id}/channels")
        return data or []

    async def _get_active_guild_threads(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> List[Dict[str, Any]]:
        data = await self._request(client, "GET", f"/guilds/{guild_id}/threads/active")
        if isinstance(data, dict) and "threads" in data:
            return data["threads"] or []
        return []

    async def _list_channel_messages(
        self,
        client: httpx.AsyncClient,
        channel_id: str,
        *,
        after: Optional[str],
        before: Optional[str],
        limit: int,
        cap: Optional[int],
    ):
        """Yield batches of messages honoring before/after pagination."""
        fetched = 0
        params: Dict[str, Any] = {"limit": str(limit)}
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        while True:
            if cap is not None:
                remain = cap - fetched
                if remain <= 0:
                    break
                params["limit"] = str(min(limit, remain))

            data = await self._request(
                client, "GET", f"/channels/{channel_id}/messages", params=params
            )
            if not data:
                break
            batch: List[Dict[str, Any]] = data
            if not batch:
                break

            fetched += len(batch)
            yield batch

            if after:
                # Move window forward
                newest = max(m["id"] for m in batch)
                if newest == after:
                    break
                params["after"] = newest
                after = newest
            else:
                # Walk history backwards
                oldest = min(m["id"] for m in batch)
                params["before"] = oldest
                before = oldest

    # ---------- entity builders ----------
    def _guild_entity(self, raw: Dict[str, Any]) -> DiscordGuildEntity:
        return DiscordGuildEntity(
            entity_id=raw["id"],
            breadcrumbs=[],
            guild_id=raw["id"],
            name=raw.get("name"),
            description=raw.get("description"),
            owner_id=str(raw.get("owner_id")) if raw.get("owner_id") else None,
            icon=raw.get("icon"),
            features=raw.get("features", []) or [],
        )

    def _channel_entity(self, guild: Dict[str, Any], ch: Dict[str, Any]) -> DiscordChannelEntity:
        return DiscordChannelEntity(
            entity_id=ch["id"],
            breadcrumbs=[
                Breadcrumb(entity_id=guild["id"], name=guild.get("name", ""), type="guild")
            ],
            channel_id=ch["id"],
            guild_id=guild["id"],
            name=ch.get("name"),
            topic=ch.get("topic"),
            type=int(ch.get("type", 0)),
            parent_id=ch.get("parent_id"),
            nsfw=ch.get("nsfw"),
            archived=ch.get("archived"),
            auto_archive_duration=ch.get("auto_archive_duration"),
        )

    def _message_entity(
        self, guild: Dict[str, Any], channel: Dict[str, Any], m: Dict[str, Any]
    ) -> Optional[DiscordMessageEntity]:
        # Optional filters
        if not self.include_bot_authors and (m.get("author", {}).get("bot") is True):
            return None
        if self.message_types:
            t = m.get("type")
            if t is not None and t not in self.message_types:
                return None

        author = m.get("author") or {}
        display = author.get("global_name") or author.get("username")
        attachments = m.get("attachments") or [] if self.include_attachments_metadata else []

        return DiscordMessageEntity(
            entity_id=m["id"],
            breadcrumbs=[
                Breadcrumb(entity_id=guild["id"], name=guild.get("name", ""), type="guild"),
                Breadcrumb(entity_id=channel["id"], name=channel.get("name", ""), type="channel"),
            ],
            message_id=m["id"],
            channel_id=str(m.get("channel_id") or channel["id"]),
            guild_id=guild["id"],
            author_id=author.get("id"),
            author_username=author.get("username"),
            author_display=display,
            author_is_bot=author.get("bot"),
            content=m.get("content"),
            timestamp=m.get("timestamp"),
            edited_timestamp=m.get("edited_timestamp"),
            pinned=m.get("pinned"),
            type=m.get("type"),
            mentions=m.get("mentions") or [],
            attachments=attachments,
            embeds=m.get("embeds") or [],
            reactions=m.get("reactions") or [],
            reference=m.get("message_reference"),
        )

    async def _get_all_channels(
        self, client: httpx.AsyncClient, guild_id: str
    ) -> List[Dict[str, Any]]:
        """Get all channels and threads for a guild, with optional filtering."""
        channels = await self._get_guild_channels(client, guild_id) or []
        threads: List[Dict[str, Any]] = []

        if self.include_threads:
            try:
                threads = await self._get_active_guild_threads(client, guild_id)
            except Exception as e:
                self.logger.warning(f"Active threads failed for guild {guild_id}: {e}")

        all_channels: List[Dict[str, Any]] = list(channels)
        for t in threads:
            t.setdefault("guild_id", guild_id)
            all_channels.append(t)

        # Optional channel filter
        if self.channel_ids:
            allowed = set(self.channel_ids)
            all_channels = [c for c in all_channels if c.get("id") in allowed]

        return all_channels

    def _is_messageable_channel(self, channel: Dict[str, Any]) -> bool:
        """Check if a channel type can have messages fetched."""
        ch_type = int(channel.get("type", 0))
        is_thread = ch_type in self.THREAD_TYPES
        messageable_parent = ch_type in self.MESSAGEABLE_PARENT_TYPES
        forum_parent = ch_type in self.THREAD_PARENTS

        if not (is_thread or messageable_parent):
            return False
        if forum_parent:
            # Messages live in child threads, not on the parent
            return False
        return True

    async def _process_channel_messages(
        self,
        client: httpx.AsyncClient,
        guild: Dict[str, Any],
        channel: Dict[str, Any],
        cursors: Dict[str, str],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages for a specific channel."""
        ch_id = channel["id"]
        after = cursors.get(ch_id) or self.after_message_id
        before = None if after else None

        total_emitted = 0
        try:
            async for batch in self._list_channel_messages(
                client,
                ch_id,
                after=after,
                before=before,
                limit=self.page_size,
                cap=self.max_messages_per_channel if after is None else None,
            ):
                for m in batch:
                    ent = self._message_entity(guild, channel, m)
                    if ent:
                        yield ent
                        total_emitted += 1

                # Update cursor to newest ID seen
                newest_id = max(msg["id"] for msg in batch)
                prev = cursors.get(ch_id)
                if prev is None or int(newest_id) > int(prev):
                    cursors[ch_id] = newest_id

        except Exception as e:
            self.logger.error(f"Error fetching messages for {ch_id}: {e}")
            return

        self.logger.debug(
            f"Channel {ch_id} ({channel.get('name', '')}): emitted {total_emitted} messages."
        )

    async def _process_guild(
        self, client: httpx.AsyncClient, guild_id: str, cursors: Dict[str, str]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a single guild, yielding all its entities."""
        guild = await self._get_guild(client, guild_id)
        if not guild:
            self.logger.warning(f"Skipping guild {guild_id}: not accessible")
            return

        # Emit guild entity
        yield self._guild_entity(guild)

        # Get all channels and threads
        all_channels = await self._get_all_channels(client, guild_id)

        # Process each channel
        for channel in all_channels:
            try:
                yield self._channel_entity(guild, channel)
            except Exception as e:
                self.logger.warning(f"Failed to build channel entity {channel.get('id')}: {e}")

            if not self._is_messageable_channel(channel):
                continue

            async for message in self._process_channel_messages(client, guild, channel, cursors):
                yield message

    # ---------- main generator ----------
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Discord entities by fetching data from Discord API.

        This method orchestrates the synchronization of Discord guilds, channels,
        and messages. It supports incremental sync using cursors to track the last
        seen message ID per channel.

        Yields:
            ChunkEntity: Guild, channel, and message entities from the configured
                        Discord guilds that the bot has access to.
        """
        per_channel_cursors = self._get_channel_cursors()

        async with httpx.AsyncClient() as client:
            for guild_id in self.guild_ids:
                async for entity in self._process_guild(client, guild_id, per_channel_cursors):
                    yield entity

                # Save after each guild
                self._save_channel_cursors(per_channel_cursors)
