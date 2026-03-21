"""Microsoft Teams source implementation.

Retrieves data from Microsoft Teams, including:
 - Teams the user has joined
 - Channels within teams
 - Chats (1:1, group, meeting)
 - Messages in channels and chats
 - Team members

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview
  https://learn.microsoft.com/en-us/graph/api/user-list-joinedteams
  https://learn.microsoft.com/en-us/graph/api/channel-list
  https://learn.microsoft.com/en-us/graph/api/chat-list
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import TeamsConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.teams import (
    TeamsChannelEntity,
    TeamsChatEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
    TeamsUserEntity,
    _parse_dt,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Teams",
    short_name="teams",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=TeamsConfig,
    labels=["Communication", "Collaboration"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class TeamsSource(BaseSource):
    """Microsoft Teams source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft Teams including teams, channels, chats, and messages.

    It provides comprehensive access to Teams resources with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: TeamsConfig,
    ) -> TeamsSource:
        """Create a new Microsoft Teams source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization + Accept headers with a fresh token."""
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: dict | None = None) -> Any:
        """Make an authenticated GET request to Microsoft Graph API.

        Uses OAuth 2.0 with rotating refresh tokens.  On 401, attempts a
        single token refresh before letting ``raise_for_status`` translate
        the response into a ``SourceAuthError``.
        """
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Microsoft Graph — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_user_entities(self) -> AsyncGenerator[TeamsUserEntity, None]:
        """Generate TeamsUserEntity objects for users in the organization."""
        self.logger.info("Starting user entity generation")
        url: str | None = f"{self.GRAPH_BASE_URL}/users"
        params: dict | None = {
            "$top": 100,
            "$select": "id,displayName,userPrincipalName,mail,jobTitle,department,officeLocation",
        }

        try:
            user_count = 0
            while url:
                data = await self._get(url, params=params)
                users = data.get("value", [])
                self.logger.info(f"Retrieved {len(users)} users")

                for user_data in users:
                    user_count += 1
                    user_id = user_data.get("id")
                    display_name = user_data.get("displayName", "Unknown User")

                    yield TeamsUserEntity(
                        breadcrumbs=[],
                        id=user_id,
                        name=display_name,
                        created_at=None,
                        updated_at=None,
                        display_name=display_name,
                        user_principal_name=user_data.get("userPrincipalName"),
                        mail=user_data.get("mail"),
                        job_title=user_data.get("jobTitle"),
                        department=user_data.get("department"),
                        office_location=user_data.get("officeLocation"),
                    )

                url = data.get("@odata.nextLink")
                if url:
                    params = None

            self.logger.info(f"Completed user generation. Total users: {user_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating user entities: {e}")

    async def _generate_team_entities(self) -> AsyncGenerator[TeamsTeamEntity, None]:
        """Generate TeamsTeamEntity objects for teams the user has joined."""
        self.logger.info("Starting team entity generation")
        url: str | None = f"{self.GRAPH_BASE_URL}/me/joinedTeams"

        try:
            team_count = 0
            while url:
                data = await self._get(url)
                teams = data.get("value", [])
                self.logger.info(f"Retrieved {len(teams)} teams")

                for team_data in teams:
                    team_count += 1
                    team_id = team_data.get("id")
                    display_name = team_data.get("displayName", "Unknown Team")

                    yield TeamsTeamEntity(
                        breadcrumbs=[],
                        id=team_id,
                        name=display_name,
                        created_at=_parse_dt(team_data.get("createdDateTime")),
                        updated_at=None,
                        display_name=display_name,
                        description=team_data.get("description"),
                        visibility=team_data.get("visibility"),
                        is_archived=team_data.get("isArchived"),
                        web_url=team_data.get("webUrl"),
                        web_url_override=team_data.get("webUrl"),
                        classification=team_data.get("classification"),
                        specialization=team_data.get("specialization"),
                        internal_id=team_data.get("internalId"),
                    )

                url = data.get("@odata.nextLink")

            self.logger.info(f"Completed team generation. Total teams: {team_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating team entities: {e}")
            raise

    async def _generate_channel_entities(
        self, team_id: str, team_name: str
    ) -> AsyncGenerator[TeamsChannelEntity, None]:
        """Generate TeamsChannelEntity objects for channels in a team."""
        self.logger.info(f"Starting channel entity generation for team: {team_name}")
        url: str | None = f"{self.GRAPH_BASE_URL}/teams/{team_id}/channels"

        try:
            channel_count = 0
            while url:
                data = await self._get(url)
                channels = data.get("value", [])
                self.logger.info(f"Retrieved {len(channels)} channels for team {team_name}")

                for channel_data in channels:
                    channel_count += 1
                    channel_id = channel_data.get("id")
                    display_name = channel_data.get("displayName", "Unknown Channel")

                    yield TeamsChannelEntity(
                        breadcrumbs=[
                            Breadcrumb(
                                entity_id=team_id,
                                name=team_name,
                                entity_type="TeamsTeamEntity",
                            )
                        ],
                        id=channel_id,
                        name=display_name,
                        created_at=_parse_dt(channel_data.get("createdDateTime")),
                        updated_at=None,
                        team_id=team_id,
                        display_name=display_name,
                        description=channel_data.get("description"),
                        email=channel_data.get("email"),
                        membership_type=channel_data.get("membershipType"),
                        is_archived=channel_data.get("isArchived"),
                        is_favorite_by_default=channel_data.get("isFavoriteByDefault"),
                        web_url_override=channel_data.get("webUrl"),
                    )

                url = data.get("@odata.nextLink")

            self.logger.info(
                f"Completed channel generation for team {team_name}. "
                f"Total channels: {channel_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating channel entities for team {team_name}: {e}")

    async def _generate_channel_message_entities(
        self,
        team_id: str,
        team_name: str,
        channel_id: str,
        channel_name: str,
        team_breadcrumb: Breadcrumb,
        channel_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TeamsMessageEntity, None]:
        """Generate TeamsMessageEntity objects for messages in a channel."""
        self.logger.info(f"Starting message generation for channel: {channel_name}")
        url: str | None = f"{self.GRAPH_BASE_URL}/teams/{team_id}/channels/{channel_id}/messages"
        params: dict | None = {"$top": 50}

        try:
            message_count = 0
            while url:
                data = await self._get(url, params=params)
                messages = data.get("value", [])
                self.logger.info(f"Retrieved {len(messages)} messages for channel {channel_name}")

                for message_data in messages:
                    message_count += 1
                    yield TeamsMessageEntity.from_api(
                        message_data,
                        breadcrumbs=[team_breadcrumb, channel_breadcrumb],
                        team_id=team_id,
                        channel_id=channel_id,
                    )

                url = data.get("@odata.nextLink")
                if url:
                    params = None

            self.logger.info(
                f"Completed message generation for channel {channel_name}. "
                f"Total messages: {message_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating messages for channel {channel_name}: {e}")

    async def _generate_chat_entities(self) -> AsyncGenerator[TeamsChatEntity, None]:
        """Generate TeamsChatEntity objects for user's chats."""
        self.logger.info("Starting chat entity generation")
        url: str | None = f"{self.GRAPH_BASE_URL}/me/chats"
        params: dict | None = {"$top": 50}

        try:
            chat_count = 0
            while url:
                data = await self._get(url, params=params)
                chats = data.get("value", [])
                self.logger.info(f"Retrieved {len(chats)} chats")

                for chat_data in chats:
                    chat_count += 1
                    chat_id = chat_data.get("id")
                    topic = chat_data.get("topic", "")
                    chat_type = chat_data.get("chatType", "oneOnOne")
                    name = topic if topic else f"{chat_type} chat"

                    yield TeamsChatEntity(
                        breadcrumbs=[],
                        id=chat_id,
                        name=name,
                        created_at=_parse_dt(chat_data.get("createdDateTime")),
                        updated_at=_parse_dt(chat_data.get("lastUpdatedDateTime")),
                        chat_type=chat_type,
                        topic_label=name,
                        topic=topic if topic else None,
                        web_url_override=chat_data.get("webUrl"),
                    )

                url = data.get("@odata.nextLink")
                if url:
                    params = None

            self.logger.info(f"Completed chat generation. Total chats: {chat_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating chat entities: {e}")

    async def _generate_chat_message_entities(
        self,
        chat_id: str,
        chat_topic: str | None,
        chat_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TeamsMessageEntity, None]:
        """Generate TeamsMessageEntity objects for messages in a chat."""
        display_chat = chat_topic if chat_topic else chat_id[:8]
        self.logger.info(f"Starting message generation for chat: {display_chat}")
        url: str | None = f"{self.GRAPH_BASE_URL}/chats/{chat_id}/messages"
        params: dict | None = {"$top": 50}

        try:
            message_count = 0
            while url:
                data = await self._get(url, params=params)
                messages = data.get("value", [])
                self.logger.info(f"Retrieved {len(messages)} messages for chat {display_chat}")

                for message_data in messages:
                    message_count += 1
                    yield TeamsMessageEntity.from_api(
                        message_data,
                        breadcrumbs=[chat_breadcrumb],
                        chat_id=chat_id,
                    )

                url = data.get("@odata.nextLink")
                if url:
                    params = None

            self.logger.info(
                f"Completed message generation for chat {display_chat}. "
                f"Total messages: {message_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating messages for chat {display_chat}: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft Teams entities.

        Yields entities in the following order:
          - TeamsUserEntity for users in the organization
          - TeamsTeamEntity for teams the user has joined
          - TeamsChannelEntity for channels in each team
          - TeamsMessageEntity for messages in each channel
          - TeamsChatEntity for user's chats
          - TeamsMessageEntity for messages in each chat
        """
        self.logger.info("Starting Microsoft Teams entity generation")
        entity_count = 0

        async for user_entity in self._generate_user_entities():
            entity_count += 1
            yield user_entity

        async for team_entity in self._generate_team_entities():
            entity_count += 1
            yield team_entity

            team_id = team_entity.id
            team_name = team_entity.display_name
            team_breadcrumb = Breadcrumb(
                entity_id=team_id,
                name=team_entity.display_name,
                entity_type="TeamsTeamEntity",
            )

            async for channel_entity in self._generate_channel_entities(team_id, team_name):
                entity_count += 1
                yield channel_entity

                channel_id = channel_entity.id
                channel_name = channel_entity.display_name
                channel_breadcrumb = Breadcrumb(
                    entity_id=channel_id,
                    name=channel_entity.display_name,
                    entity_type="TeamsChannelEntity",
                )

                async for message_entity in self._generate_channel_message_entities(
                    team_id,
                    team_name,
                    channel_id,
                    channel_name,
                    team_breadcrumb,
                    channel_breadcrumb,
                ):
                    entity_count += 1
                    yield message_entity

        async for chat_entity in self._generate_chat_entities():
            entity_count += 1
            yield chat_entity

            chat_id = chat_entity.id
            chat_breadcrumb = Breadcrumb(
                entity_id=chat_id,
                name=chat_entity.name,
                entity_type="TeamsChatEntity",
            )

            async for message_entity in self._generate_chat_message_entities(
                chat_id, chat_entity.topic, chat_breadcrumb
            ):
                entity_count += 1
                yield message_entity

        self.logger.info(f"Microsoft Teams entity generation complete: {entity_count} entities")

    async def validate(self) -> None:
        """Validate credentials by pinging the joinedTeams endpoint."""
        await self._get(f"{self.GRAPH_BASE_URL}/me/joinedTeams")
