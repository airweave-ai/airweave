"""Microsoft Teams (OAuth2 delegated) source via Microsoft Graph.

Reads what the signed-in user can access:
- Teams → channels → channel messages (optionally with replies)
- User chats (DMs, group, meeting) → chat messages

Docs & key behaviors:
- /me/joinedTeams (Team.ReadBasic.All). https://learn.microsoft.com/graph/api/user-list-joinedteams
- /teams/{team}/channels (Channel.ReadBasic.All). https://learn.microsoft.com/graph/api/channel-list
- /teams/{team}/channels/{channel}/messages ($top≤50; $expand=replies). https://learn.microsoft.com/graph/api/channel-list-messages
- /me/chats, /chats/{id}/messages ($top≤50; supports $orderby/$filter on lastModifiedDateTime).
  https://learn.microsoft.com/graph/api/chat-list ;
  https://learn.microsoft.com/graph/api/chat-list-messages
- Throttling: honor Retry-After on 429/503. https://learn.microsoft.com/graph/throttling
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.microsoft_teams import (
    TeamsChannelEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Microsoft Teams",
    short_name="microsoft_teams",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="MicrosoftTeamsAuthConfig",
    config_class="MicrosoftTeamsConfig",
    labels=["Chat", "Collaboration"],
)
class MicrosoftTeamsSource(BaseSource):
    """Microsoft Teams OAuth2 source for accessing Teams and chat data via Microsoft Graph API.

    This source connects to Microsoft Teams using OAuth2 delegated authentication
    to read teams, channels, and messages that the signed-in user has access to.
    It supports incremental synchronization using cursors to track progress.
    """

    GRAPH = "https://graph.microsoft.com/v1.0"

    # ---------- cursors ----------
    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field name for tracking synchronization progress.

        Returns:
            The cursor field name used to store nested maps for incremental sync.
        """
        # Store nested maps for incremental:
        # { "channels": {channel_id: "last_seen_message_id"},
        #   "chats":    {chat_id: "last_seen_lastModifiedDateTime"} }
        return "teams_oauth_cursors"

    def _get_cursor(self) -> Dict[str, Dict[str, str]]:
        data = self.cursor.cursor_data if self.cursor and self.cursor.cursor_data else {}
        cur = data.get(self.get_default_cursor_field(), {}) or {}
        cur.setdefault("channels", {})
        cur.setdefault("chats", {})
        return cur

    def _save_cursor(self, cur: Dict[str, Dict[str, str]]) -> None:
        if not self.cursor:
            return
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}
        self.cursor.cursor_data[self.get_default_cursor_field()] = cur

    # ---------- HTTP helpers ----------
    async def _oauth_get(
        self, client: httpx.AsyncClient, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.GRAPH}{path}"
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        while True:
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 401:
                # refresh and retry once
                new_token = await self.refresh_on_unauthorized()
                if new_token:
                    headers["Authorization"] = f"Bearer {new_token}"
                    resp = await client.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code in (429, 503):
                # Graph throttling: use Retry-After seconds
                try:
                    delay = float(resp.headers.get("Retry-After", "1"))
                except Exception:
                    delay = 1.0
                self.logger.warning(f"Graph throttled on {path}; sleeping {delay}s")
                await asyncio.sleep(max(0.0, delay) + 0.05)
                continue
            if resp.status_code in (401, 403, 404):
                self.logger.warning(f"Graph {resp.status_code} on {path}")
                return None
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return None

    async def _page_collection(
        self,
        client: httpx.AsyncClient,
        first_path: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Yield list pages, following @odata.nextLink."""
        data = await self._oauth_get(client, first_path, params)
        while data:
            yield data.get("value", []) or []
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            # nextLink is an absolute URL; call through with GET
            # (reuse same helper but pass full URL via a small wrapper)
            token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            while True:
                resp = await client.get(next_link, headers=headers, timeout=30.0)
                if resp.status_code in (429, 503):
                    try:
                        delay = float(resp.headers.get("Retry-After", "1"))
                    except Exception:
                        delay = 1.0
                    await asyncio.sleep(max(0.0, delay) + 0.05)
                    continue
                if resp.status_code == 401:
                    new = await self.refresh_on_unauthorized()
                    if new:
                        headers["Authorization"] = f"Bearer {new}"
                        resp = await client.get(next_link, headers=headers, timeout=30.0)
                if resp.status_code in (401, 403, 404):
                    data = None
                    break
                resp.raise_for_status()
                data = resp.json()
                break

    # ---------- entity builders ----------
    @staticmethod
    def _team_entity(raw: Dict[str, Any]) -> TeamsTeamEntity:
        return TeamsTeamEntity(
            entity_id=raw["id"],
            breadcrumbs=[],
            team_id=raw["id"],
            display_name=raw.get("displayName"),
            description=raw.get("description"),
            visibility=raw.get("visibility"),
        )

    @staticmethod
    def _channel_entity(team: Dict[str, Any], ch: Dict[str, Any]) -> TeamsChannelEntity:
        return TeamsChannelEntity(
            entity_id=ch["id"],
            breadcrumbs=[
                Breadcrumb(entity_id=team["id"], name=team.get("displayName", ""), type="team")
            ],
            channel_id=ch["id"],
            team_id=team["id"],
            display_name=ch.get("displayName"),
            description=ch.get("description"),
            membership_type=ch.get("membershipType"),
            is_archived=ch.get("isArchived"),
        )

    def _message_entity(
        self, *, team: Optional[Dict[str, Any]], ch: Optional[Dict[str, Any]], m: Dict[str, Any]
    ) -> TeamsMessageEntity:
        # sender
        sender = (m.get("from") or {}).get("user") or {}
        author_id = sender.get("id")
        author_display = sender.get("displayName") or sender.get("userPrincipalName")

        attachments = (
            m.get("attachments") or []
            if getattr(self, "include_attachments_metadata", True)
            else []
        )
        hosted_contents = []
        if attachments or m.get("hostedContents"):
            hosted_contents = [
                {"id": hc.get("id"), "contentType": hc.get("contentType")}
                for hc in (m.get("hostedContents") or [])
            ]

        return TeamsMessageEntity(
            entity_id=m["id"],
            breadcrumbs=(
                [Breadcrumb(entity_id=team["id"], name=team.get("displayName", ""), type="team")]
                + (
                    [Breadcrumb(entity_id=ch["id"], name=ch.get("displayName", ""), type="channel")]
                    if ch
                    else []
                )
            ),
            message_id=m["id"],
            team_id=team["id"] if team else None,
            channel_id=ch["id"] if ch else None,
            chat_id=m.get("chatId") if not ch else None,
            reply_to_id=m.get("replyToId"),
            author_id=author_id,
            author_display=author_display,
            content=((m.get("body") or {}).get("content")),
            created_at=m.get("createdDateTime"),
            last_modified_at=m.get("lastModifiedDateTime"),
            deleted_at=m.get("deletedDateTime"),
            attachments=attachments,
            hosted_contents=hosted_contents,
            reactions=m.get("reactions") or [],
        )

    async def _get_teams(self, client: httpx.AsyncClient) -> list[Dict[str, Any]]:
        """Get teams based on configuration."""
        if self.team_ids:
            return [{"id": t} for t in self.team_ids]

        teams = []
        async for page in self._page_collection(client, "/me/joinedTeams"):
            teams.extend(page)
        return teams

    async def _get_channels(self, client: httpx.AsyncClient, team_id: str) -> list[Dict[str, Any]]:
        """Get channels for a team, filtered by configuration."""
        channels = []
        async for page in self._page_collection(client, f"/teams/{team_id}/channels"):
            channels.extend(page)

        if self.channel_ids:
            channels = [c for c in channels if c.get("id") in set(self.channel_ids)]

        return channels

    async def _process_channel_messages(
        self,
        client: httpx.AsyncClient,
        team: Dict[str, Any],
        channel: Dict[str, Any],
        cursors: Dict[str, Dict[str, str]],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages for a specific channel."""
        ch_id = channel["id"]
        last_seen_id = (cursors.get("channels") or {}).get(ch_id)
        top = 50 if self.page_size > 50 else (1 if self.page_size < 1 else self.page_size)

        params = {"$top": str(top)}
        if self.include_replies:
            params["$expand"] = "replies"

        fetched = 0
        hit_seen = False
        async for page in self._page_collection(
            client, f"/teams/{team['id']}/channels/{ch_id}/messages", params
        ):
            for m in page:
                if last_seen_id and m.get("id") == last_seen_id:
                    hit_seen = True
                    break
                try:
                    yield self._message_entity(team=team, ch=channel, m=m)
                    fetched += 1
                except Exception as e:
                    self.logger.warning(f"Skip channel message {m.get('id')}: {e}")

            if hit_seen:
                break
            if self.max_messages_per_conversation and fetched >= self.max_messages_per_conversation:
                break

            # update newest seen id per page
            if page:
                newest = page[0].get("id")
                if newest:
                    cursors["channels"][ch_id] = newest

    async def _process_channels(
        self, client: httpx.AsyncClient, cursors: Dict[str, Dict[str, str]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process all Teams channels and their messages."""
        teams = await self._get_teams(client)

        for team in teams:
            try:
                yield self._team_entity(team)
            except Exception as e:
                self.logger.warning(f"Team entity failed for {team.get('id')}: {e}")

            channels = await self._get_channels(client, team["id"])

            for channel in channels:
                try:
                    yield self._channel_entity(team, channel)
                except Exception as e:
                    self.logger.warning(f"Channel entity failed {channel.get('id')}: {e}")

                async for message in self._process_channel_messages(client, team, channel, cursors):
                    yield message

                self._save_cursor(cursors)

    async def _process_chat_messages(
        self, client: httpx.AsyncClient, chat: Dict[str, Any], cursors: Dict[str, Dict[str, str]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages for a specific chat."""
        chat_id = chat["id"]
        top = 50 if self.page_size > 50 else (1 if self.page_size < 1 else self.page_size)

        params = {"$top": str(top), "$orderby": "lastModifiedDateTime desc"}
        last_ts = (cursors.get("chats") or {}).get(chat_id)
        if last_ts:
            params["$filter"] = f"lastModifiedDateTime gt {last_ts}"

        fetched = 0
        async for page in self._page_collection(client, f"/chats/{chat_id}/messages", params):
            for m in page:
                try:
                    yield self._message_entity(team=None, ch=None, m=m)
                    fetched += 1
                except Exception as e:
                    self.logger.warning(f"Skip chat message {m.get('id')}: {e}")

            if self.max_messages_per_conversation and fetched >= self.max_messages_per_conversation:
                break

            # update last modified timestamp cursor (most recent item first)
            if page:
                newest_ts = page[0].get("lastModifiedDateTime") or page[0].get("createdDateTime")
                if newest_ts:
                    cursors["chats"][chat_id] = newest_ts

    async def _process_chats(
        self, client: httpx.AsyncClient, cursors: Dict[str, Dict[str, str]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process all user chats and their messages."""
        chats = []
        async for page in self._page_collection(client, "/me/chats", params={"$top": "50"}):
            chats.extend(page)

        if self.chat_ids:
            chats = [c for c in chats if c.get("id") in set(self.chat_ids)]

        for chat in chats:
            async for message in self._process_chat_messages(client, chat, cursors):
                yield message
            self._save_cursor(cursors)

    # ---------- main ----------
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Teams entities by fetching data from Microsoft Graph API.

        This method orchestrates the synchronization of Teams channels and user chats.
        It supports incremental sync using cursors to track progress and avoid
        re-processing already seen messages.

        Yields:
            ChunkEntity: Teams, channels, and message entities from the user's
                        accessible Teams and chats.
        """
        cursors = self._get_cursor()

        async with httpx.AsyncClient() as client:
            if self.include_channels:
                async for entity in self._process_channels(client, cursors):
                    yield entity

            if self.include_chats:
                async for entity in self._process_chats(client, cursors):
                    yield entity
